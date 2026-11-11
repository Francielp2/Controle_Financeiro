from datetime import date
from django.db.models import Q, Sum
from financeiro import consultas
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from financeiro.models import Movimentacao, Conta, Categoria, CompromissoFinanceiro


# Retorna o período e os totais de entradas, saídas e resultado com filtros combináveis.
def consultar_resumo_periodo(usuario, inicio, fim, **filtros):
    fluxo = consultar_fluxo_mensal(
        usuario, inicio, fim, **filtros
    )

    entradas = sum(
        (Decimal(mes["entradas"]) for mes in fluxo["meses"]),
        Decimal("0.00"),
    )
    saidas = sum(
        (Decimal(mes["saidas"]) for mes in fluxo["meses"]),
        Decimal("0.00"),
    )

    return {
        "inicio": fluxo["inicio"],
        "fim": fluxo["fim"],
        "entradas": consultas.valor_para_texto(entradas),
        "saidas": consultas.valor_para_texto(saidas),
        "resultado": consultas.valor_para_texto(entradas - saidas),
    }


# Filtra movimentações do usuário e retorna período, tipo, quantidade e dados da lista.
def consultar_movimentacoes(
    usuario, inicio=None, fim=None, tipo=None,
    contas=None, contas_origem=None, contas_destino=None,
    categorias=None, descricao=None, valor_minimo=None, valor_maximo=None
):
    try:
        data_inicio = date.fromisoformat(
            inicio) if inicio is not None else None
        data_fim = date.fromisoformat(fim) if fim is not None else None
    except (TypeError, ValueError):
        raise ValueError("As datas devem usar o formato AAAA-MM-DD.") from None

    if data_inicio and data_fim and data_inicio > data_fim:
        raise ValueError("A data inicial não pode ser posterior à final.")
    if tipo is not None and tipo not in Movimentacao.Tipo.values:
        raise ValueError("Tipo de movimentação inválido.")

    movimentos = consultas.movimentacoes_filtradas(
        usuario, data_inicio, data_fim, tipo=tipo
    )

    ids_contas = _ids_por_nomes(Conta, usuario, contas)
    ids_origem = _ids_por_nomes(Conta, usuario, contas_origem)
    ids_destino = _ids_por_nomes(Conta, usuario, contas_destino)
    ids_categorias = _ids_por_nomes(Categoria, usuario, categorias)

    # "Contas" significa movimentações ligadas a qualquer conta selecionada.
    if ids_contas is not None:
        movimentos = movimentos.filter(
            Q(conta_origem_id__in=ids_contas)
            | Q(conta_destino_id__in=ids_contas)
        )
    if ids_origem is not None:
        movimentos = movimentos.filter(conta_origem_id__in=ids_origem)
    if ids_destino is not None:
        movimentos = movimentos.filter(conta_destino_id__in=ids_destino)
    if ids_categorias is not None:
        movimentos = movimentos.filter(categoria_id__in=ids_categorias)

    if descricao is not None:
        if not isinstance(descricao, str) or not descricao.strip():
            raise ValueError("Informe uma descrição não vazia.")
        movimentos = movimentos.filter(descricao__icontains=descricao.strip())

    try:
        minimo = Decimal(str(valor_minimo)
                         ) if valor_minimo is not None else None
        maximo = Decimal(str(valor_maximo)
                         ) if valor_maximo is not None else None
    except InvalidOperation:
        raise ValueError("Os valores devem ser números válidos.") from None

    if any(valor is not None and (not valor.is_finite() or valor < 0)
            for valor in (minimo, maximo)):
        raise ValueError("Os valores devem ser finitos e não negativos.")
    if minimo is not None and maximo is not None and minimo > maximo:
        raise ValueError("O valor mínimo não pode superar o máximo.")

    if minimo is not None:
        movimentos = movimentos.filter(valor__gte=minimo)
    if maximo is not None:
        movimentos = movimentos.filter(valor__lte=maximo)

    dados = [consultas.movimentacao_para_dict(item) for item in movimentos]

    return {
        "inicio": data_inicio.isoformat() if data_inicio else None,
        "fim": data_fim.isoformat() if data_fim else None,
        "tipo": tipo,
        "quantidade": len(dados),
        "movimentacoes": dados,
    }


