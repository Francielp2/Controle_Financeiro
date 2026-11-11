from datetime import date
from financeiro import consultas

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


