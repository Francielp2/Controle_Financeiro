import json
import os

from openai import OpenAI

from .distribuidor import executar_ferramenta
from .esquemas import obter_ferramentas
from .instrucoes import obter_instrucoes


# Retorna uma versão curta para o modelo; a aplicação recebe a lista completa.
def _resultado_para_modelo(resultado):
    if not isinstance(resultado, dict):
        return resultado

    resumo = resultado.copy()
    for campo in ("movimentacoes", "compromissos"):
        registros = resumo.get(campo)
        if isinstance(registros, list) and len(registros) > 20:
            resumo[campo] = registros[:20]
            resumo["aviso"] = (
                "A lista completa foi entregue à aplicação. "
                "Não calcule totais usando apenas estes 20 registros."
            )

    return resumo


# Interpreta a chamada do modelo e retorna o resultado da função autorizada.
def _executar_chamada(usuario, chamada):
    parametros = json.loads(chamada.arguments)

    if chamada.name == "consultar_financas":
        nome = parametros["nome"]
        argumentos = json.loads(parametros["argumentos_json"])
        return executar_ferramenta(usuario, nome, argumentos)

    if chamada.name == "propor_acao":
        dados = json.loads(parametros["dados_json"])
        return executar_ferramenta(
            usuario,
            "propor_acao",
            {"acao": parametros["acao"], "dados": dados},
        )

    raise ValueError("Ferramenta não permitida.")


# Retorna a resposta do chat, os dados completos das ferramentas e o histórico curto.
def responder(usuario, mensagem, historico=None):
    if not isinstance(mensagem, str) or not mensagem.strip():
        raise ValueError("Escreva uma mensagem.")
    if len(mensagem) > 1000:
        raise ValueError("A mensagem deve ter até 1000 caracteres.")
    if historico is None:
        historico = []
    if not isinstance(historico, list):
        raise ValueError("Histórico inválido.")

    mensagem = mensagem.strip()
    historico = historico[-7:]
    entrada = [
        *historico,
        {"role": "user", "content": mensagem},
    ]
    resultados = []
    cliente = OpenAI()

    for _ in range(4):
        resposta = cliente.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
            instructions=obter_instrucoes(),
            input=entrada,
            tools=obter_ferramentas(),
            parallel_tool_calls=False,
            reasoning={"effort": "none"},
            max_output_tokens=800,
            store=False,
        )

        chamadas = [
            item for item in resposta.output
            if item.type == "function_call"
        ]

        if not chamadas:
            texto = resposta.output_text.strip()
            if not texto:
                texto = "Não consegui elaborar uma resposta. Tente reformular."
            novo_historico = [
                *historico,
                {"role": "user", "content": mensagem},
                {"role": "assistant", "content": texto},
            ][-7:]
            return {
                "resposta": texto,
                "resultados": resultados,
                "historico": novo_historico,
            }

        entrada.extend(resposta.output)

        for chamada in chamadas:
            try:
                resultado = _executar_chamada(usuario, chamada)
            except (ValueError, TypeError, KeyError) as erro:
                resultado = {"erro": str(erro)}
            else:
                resultados.append({
                    "ferramenta": chamada.name,
                    "dados": resultado,
                })

            entrada.append({
                "type": "function_call_output",
                "call_id": chamada.call_id,
                "output": json.dumps(
                    _resultado_para_modelo(resultado),
                    ensure_ascii=False,
                ),
            })

    return {
        "resposta": "Não consegui concluir essa consulta. Tente reformular.",
        "resultados": resultados,
        "historico": historico,
    }