# Filtra por uma lista de nomes e retorna a queryset resultante.
def _filtrar_nomes(queryset, nomes):
    if nomes is None:
        return queryset

    if not isinstance(nomes, list) or not nomes or any(
        not isinstance(nome, str) or not nome.strip() for nome in nomes
    ):
        raise ValueError("Informe uma lista de nomes não vazios.")

    filtro = Q(nome__iexact=nomes[0].strip())
    for nome in nomes[1:]:
        filtro |= Q(nome__iexact=nome.strip())

    return queryset.filter(filtro)


# Resolve nomes do usuário e retorna seus IDs, ou None quando não há filtro.
def _ids_por_nomes(modelo, usuario, nomes):
    if nomes is None:
        return None

    registros = list(
        _filtrar_nomes(modelo.objects.filter(usuario=usuario), nomes)
    )
    encontrados = {registro.nome.casefold() for registro in registros}
    ausentes = [
        nome for nome in nomes
        if nome.strip().casefold() not in encontrados
    ]

    if ausentes:
        raise ValueError(
            "Nome não encontrado nos seus registros: " + ", ".join(ausentes)
        )

    return [registro.id for registro in registros]


# Consulta contas do usuário, inclusive inativas, e retorna quantidade e dados selecionados.
def consultar_contas(usuario, nomes=None, ativa=None, tipo=None):
    if ativa is not None and not isinstance(ativa, bool):
        raise ValueError("O estado da conta deve ser verdadeiro ou falso.")
    if tipo is not None and tipo not in Conta.Tipo.values:
        raise ValueError("Tipo de conta inválido.")

    contas = _filtrar_nomes(Conta.objects.filter(usuario=usuario), nomes)

    if ativa is not None:
        contas = contas.filter(ativa=ativa)
    if tipo is not None:
        contas = contas.filter(tipo=tipo)

    dados = [
        {
            "id": conta.id,
            "nome": conta.nome,
            "tipo": conta.tipo,
            "tipo_nome": conta.get_tipo_display(),
            "ativa": conta.ativa,
            "saldo_inicial": consultas.valor_para_texto(conta.saldo_inicial),
            "saldo_atual": consultas.valor_para_texto(conta.saldo_atual),
            "data_criacao": conta.data_criacao.isoformat(),
        }
        for conta in contas.order_by("nome")
    ]

    return {"quantidade": len(dados), "contas": dados}


# Consulta categorias do usuário, inclusive inativas, e retorna quantidade e dados selecionados.
def consultar_categorias(usuario, nomes=None, ativa=None, tipo=None):

    if ativa is not None and not isinstance(ativa, bool):
        raise ValueError("O estado da categoria deve ser verdadeiro ou falso.")
    if tipo is not None and tipo not in Categoria.Tipo.values:
        raise ValueError("Tipo de categoria inválido.")

    categorias = _filtrar_nomes(
        Categoria.objects.filter(usuario=usuario), nomes
    )

    if ativa is not None:
        categorias = categorias.filter(ativa=ativa)
    if tipo is not None:
        categorias = categorias.filter(tipo=tipo)

    dados = [
        {
            "id": categoria.id,
            "nome": categoria.nome,
            "descricao": categoria.descricao,
            "tipo": categoria.tipo,
            "tipo_nome": categoria.get_tipo_display(),
            "ativa": categoria.ativa,
            "data_criacao": categoria.data_criacao.isoformat(),
        }
        for categoria in categorias.order_by("nome", "tipo")
    ]

    return {"quantidade": len(dados), "categorias": dados}


