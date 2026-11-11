from . import ferramentas
from .acoes import criar_acao_pendente


CONSULTAS = {
    "consultar_movimentacoes": ferramentas.consultar_movimentacoes,
    "consultar_resumo_periodo": ferramentas.consultar_resumo_periodo,
    "consultar_fluxo_mensal": ferramentas.consultar_fluxo_mensal,
    "consultar_totais_por_categoria": ferramentas.consultar_totais_por_categoria,
    "consultar_contas": ferramentas.consultar_contas,
    "consultar_categorias": ferramentas.consultar_categorias,
    "consultar_compromissos": ferramentas.consultar_compromissos,
    "resumir_compromissos": ferramentas.resumir_compromissos,
    "consultar_saldos": ferramentas.consultar_saldos,
    "consultar_saldos_mensais": ferramentas.consultar_saldos_mensais,
}


# Executa uma consulta permitida ou guarda uma proposta; retorna o resultado da função escolhida.
def executar_ferramenta(usuario, nome, argumentos):
    if not isinstance(nome, str):
        raise ValueError("Nome de ferramenta inválido.")
    if not isinstance(argumentos, dict):
        raise ValueError("Os argumentos devem formar um objeto.")
    if "usuario" in argumentos:
        raise ValueError("O usuário é definido pelo servidor.")

    if nome == "propor_acao":
        if set(argumentos) != {"acao", "dados"}:
            raise ValueError("A proposta precisa de ação e dados.")
        return criar_acao_pendente(
            usuario, argumentos["acao"], argumentos["dados"]
        )

    funcao = CONSULTAS.get(nome)
    if funcao is None:
        raise ValueError("Ferramenta não permitida.")

    try:
        return funcao(usuario, **argumentos)
    except TypeError:
        raise ValueError("Argumentos inválidos para esta consulta.") from None
