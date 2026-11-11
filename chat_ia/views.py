import json
from copy import deepcopy
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from openai import OpenAIError

from usuarios.utils import usuario_logado

from .acoes import confirmar_acao_pendente
from .agente import responder
from .apresentacao import (
    limpar_resposta,
    mensagem_confirmacao,
    preparar_exibicao,
)
from .models import AcaoPendente, PRAZO_CHAT, TarefaChat


# Remove tarefas encerradas há mais de dois dias e ações fora do prazo.
def _limpar_dados_antigos(usuario):
    limite = timezone.now() - PRAZO_CHAT
    TarefaChat.objects.filter(
        usuario=usuario, encerrada_em__lt=limite
    ).delete()
    AcaoPendente.objects.filter(usuario=usuario, criada_em__lt=limite).delete()


# Obtém a tarefa em andamento ou inicia a primeira conversa do usuário.
def _tarefa_ativa(usuario):
    tarefa, _ = TarefaChat.objects.get_or_create(
        usuario=usuario, encerrada_em=None
    )
    return tarefa


# Envia ao modelo somente as sete mensagens mais recentes da tarefa atual.
def _contexto_da_tarefa(tarefa):
    return [
        {
            "role": "assistant" if item["papel"] != "usuario" else "user",
            "content": item.get("contexto", item["texto"]),
        }
        for item in tarefa.mensagens[-7:]
    ]


# Marca prévias confirmadas ou vencidas antes de restaurar a conversa na tela.
def _mensagens_para_tela(tarefa):
    mensagens = deepcopy(tarefa.mensagens)
    agora = timezone.now()
    ids = [
        previa["id_acao"]
        for item in mensagens
        for previa in item.get("exibicao", {}).get("previas", [])
    ]
    acoes = {
        str(acao.pk): acao
        for acao in AcaoPendente.objects.filter(usuario=tarefa.usuario, pk__in=ids)
    }
    for item in mensagens:
        for previa in item.get("exibicao", {}).get("previas", []):
            acao = acoes.get(previa["id_acao"])
            if acao is None or agora > acao.criada_em + PRAZO_CHAT:
                previa["situacao"] = "expirada"
            elif acao.confirmada_em is not None:
                previa["situacao"] = "confirmada"
            else:
                previa["situacao"] = "pendente"
    return mensagens


# Restaura a tarefa ativa e oferece as tarefas recentes para retomada.
@login_required
@require_GET
def pagina_chat(request):
    usuario = usuario_logado(request)
    if usuario is None:
        return JsonResponse({"erro": "Perfil financeiro não encontrado."}, status=403)
    request.session.pop("historico_chat_ia", None)
    _limpar_dados_antigos(usuario)
    tarefa = _tarefa_ativa(usuario)
    outras_tarefas = TarefaChat.objects.filter(
        usuario=usuario, encerrada_em__isnull=False
    ).order_by("-encerrada_em")
    return render(request, "chat_ia/chat.html", {
        "tarefa": tarefa,
        "mensagens_iniciais": _mensagens_para_tela(tarefa),
        "outras_tarefas": outras_tarefas,
    })


# Inicia outra tarefa ou retoma uma conversa recente sem misturar contextos.
@login_required
@require_POST
def gerenciar_tarefa(request):
    usuario = usuario_logado(request)
    if usuario is None:
        return JsonResponse({"erro": "Perfil financeiro não encontrado."}, status=403)
    _limpar_dados_antigos(usuario)
    operacao = request.POST.get("operacao")
    if operacao not in ("nova", "retomar"):
        return JsonResponse({"erro": "Operação inválida."}, status=400)

    with transaction.atomic():
        atual = TarefaChat.objects.filter(
            usuario=usuario, encerrada_em__isnull=True
        ).first()
        alvo = None
        if operacao == "retomar":
            try:
                identificador = UUID(request.POST.get("tarefa_id", ""))
            except (TypeError, ValueError, AttributeError):
                return JsonResponse({"erro": "Tarefa inválida."}, status=400)
            alvo = TarefaChat.objects.filter(
                usuario=usuario, pk=identificador
            ).first()
            if alvo is None:
                return JsonResponse({"erro": "Tarefa não encontrada."}, status=404)
        if atual and atual != alvo:
            atual.encerrada_em = timezone.now()
            atual.save(update_fields=["encerrada_em", "atualizada_em"])
        if operacao == "nova":
            TarefaChat.objects.create(usuario=usuario)
        elif alvo.encerrada_em is not None:
            alvo.encerrada_em = None
            alvo.save(update_fields=["encerrada_em", "atualizada_em"])

    return redirect("chat_ia:pagina")