# Consulta compromissos a pagar ou receber com filtros combináveis e retorna quantidade e dados selecionados.
def consultar_compromissos(
    usuario, tipo=None, situacao=None,
    inicio_vencimento=None, fim_vencimento=None,
    contas=None, categorias=None, pessoa=None, titulo=None,
):
    try:
        data_inicio = (
            date.fromisoformat(inicio_vencimento)
            if inicio_vencimento is not None else None
        )
        data_fim = (
            date.fromisoformat(fim_vencimento)
            if fim_vencimento is not None else None
        )
    except (TypeError, ValueError):
        raise ValueError("As datas devem usar o formato AAAA-MM-DD.") from None

    if data_inicio and data_fim and data_inicio > data_fim:
        raise ValueError("A data inicial não pode ser posterior à final.")
    if tipo is not None and tipo not in CompromissoFinanceiro.Tipo.values:
        raise ValueError("Tipo de compromisso inválido.")
    if situacao is not None and situacao not in CompromissoFinanceiro.Status.values:
        raise ValueError("Situação do compromisso inválida.")

    compromissos = (
        CompromissoFinanceiro.objects.filter(usuario=usuario)
        .select_related("conta", "categoria")
        .order_by("data_vencimento", "pk")
    )

    if tipo is not None:
        compromissos = compromissos.filter(tipo=tipo)
    if data_inicio is not None:
        compromissos = compromissos.filter(data_vencimento__gte=data_inicio)
    if data_fim is not None:
        compromissos = compromissos.filter(data_vencimento__lte=data_fim)
    if pessoa is not None:
        compromissos = compromissos.filter(pessoa__icontains=pessoa)
    if titulo is not None:
        compromissos = compromissos.filter(titulo__icontains=titulo)

    ids_contas = _ids_por_nomes(Conta, usuario, contas)
    ids_categorias = _ids_por_nomes(Categoria, usuario, categorias)

    if ids_contas is not None:
        compromissos = compromissos.filter(conta_id__in=ids_contas)
    if ids_categorias is not None:
        compromissos = compromissos.filter(categoria_id__in=ids_categorias)

    dados = []
    for compromisso in compromissos:
        # Usa a situação calculada hoje, inclusive para compromissos vencidos.
        if situacao is not None and compromisso.situacao != situacao:
            continue

        item = consultas.compromisso_para_dict(compromisso)
        item["valor_pago_recebido_inicial"] = consultas.valor_para_texto(
            compromisso.valor_pago_recebido_inicial
        )
        item["valor_apos_cadastro"] = consultas.valor_para_texto(
            compromisso.valor_pago_recebido
            - compromisso.valor_pago_recebido_inicial
        )
        item["data_criacao"] = compromisso.data_criacao.isoformat()
        dados.append(item)

    return {"quantidade": len(dados), "compromissos": dados}


# Retorna quantidade e valores zerados para iniciar os totais de um tipo de compromisso.
def _totais_compromissos_vazios():
    return {
        "quantidade": 0,
        "valor_total": Decimal("0.00"),
        "valor_pago_recebido_inicial": Decimal("0.00"),
        "valor_apos_cadastro": Decimal("0.00"),
        "valor_pago_recebido": Decimal("0.00"),
        "valor_restante": Decimal("0.00"),
    }


# Soma compromissos filtrados e retorna contagem e valores separados em pagar e receber.
def resumir_compromissos(
    usuario, tipo=None, situacao=None,
    inicio_vencimento=None, fim_vencimento=None,
    contas=None, categorias=None, pessoa=None, titulo=None,
):
    selecionados = consultar_compromissos(
        usuario,
        tipo=tipo,
        situacao=situacao,
        inicio_vencimento=inicio_vencimento,
        fim_vencimento=fim_vencimento,
        contas=contas,
        categorias=categorias,
        pessoa=pessoa,
        titulo=titulo,
    )

    grupos = {
        "PAGAR": _totais_compromissos_vazios(),
        "RECEBER": _totais_compromissos_vazios(),
    }
    campos_de_valor = (
        "valor_total",
        "valor_pago_recebido_inicial",
        "valor_apos_cadastro",
        "valor_pago_recebido",
        "valor_restante",
    )

    for item in selecionados["compromissos"]:
        grupo = grupos[item["tipo"]]
        grupo["quantidade"] += 1
        for campo in campos_de_valor:
            grupo[campo] += Decimal(item[campo])

    # Converte Decimal em texto para a resposta poder ser enviada como JSON.
    for grupo in grupos.values():
        for campo in campos_de_valor:
            grupo[campo] = consultas.valor_para_texto(grupo[campo])

    return {
        "quantidade": selecionados["quantidade"],
        "a_pagar": grupos["PAGAR"],
        "a_receber": grupos["RECEBER"],
    }


