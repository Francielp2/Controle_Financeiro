from datetime import date
from decimal import Decimal

from financeiro.models import Categoria, CompromissoFinanceiro, Conta, Movimentacao


ACOES_NOME = {
    "cadastrar_conta": "Nova conta",
    "cadastrar_categoria": "Nova categoria",
    "cadastrar_compromisso": "Novo compromisso",
    "registrar_movimentacao": "Nova movimentação",
}

CAMPOS_NOME = {
    "nome": "Nome", "titulo": "Título", "tipo": "Tipo",
    "valor": "Valor", "valor_total": "Valor total",
    "valor_pago_recebido_inicial": "Valor inicial pago ou recebido",
    "saldo_inicial": "Saldo inicial", "descricao": "Descrição",
    "pessoa": "Pessoa", "data": "Data", "hora": "Hora",
    "data_vencimento": "Vencimento", "ativa": "Ativa",
    "conta": "Conta", "conta_origem": "Conta de origem",
    "conta_destino": "Conta de destino", "categoria": "Categoria",
    "compromisso_financeiro": "Compromisso",
}

TIPOS_NOME = {
    valor: rotulo
    for modelo in (Conta, Categoria, CompromissoFinanceiro, Movimentacao)
    for valor, rotulo in modelo.Tipo.choices
}

CAMPOS_DINHEIRO = {
    "valor", "valor_total", "valor_pago_recebido_inicial", "saldo_inicial",
}


# Remove marcas simples que aparecem quando a resposta é mostrada como texto.
def limpar_resposta(texto):
    return texto.replace("**", "").replace("`", "")


# Converte um campo validado em texto legível para a prévia.
def _valor_legivel(campo, valor):
    if isinstance(valor, dict):
        return valor.get("nome", "")
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if campo in CAMPOS_DINHEIRO:
        return f"R$ {Decimal(str(valor)):.2f}".replace(".", ",")
    if campo in ("data", "data_vencimento"):
        return date.fromisoformat(valor).strftime("%d/%m/%Y")
    if campo == "hora":
        return str(valor)[:5]
    if campo == "tipo":
        return TIPOS_NOME.get(valor, str(valor))
    return str(valor)


# Monta uma linha de movimentação com os dados completos para exibição opcional.
def _linha_movimentacao(item):
    partes = [
        date.fromisoformat(item["data"]).strftime("%d/%m/%Y"),
        item.get("tipo_nome", item["tipo"]),
        _valor_legivel("valor", item["valor"]),
    ]
    if item.get("descricao"):
        partes.append(item["descricao"])
    if item.get("conta_origem"):
        partes.append("de " + item["conta_origem"])
    if item.get("conta_destino"):
        partes.append("para " + item["conta_destino"])
    if item.get("categoria"):
        partes.append("categoria " + item["categoria"])
    if item.get("compromisso"):
        partes.append("compromisso " + item["compromisso"])
    return " · ".join(partes)


# Monta uma linha de compromisso com valores, vencimento e situação.
def _linha_compromisso(item):
    partes = [
        item["titulo"],
        item.get("tipo_nome", item["tipo"]),
        "total " + _valor_legivel("valor", item["valor_total"]),
        "restante " + _valor_legivel("valor", item["valor_restante"]),
        "vence " + _valor_legivel("data_vencimento", item["data_vencimento"]),
        item.get("situacao_nome", item["situacao"]),
    ]
    if item.get("conta"):
        partes.append("conta " + item["conta"])
    if item.get("categoria"):
        partes.append("categoria " + item["categoria"])
    if item.get("pessoa"):
        partes.append("pessoa " + item["pessoa"])
    return " · ".join(partes)


# Retorna prévias para confirmação e listas legíveis sem expor JSON na tela.
def preparar_exibicao(resultados):
    previas = []
    listas = []

    for item in resultados:
        dados = item.get("dados", {})
        if not isinstance(dados, dict):
            continue

        if item.get("ferramenta") == "propor_acao" and dados.get("id_acao"):
            linhas = [
                f"{CAMPOS_NOME.get(campo, campo)}: {_valor_legivel(campo, valor)}"
                for campo, valor in dados["dados"].items()
                if valor is not None and valor != ""
            ]
            previas.append({
                "titulo": ACOES_NOME.get(dados["acao"], "Nova ação"),
                "linhas": linhas,
                "id_acao": dados["id_acao"],
            })

        if item.get("ferramenta") != "consultar_financas":
            continue
        if "movimentacoes" in dados:
            listas.append({
                "titulo": f"Ver movimentações ({dados['quantidade']})",
                "linhas": [
                    _linha_movimentacao(registro)
                    for registro in dados["movimentacoes"]
                ],
            })
        elif "compromissos" in dados:
            listas.append({
                "titulo": f"Ver compromissos ({dados['quantidade']})",
                "linhas": [
                    _linha_compromisso(registro)
                    for registro in dados["compromissos"]
                ],
            })

    return {"previas": previas, "listas": listas}


# Retorna uma confirmação ou os erros do formulário em texto simples.
def mensagem_confirmacao(resultado):
    if resultado.get("confirmada"):
        return "Registro criado com sucesso."
    if resultado.get("erro"):
        return resultado["erro"]
    mensagens = [
        erro["message"]
        for campo in resultado.get("erros", {}).values()
        for erro in campo
    ]
    return " ".join(mensagens) or "Não foi possível gravar o registro."
