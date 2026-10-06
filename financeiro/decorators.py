from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from usuarios.utils import usuario_logado


def perfil_obrigatorio(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        usuario = usuario_logado(request)

        if usuario is None:
            messages.info(
                request,
                "Administradores não possuem perfil financeiro.",
            )
            return redirect("admin:index")

        request.usuario = usuario

        return view(request, *args, **kwargs)

    return wrapper