# Agrupa movimentações filtradas por mês e retorna totais e resultado, incluindo meses sem registros.
def consultar_fluxo_mensal(usuario, inicio, fim, **filtros):
    consulta = consultar_movimentacoes(
        usuario, inicio=inicio, fim=fim, **filtros
    )

    atual = date.fromisoformat(consulta["inicio"]).replace(day=1)
    ultimo = date.fromisoformat(consulta["fim"]).replace(day=1)
    meses = {}

    while atual <= ultimo:
        meses[atual.strftime("%Y-%m")] = {
            "entradas": Decimal("0.00"),
            "saidas": Decimal("0.00"),
            "transferencias": Decimal("0.00"),
        }
        if atual == ultimo:
            break
        atual = date(
            atual.year + (atual.month == 12),
            1 if atual.month == 12 else atual.month + 1,
            1,
        )

    for movimento in consulta["movimentacoes"]:
        valores = meses[movimento["data"][:7]]
        valor = Decimal(movimento["valor"])

        if movimento["tipo"] == Movimentacao.Tipo.ENTRADA:
            valores["entradas"] += valor
        elif movimento["tipo"] == Movimentacao.Tipo.SAIDA:
            valores["saidas"] += valor
        else:
            valores["transferencias"] += valor

    return {
        "inicio": consulta["inicio"],
        "fim": consulta["fim"],
        "quantidade": consulta["quantidade"],
        "meses": [
            {
                "mes": mes,
                "entradas": consultas.valor_para_texto(valores["entradas"]),
                "saidas": consultas.valor_para_texto(valores["saidas"]),
                "resultado": consultas.valor_para_texto(
                    valores["entradas"] - valores["saidas"]
                ),
                "transferencias": consultas.valor_para_texto(
                    valores["transferencias"]
                ),
            }
            for mes, valores in meses.items()
        ],
    }


# Agrupa entradas e saídas por tipo e categoria e retorna contagem e total de cada grupo.
def consultar_totais_por_categoria(usuario, inicio, fim, **filtros):
    consulta = consultar_movimentacoes(
        usuario, inicio=inicio, fim=fim, **filtros
    )
    grupos = {}

    for movimento in consulta["movimentacoes"]:
        # Transferência não tem categoria e não representa receita ou despesa.
        if movimento["tipo"] == Movimentacao.Tipo.TRANSFERENCIA:
            continue

        chave = (
            movimento["tipo"],
            movimento["categoria"] or "Sem categoria",
        )
        if chave not in grupos:
            grupos[chave] = {
                "tipo": chave[0],
                "categoria": chave[1],
                "quantidade": 0,
                "total": Decimal("0.00"),
            }

        grupos[chave]["quantidade"] += 1
        grupos[chave]["total"] += Decimal(movimento["valor"])

    ordenados = sorted(
        grupos.values(),
        key=lambda grupo: (-grupo["total"], grupo["tipo"], grupo["categoria"]),
    )

    return {
        "inicio": consulta["inicio"],
        "fim": consulta["fim"],
        "quantidade": sum(grupo["quantidade"] for grupo in ordenados),
        "categorias": [
            {
                "tipo": grupo["tipo"],
                "categoria": grupo["categoria"],
                "quantidade": grupo["quantidade"],
                "total": consultas.valor_para_texto(grupo["total"]),
            }
            for grupo in ordenados
        ],
    }


