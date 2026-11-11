from datetime import date
from django.db.models import Q
from financeiro import consultas
from financeiro.models import Movimentacao, Conta, Categoria

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

# Lista as movimentações do usuário no período.
def consultar_movimentacoes(usuario, inicio=None, fim=None, tipo=None):
    """Retorna todas as movimentações que atendem aos filtros."""
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

    # A consulta existente filtra pelo usuário autenticado.
    movimentos = consultas.movimentacoes_filtradas(
        usuario, data_inicio, data_fim, tipo=tipo
    )
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
