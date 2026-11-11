import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from openai import OpenAIError
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .agente import responder
from .acoes import confirmar_acao_pendente
from usuarios.utils import usuario_logado


# Exibe a página provisória sem carregar mensagens antigas na tela.
@login_required
@require_GET
def pagina_chat(request):
    return render(request, "chat_ia/chat.html")


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

    try:
        resultado = responder(
            usuario,
            corpo.get("mensagem"),
            request.session.get("historico_chat_ia", []),
        )
    except ValueError as erro:
        return JsonResponse({"erro": str(erro)}, status=400)
    except OpenAIError:
        return JsonResponse(
            {"erro": "Serviço de IA indisponível. Tente novamente."},
            status=503,
        )

    request.session["historico_chat_ia"] = resultado.pop("historico")
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

    try:
        resultado = confirmar_acao_pendente(
            usuario, corpo.get("id_acao")
        )
    except ValueError as erro:
        return JsonResponse({"erro": str(erro)}, status=400)

    return JsonResponse(resultado)