# Recebe uma mensagem e retorna a resposta e os dados consultados em JSON.
@require_POST
def conversar(request):
    if not request.user.is_authenticated:
        return JsonResponse({"erro": "Faça login para usar o chat."}, status=401)

    usuario = usuario_logado(request)
    if usuario is None:
        return JsonResponse(
            {"erro": "Perfil financeiro não encontrado."},
            status=403,
        )

    if request.content_type != "application/json":
        return JsonResponse({"erro": "Envie JSON."}, status=415)

    try:
        corpo = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"erro": "JSON inválido."}, status=400)

    if not isinstance(corpo, dict):
        return JsonResponse({"erro": "Envie um objeto JSON."}, status=400)

    _limpar_dados_antigos(usuario)
    tarefa = _tarefa_ativa(usuario)
    if corpo.get("tarefa_id") != str(tarefa.pk):
        return JsonResponse(
            {"erro": "Outra tarefa está ativa. Atualize a página do chat."},
            status=409,
        )

    try:
        resultado = responder(
            usuario,
            corpo.get("mensagem"),
            _contexto_da_tarefa(tarefa),
        )
    except ValueError as erro:
        return JsonResponse({"erro": str(erro)}, status=400)
    except OpenAIError:
        return JsonResponse(
            {"erro": "Serviço de IA indisponível. Tente novamente."},
            status=503,
        )

    resultado.pop("historico")
    resultado["resposta"] = limpar_resposta(resultado["resposta"])
    resultado["exibicao"] = preparar_exibicao(resultado["resultados"])
    with transaction.atomic():
        atual = TarefaChat.objects.select_for_update().get(pk=tarefa.pk)
        if atual.encerrada_em is not None or atual.mensagens != tarefa.mensagens:
            return JsonResponse(
                {"erro": "A conversa mudou durante a resposta. Envie novamente."},
                status=409,
            )
        if not atual.mensagens:
            atual.titulo = corpo["mensagem"].strip()[:80]
        atual.mensagens = [
            *atual.mensagens,
            {"papel": "usuario", "texto": corpo["mensagem"].strip()},
            {
                "papel": "assistente",
                "texto": resultado["resposta"],
                "exibicao": resultado["exibicao"],
            },
        ]
        atual.save(update_fields=["titulo", "mensagens", "atualizada_em"])
    return JsonResponse(resultado)


# Confirma a proposta do usuário autenticado e retorna o resultado da gravação.
@require_POST
def confirmar(request):
    if not request.user.is_authenticated:
        return JsonResponse({"erro": "Faça login para usar o chat."}, status=401)

    usuario = usuario_logado(request)
    if usuario is None:
        return JsonResponse(
            {"erro": "Perfil financeiro não encontrado."},
            status=403,
        )

    if request.content_type != "application/json":
        return JsonResponse({"erro": "Envie JSON."}, status=415)

    try:
        corpo = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"erro": "JSON inválido."}, status=400)

    if not isinstance(corpo, dict):
        return JsonResponse({"erro": "Envie um objeto JSON."}, status=400)

    _limpar_dados_antigos(usuario)
    with transaction.atomic():
        tarefa = TarefaChat.objects.select_for_update().filter(
            usuario=usuario, encerrada_em=None
        ).first()
        if tarefa is None or corpo.get("tarefa_id") != str(tarefa.pk):
            return JsonResponse(
                {"erro": "Outra tarefa está ativa. Atualize a página do chat."},
                status=409,
            )
        id_acao = str(corpo.get("id_acao"))
        ids_da_tarefa = {
            previa["id_acao"]
            for item in tarefa.mensagens
            for previa in item.get("exibicao", {}).get("previas", [])
        }
        if id_acao not in ids_da_tarefa:
            return JsonResponse({"erro": "Ação não pertence a esta tarefa."}, status=400)

        pendente = AcaoPendente.objects.filter(usuario=usuario, pk=id_acao).first()
        try:
            resultado = confirmar_acao_pendente(usuario, id_acao)
        except ValueError as erro:
            return JsonResponse({"erro": str(erro)}, status=400)

        resultado["mensagem"] = mensagem_confirmacao(resultado)
        if resultado.get("confirmada"):
            for item in tarefa.mensagens:
                for previa in item.get("exibicao", {}).get("previas", []):
                    if previa["id_acao"] == id_acao:
                        previa["situacao"] = "confirmada"
            nome = (
                pendente.dados.get("nome")
                or pendente.dados.get("titulo")
                or pendente.dados.get("descricao")
                or ""
            )
            tarefa.mensagens.append({
                "papel": "sistema",
                "texto": resultado["mensagem"],
                "contexto": (
                    f"O usuário confirmou {resultado['acao']} {nome}. "
                    f"O registro criado tem ID {resultado['registro_id']}."
                ),
            })
            tarefa.save(update_fields=["mensagens", "atualizada_em"])
    return JsonResponse(resultado)