# Retorna a quantidade e os saldos das contas selecionadas, atuais ou até uma data, além do saldo total.
def consultar_saldos(usuario, ate=None, contas=None, ativa=None, tipo=None):
    try:
        data_limite = date.fromisoformat(ate) if ate is not None else None
    except (TypeError, ValueError):
        raise ValueError("A data deve usar o formato AAAA-MM-DD.") from None

    if ativa is not None and not isinstance(ativa, bool):
        raise ValueError("O estado da conta deve ser verdadeiro ou falso.")
    if tipo is not None and tipo not in Conta.Tipo.values:
        raise ValueError("Tipo de conta inválido.")

    ids = _ids_por_nomes(Conta, usuario, contas)
    selecionadas = Conta.objects.filter(usuario=usuario)

    if ids is not None:
        selecionadas = selecionadas.filter(id__in=ids)
    if ativa is not None:
        selecionadas = selecionadas.filter(ativa=ativa)
    if tipo is not None:
        selecionadas = selecionadas.filter(tipo=tipo)
    if data_limite is not None:
        selecionadas = selecionadas.filter(
            data_criacao__date__lte=data_limite
        )

    dados = []
    total = Decimal("0.00")

    for conta in selecionadas.order_by("nome"):
        if data_limite is None:
            saldo = conta.saldo_atual
        else:
            entradas = (
                conta.movimentacoes_destino.filter(
                    usuario=usuario, data__lte=data_limite
                ).aggregate(total=Sum("valor"))["total"]
                or Decimal("0.00")
            )
            saidas = (
                conta.movimentacoes_origem.filter(
                    usuario=usuario, data__lte=data_limite
                ).aggregate(total=Sum("valor"))["total"]
                or Decimal("0.00")
            )
            saldo = conta.saldo_inicial + entradas - saidas

        total += saldo
        dados.append({
            "id": conta.id,
            "nome": conta.nome,
            "ativa": conta.ativa,
            "saldo": consultas.valor_para_texto(saldo),
        })

    return {
        "ate": data_limite.isoformat() if data_limite else None,
        "quantidade": len(dados),
        "saldo_total": consultas.valor_para_texto(total),
        "contas": dados,
    }


# Retorna os saldos mensais das contas selecionadas e, opcionalmente, o saldo de cada conta.
def consultar_saldos_mensais(
    usuario, inicio, fim, contas=None, ativa=None, tipo=None,
    detalhar_contas=False,
):
    try:
        data_inicio = date.fromisoformat(inicio)
        data_fim = date.fromisoformat(fim)
    except (TypeError, ValueError):
        raise ValueError("As datas devem usar o formato AAAA-MM-DD.") from None

    if data_inicio > data_fim:
        raise ValueError("A data inicial não pode ser posterior à final.")
    if not isinstance(detalhar_contas, bool):
        raise ValueError("Detalhar contas deve ser verdadeiro ou falso.")

    # O mês atual só pode mostrar o saldo até hoje.
    fim_considerado = min(data_fim, timezone.localdate())
    if data_inicio > fim_considerado:
        raise ValueError("O período informado ainda não começou.")

    atual = data_inicio.replace(day=1)
    meses = []

    while atual <= fim_considerado:
        fechamento = min(
            consultas.periodo_do_mes(atual)[1],
            fim_considerado,
        )
        saldos = consultar_saldos(
            usuario,
            ate=fechamento.isoformat(),
            contas=contas,
            ativa=ativa,
            tipo=tipo,
        )

        item = {
            "mes": atual.strftime("%Y-%m"),
            "ate": fechamento.isoformat(),
            "quantidade_contas": saldos["quantidade"],
            "saldo_total": saldos["saldo_total"],
        }
        if detalhar_contas:
            item["contas"] = saldos["contas"]

        meses.append(item)
        if atual.month == 12:
            atual = date(atual.year + 1, 1, 1)
        else:
            atual = date(atual.year, atual.month + 1, 1)

    return {
        "inicio": data_inicio.isoformat(),
        "fim_solicitado": data_fim.isoformat(),
        "fim_considerado": fim_considerado.isoformat(),
        "meses": meses,
    }
