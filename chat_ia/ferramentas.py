from datetime import date
from django.db.models import Q
from financeiro import consultas
from decimal import Decimal
from financeiro.models import Movimentacao, Conta, Categoria, CompromissoFinanceiro


# Retorna total de entradas, saídas e resultado do período escolhido no chat. Aproveita  função de resumo do periodo em consultas.py
def consultar_resumo_periodo(usuario, inicio, fim):
    try:
        data_inicio = date.fromisoformat(inicio)
        data_fim = date.fromisoformat(fim)
    except (TypeError, ValueError):
        raise ValueError("As datas devem usar o formato AAAA-MM-DD.") from None

    if data_inicio > data_fim:
        raise ValueError("A data inicial não pode ser posterior à final.")

    # A consulta financeira aplica o filtro pelo usuário recebido do servidor.
    totais = consultas.resumo_periodo(usuario, data_inicio, data_fim)

    return {
        "inicio": data_inicio.isoformat(),
        "fim": data_fim.isoformat(),
        "entradas": consultas.valor_para_texto(totais["entradas"]),
        "saidas": consultas.valor_para_texto(totais["saidas"]),
        "resultado": consultas.valor_para_texto(totais["resultado"]),
    }


# Lista movimentações com filtros combináveis do próprio usuário.
def consultar_movimentacoes(
    usuario, inicio=None, fim=None, tipo=None,
    contas=None, contas_origem=None, contas_destino=None,
    categorias=None,
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

    dados = [consultas.movimentacao_para_dict(item) for item in movimentos]

    return {
        "inicio": data_inicio.isoformat() if data_inicio else None,
        "fim": data_fim.isoformat() if data_fim else None,
        "tipo": tipo,
        "quantidade": len(dados),
        "movimentacoes": dados,
    }


# Faz uma seleção de vários nomes e transforma em filtros
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


# Resolve nomes apenas entre os registros pertencentes ao usuário.
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


# Consulta uma, várias ou todas as contas, inclusive inativas.
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


# Consulta uma, várias ou todas as categorias, inclusive inativas.
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


# CONSULTA COMPROMISSOS A PAGAR OU RECEBER COM FILTROS COMBINÁVEIS
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


# PREPARA OS TOTAIS DE UM TIPO DE COMPROMISSO
def _totais_compromissos_vazios():
    return {
        "quantidade": 0,
        "valor_total": Decimal("0.00"),
        "valor_pago_recebido_inicial": Decimal("0.00"),
        "valor_apos_cadastro": Decimal("0.00"),
        "valor_pago_recebido": Decimal("0.00"),
        "valor_restante": Decimal("0.00"),
    }


# SOMA OS COMPROMISSOS FILTRADOS, SEPARANDO A PAGAR E A RECEBER
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
