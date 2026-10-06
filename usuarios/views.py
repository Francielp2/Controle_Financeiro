from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from financeiro.models import Categoria, CompromissoFinanceiro, Conta, Movimentacao

from .forms import UsuarioCreationForm, UsuarioUpdateForm
from .models import Usuario
from .utils import usuario_logado


# LISTA OS USUARIOS CADASTRADOS
@login_required
@user_passes_test(lambda u: u.is_staff, login_url="financeiro:inicio")
def usuario_listar(request):
    usuarios = Usuario.objects.all().order_by(
        "first_name",
        "email",
    )

    return render(
        request,
        "usuarios/listar.html",
        {"usuarios": usuarios},
    )


# DETALHA UM USUARIO
@login_required
def usuario_detalhar(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario.pk != request.user.pk and not request.user.is_staff:
        raise PermissionDenied

    contexto = {
        "usuario": usuario,
        "contas": usuario.contas.all().order_by("nome"),
        "categorias": usuario.categorias.all().order_by("nome"),
        "compromissos": usuario.compromissos.all().order_by(
            "-data_vencimento"
        ),
        "movimentacoes": usuario.movimentacoes.all().order_by(
            "-data",
            "-hora",
        )[:10],
    }

    return render(
        request,
        "usuarios/detalhar.html",
        contexto,
    )


# CRIA UM USUARIO
def usuario_criar(request):
    if request.user.is_authenticated:
        return redirect("financeiro:inicio")

    if request.method == "POST":
        form = UsuarioCreationForm(request.POST)

        if form.is_valid():
            usuario = form.save()

            messages.success(
                request,
                "Usuário cadastrado com sucesso.",
            )

            login(request, usuario)
            return redirect("financeiro:inicio")

    else:
        form = UsuarioCreationForm()

    return render(
        request,
        "form.html",
        {
            "titulo": "Cadastrar usuário",
            "form": form,
            "cancelar_url": reverse("usuarios:usuario_listar"),
        },
    )


# EDITA UM USUARIO
@login_required
def usuario_editar(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario.pk != request.user.pk and not request.user.is_staff:
        raise PermissionDenied

    if request.method == "POST":
        form = UsuarioUpdateForm(
            request.POST,
            instance=usuario,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Usuário atualizado com sucesso.",
            )

            return redirect(
                "usuarios:usuario_detalhar",
                pk=usuario.pk,
            )
    else:
        form = UsuarioUpdateForm(instance=usuario)

    return render(
        request,
        "form.html",
        {
            "titulo": "Editar usuário",
            "form": form,
            "cancelar_url": reverse(
                "usuarios:usuario_detalhar",
                args=[usuario.pk],
            ),
        },
    )


# EXCLUI UM USUARIO E SEUS DADOS
@login_required
def usuario_excluir(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario.pk != request.user.pk and not request.user.is_staff:
        raise PermissionDenied
    excluindo_propria_conta = usuario.pk == request.user.pk

    if request.method == "POST":
        # ORDEM NECESSARIA PARA EVITAR CONFLITOS COM CAMPOS PROTECT
        with transaction.atomic():
            Movimentacao.objects.filter(usuario=usuario).delete()

            CompromissoFinanceiro.objects.filter(usuario=usuario).delete()

            Conta.objects.filter(usuario=usuario).delete()

            Categoria.objects.filter(usuario=usuario).delete()

            usuario.delete()

        messages.success(
            request,
            "Usuário e seus dados foram excluídos.",
        )

        if excluindo_propria_conta:
            logout(request)
            return redirect("usuarios:login")

        return redirect("usuarios:usuario_listar")

    return render(
        request,
        "confirmar_exclusao.html",
        {
            "titulo": "Excluir usuário",
            "objeto": usuario,
            "aviso": (
                "As contas, categorias, compromissos e "
                "movimentações deste usuário também serão excluídos."
            ),
            "cancelar_url": reverse(
                "usuarios:usuario_detalhar",
                args=[usuario.pk],
            ),
        },
    )

@login_required
def perfil(request):
    usuario = usuario_logado(request)

    if usuario is None:
        messages.info(
            request,
            "Administradores não possuem perfil financeiro.",
        )
        return redirect("admin:index")

    return redirect(
        "usuarios:usuario_detalhar",
        pk=usuario.pk,
    )