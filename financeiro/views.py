from django.contrib import messages
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse

from .forms import (
    ContaForm,
)
from .models import (
    Categoria,
    CompromissoFinanceiro,
    Conta,
    Movimentacao,
)


# VIEW DA PAGINA INICIAL
def inicio(request):
    contexto = {
        "quantidade_contas": Conta.objects.count(),
        "quantidade_categorias": Categoria.objects.count(),
        "quantidade_compromissos": CompromissoFinanceiro.objects.count(),
        "quantidade_movimentacoes": Movimentacao.objects.count(),
    }

    return render(
        request,
        "financeiro/inicio.html",
        contexto,
    )


# -------------------------
# CRUD DE CONTAS
# -------------------------


# LISTA AS CONTAS CADASTRADAS
def conta_listar(request):
    contas = Conta.objects.select_related("usuario").order_by(
        "usuario__email",
        "nome",
    )

    return render(
        request,
        "financeiro/contas/listar.html",
        {"contas": contas},
    )


# DETALHA UMA CONTA
def conta_detalhar(request, pk):
    conta = get_object_or_404(
        Conta.objects.select_related("usuario"),
        pk=pk,
    )

    movimentacoes = Movimentacao.objects.filter(
        Q(conta_origem=conta)
        | Q(conta_destino=conta)
    ).select_related(
        "conta_origem",
        "conta_destino",
        "categoria",
    ).order_by("-data", "-hora")

    return render(
        request,
        "financeiro/contas/detalhar.html",
        {
            "conta": conta,
            "movimentacoes": movimentacoes,
        },
    )


# CRIA UMA CONTA
def conta_criar(request):
    if request.method == "POST":
        form = ContaForm(request.POST)

        if form.is_valid():
            conta = form.save()

            messages.success(
                request,
                "Conta cadastrada com sucesso.",
            )

            return redirect(
                "financeiro:conta_detalhar",
                pk=conta.pk,
            )
    else:
        form = ContaForm()

    return render(
        request,
        "form.html",
        {
            "titulo": "Cadastrar conta",
            "form": form,
            "cancelar_url": reverse("financeiro:conta_listar"),
        },
    )


# EDITA UMA CONTA
def conta_editar(request, pk):
    conta = get_object_or_404(Conta, pk=pk)

    if request.method == "POST":
        form = ContaForm(
            request.POST,
            instance=conta,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Conta atualizada com sucesso.",
            )

            return redirect(
                "financeiro:conta_detalhar",
                pk=conta.pk,
            )
    else:
        form = ContaForm(instance=conta)

    return render(
        request,
        "form.html",
        {
            "titulo": "Editar conta",
            "form": form,
            "cancelar_url": reverse(
                "financeiro:conta_detalhar",
                args=[conta.pk],
            ),
        },
    )


# EXCLUI UMA CONTA
def conta_excluir(request, pk):
    conta = get_object_or_404(Conta, pk=pk)

    if request.method == "POST":
        try:
            conta.delete()

            messages.success(
                request,
                "Conta excluída com sucesso.",
            )

            return redirect("financeiro:conta_listar")

        except ProtectedError:
            messages.error(
                request,
                "A conta não pode ser excluída porque possui "
                "movimentações ou compromissos relacionados.",
            )

            return redirect(
                "financeiro:conta_detalhar",
                pk=conta.pk,
            )

    return render(
        request,
        "confirmar_exclusao.html",
        {
            "titulo": "Excluir conta",
            "objeto": conta,
            "cancelar_url": reverse(
                "financeiro:conta_detalhar",
                args=[conta.pk],
            ),
        },
    )