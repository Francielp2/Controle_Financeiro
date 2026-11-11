from datetime import date
from financeiro import consultas
from financeiro.models import Movimentacao

# Retorna entradas, saídas e resultado do período escolhido no chat. Aproveita  função de resumo do periodo em consultas.py


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
