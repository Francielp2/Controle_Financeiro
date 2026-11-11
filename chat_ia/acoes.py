import json
from datetime import date, time, timedelta
from decimal import Decimal
from uuid import UUID

from django.db import OperationalError, transaction
from django.db.models import Model
from django.utils import timezone

from financeiro.concorrencia import (
    MENSAGEM_CONCORRENCIA,
    eh_erro_de_concorrencia,
    salvar_formulario_com_tratamento,
)
from financeiro.forms import (
    ContaForm,
    CategoriaForm,
    CompromissoFinanceiroForm,
    MovimentacaoForm,
)
from financeiro.models import (
    Conta,
    Categoria,
    CompromissoFinanceiro,
    Movimentacao,
)

from .models import AcaoPendente


ACOES = {
    "cadastrar_conta": (Conta, ContaForm),
    "cadastrar_categoria": (Categoria, CategoriaForm),
    "cadastrar_compromisso": (
        CompromissoFinanceiro, CompromissoFinanceiroForm
    ),
    "registrar_movimentacao": (Movimentacao, MovimentacaoForm),
}


# Converte valores validados pelo formulário em dados simples para a prévia.
def _valor_para_previa(valor):
    if isinstance(valor, Model):
        return {"id": valor.pk, "nome": str(valor)}
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (date, time)):
        return valor.isoformat()
    return valor


# Valida um cadastro do usuário e retorna a prévia ou os erros, sem gravar no banco.
def preparar_acao(usuario, acao, dados):
    if not isinstance(acao, str) or acao not in ACOES:
        raise ValueError("Ação não permitida.")
    if not isinstance(dados, dict):
        raise ValueError("Os dados da ação devem formar um objeto.")

    modelo, classe_formulario = ACOES[acao]
    extras = set(dados) - set(classe_formulario.Meta.fields)
    if extras:
        raise ValueError(
            "Campos não permitidos: " + ", ".join(sorted(extras))
        )

    formulario = classe_formulario(
        dados,
        instance=modelo(usuario=usuario),
    )

    if not formulario.is_valid():
        return {
            "valido": False,
            "acao": acao,
            "erros": formulario.errors.get_json_data(),
        }

    return {
        "valido": True,
        "acao": acao,
        "dados": {
            campo: _valor_para_previa(valor)
            for campo, valor in formulario.cleaned_data.items()
        },
    }


# Completa os padrões, valida e guarda a proposta; retorna a prévia e o identificador para confirmação.
def criar_acao_pendente(usuario, acao, dados):
    if isinstance(dados, dict):
        dados = dados.copy()

        if acao in ("cadastrar_conta", "cadastrar_categoria"):
            dados.setdefault("ativa", True)

        if acao == "registrar_movimentacao":
            agora = timezone.localtime()
            dados.setdefault("data", agora.date().isoformat())
            dados.setdefault(
                "hora",
                agora.time().replace(second=0, microsecond=0).isoformat(
                    timespec="minutes"
                ),
            )

    previa = preparar_acao(usuario, acao, dados)
    if not previa["valido"]:
        return previa

    try:
        json.dumps(dados, allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError(
            "Os dados da ação devem estar em formato JSON."
        ) from None

    pendente = AcaoPendente.objects.create(
        usuario=usuario,
        acao=acao,
        dados=dados,
    )

    return {
        **previa,
        "id_acao": str(pendente.pk),
        "expira_em": (pendente.criada_em + timedelta(minutes=10)).isoformat(),
    }


# Revalida e grava a ação confirmada uma única vez; retorna o registro criado ou os erros.
def confirmar_acao_pendente(usuario, id_acao):
    try:
        identificador = UUID(str(id_acao))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("Identificador de ação inválido.") from None

    try:
        with transaction.atomic():
            pendente = (
                AcaoPendente.objects.select_for_update()
                .filter(pk=identificador, usuario=usuario)
                .first()
            )

            if pendente is None:
                raise ValueError("Ação pendente não encontrada.")
            if pendente.confirmada_em is not None:
                raise ValueError("Esta ação já foi confirmada.")
            if timezone.now() > pendente.criada_em + timedelta(minutes=10):
                raise ValueError(
                    "Esta ação expirou. Faça a solicitação novamente."
                )
            if pendente.acao not in ACOES:
                raise ValueError("Ação não permitida.")

            modelo, classe_formulario = ACOES[pendente.acao]
            formulario = classe_formulario(
                pendente.dados,
                instance=modelo(usuario=usuario),
            )

            if not salvar_formulario_com_tratamento(formulario):
                return {
                    "confirmada": False,
                    "erros": formulario.errors.get_json_data(),
                }

            pendente.confirmada_em = timezone.now()
            pendente.registro_id = formulario.instance.pk
            pendente.save(update_fields=["confirmada_em", "registro_id"])

            return {
                "confirmada": True,
                "acao": pendente.acao,
                "registro_id": pendente.registro_id,
            }

    except OperationalError as erro:
        if not eh_erro_de_concorrencia(erro):
            raise
        return {"confirmada": False, "erro": MENSAGEM_CONCORRENCIA}
