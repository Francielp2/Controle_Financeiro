from django.contrib import messages
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from .forms import (
    CategoriaForm,
    CompromissoFinanceiroForm,
    ContaForm,
    MovimentacaoForm,
)
from .models import (
    Categoria,
    CompromissoFinanceiro,
    Conta,
    Movimentacao,
)
from .decorators import perfil_obrigatorio


# VIEW DA PAGINA INICIAL
@login_required
@perfil_obrigatorio
def inicio(request):
    contexto = {
        "quantidade_contas": request.usuario.contas.count(),
        "quantidade_categorias": request.usuario.categorias.count(),
        "quantidade_compromissos": request.usuario.compromissos.count(),
        "quantidade_movimentacoes": request.usuario.movimentacoes.count(),
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
@login_required
@perfil_obrigatorio
def conta_listar(request):
    contas = Conta.objects.filter(usuario=request.usuario).order_by("nome")

    return render(
        request,
        "financeiro/contas/listar.html",
        {"contas": contas},
    )


# DETALHA UMA CONTA
@login_required
@perfil_obrigatorio
def conta_detalhar(request, pk):
    conta = get_object_or_404(
        Conta.objects.select_related("usuario"),
        pk=pk,
        usuario=request.usuario
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
@login_required
@perfil_obrigatorio
def conta_criar(request):
    if request.method == "POST":

        form = ContaForm(request.POST, instance=Conta(usuario=request.usuario))

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
        form = ContaForm(instance=Conta(usuario=request.usuario))

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
@login_required
@perfil_obrigatorio
def conta_editar(request, pk):
    conta = get_object_or_404(Conta, pk=pk, usuario=request.usuario)

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
@login_required
@perfil_obrigatorio
def conta_excluir(request, pk):
    conta = get_object_or_404(Conta, pk=pk, usuario=request.usuario)

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

# -------------------------
# CRUD DE CATEGORIAS
# -------------------------


# LISTA AS CATEGORIAS CADASTRADAS
@login_required
@perfil_obrigatorio
def categoria_listar(request):
    categorias = Categoria.objects.filter(
        usuario=request.usuario).order_by("nome")

    return render(
        request,
        "financeiro/categorias/listar.html",
        {"categorias": categorias},
    )


# DETALHA UMA CATEGORIA
@login_required
@perfil_obrigatorio
def categoria_detalhar(request, pk):
    categoria = get_object_or_404(
        Categoria.objects.select_related("usuario"),
        pk=pk,
        usuario=request.usuario,
    )

    return render(
        request,
        "financeiro/categorias/detalhar.html",
        {
            "categoria": categoria,
            "movimentacoes": categoria.movimentacoes.all().order_by(
                "-data",
                "-hora",
            ),
            "compromissos": categoria.compromissos.all().order_by(
                "-data_vencimento"
            ),
        },
    )


# CRIA UMA CATEGORIA
@login_required
@perfil_obrigatorio
def categoria_criar(request):
    if request.method == "POST":
        form = CategoriaForm(
            request.POST, instance=Categoria(usuario=request.usuario))

        if form.is_valid():
            categoria = form.save()

            messages.success(
                request,
                "Categoria cadastrada com sucesso.",
            )

            return redirect(
                "financeiro:categoria_detalhar",
                pk=categoria.pk,
            )
    else:
        form = CategoriaForm(instance=Categoria(usuario=request.usuario))

    return render(
        request,
        "form.html",
        {
            "titulo": "Cadastrar categoria",
            "form": form,
            "cancelar_url": reverse("financeiro:categoria_listar"),
        },
    )


# EDITA UMA CATEGORIA
@login_required
@perfil_obrigatorio
def categoria_editar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk, usuario=request.usuario)

    if request.method == "POST":
        form = CategoriaForm(
            request.POST,
            instance=categoria,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Categoria atualizada com sucesso.",
            )

            return redirect(
                "financeiro:categoria_detalhar",
                pk=categoria.pk,
            )
    else:
        form = CategoriaForm(instance=categoria)

    return render(
        request,
        "form.html",
        {
            "titulo": "Editar categoria",
            "form": form,
            "cancelar_url": reverse(
                "financeiro:categoria_detalhar",
                args=[categoria.pk],
            ),
        },
    )


# EXCLUI UMA CATEGORIA
@login_required
@perfil_obrigatorio
def categoria_excluir(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk, usuario=request.usuario)

    if request.method == "POST":
        try:
            categoria.delete()

            messages.success(
                request,
                "Categoria excluída com sucesso.",
            )

            return redirect("financeiro:categoria_listar")

        except ProtectedError:
            messages.error(
                request,
                "A categoria não pode ser excluída porque "
                "possui registros relacionados.",
            )

            return redirect(
                "financeiro:categoria_detalhar",
                pk=categoria.pk,
            )

    return render(
        request,
        "confirmar_exclusao.html",
        {
            "titulo": "Excluir categoria",
            "objeto": categoria,
            "cancelar_url": reverse(
                "financeiro:categoria_detalhar",
                args=[categoria.pk],
            ),
        },
    )

# -------------------------
# CRUD DE COMPROMISSOS
# -------------------------


# LISTA OS COMPROMISSOS FINANCEIROS
def compromisso_listar(request):
    compromissos = CompromissoFinanceiro.objects.select_related(
        "conta",
        "categoria",
    ).order_by("-data_vencimento").filter(usuario=request.usuario)

    return render(
        request,
        "financeiro/compromissos/listar.html",
        {"compromissos": compromissos},
    )


# DETALHA UM COMPROMISSO FINANCEIRO
def compromisso_detalhar(request, pk):
    compromisso = get_object_or_404(
        CompromissoFinanceiro.objects.select_related(
            "usuario",
            "conta",
            "categoria",
        ),
        pk=pk,
        usuario=request.usuario,
    )

    return render(
        request,
        "financeiro/compromissos/detalhar.html",
        {
            "compromisso": compromisso,
            "movimentacoes": compromisso.movimentacoes.all().order_by(
                "-data",
                "-hora",
            ),
        },
    )


# CRIA UM COMPROMISSO FINANCEIRO
def compromisso_criar(request):
    if request.method == "POST":
        form = CompromissoFinanceiroForm(
            request.POST, instance=CompromissoFinanceiro(usuario=request.usuario))

        if form.is_valid():
            compromisso = form.save()

            messages.success(
                request,
                "Compromisso cadastrado com sucesso.",
            )

            return redirect(
                "financeiro:compromisso_detalhar",
                pk=compromisso.pk,
            )
    else:
        form = CompromissoFinanceiroForm(
            instance=CompromissoFinanceiro(usuario=request.usuario))

    return render(
        request,
        "form.html",
        {
            "titulo": "Cadastrar compromisso",
            "form": form,
            "cancelar_url": reverse("financeiro:compromisso_listar"),
        },
    )


# EDITA UM COMPROMISSO FINANCEIRO
def compromisso_editar(request, pk):
    compromisso = get_object_or_404(
        CompromissoFinanceiro,
        pk=pk,
        usuario=request.usuario,
    )

    if request.method == "POST":
        form = CompromissoFinanceiroForm(
            request.POST,
            instance=compromisso,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Compromisso atualizado com sucesso.",
            )

            return redirect(
                "financeiro:compromisso_detalhar",
                pk=compromisso.pk,
            )
    else:
        form = CompromissoFinanceiroForm(instance=compromisso)

    return render(
        request,
        "form.html",
        {
            "titulo": "Editar compromisso",
            "form": form,
            "cancelar_url": reverse(
                "financeiro:compromisso_detalhar",
                args=[compromisso.pk],
            ),
        },
    )


# EXCLUI UM COMPROMISSO FINANCEIRO
def compromisso_excluir(request, pk):
    compromisso = get_object_or_404(
        CompromissoFinanceiro,
        pk=pk,
        usuario=request.usuario
    )

    if request.method == "POST":
        compromisso.delete()

        messages.success(
            request,
            "Compromisso excluído com sucesso.",
        )

        return redirect("financeiro:compromisso_listar")

    return render(
        request,
        "confirmar_exclusao.html",
        {
            "titulo": "Excluir compromisso",
            "objeto": compromisso,
            "cancelar_url": reverse(
                "financeiro:compromisso_detalhar",
                args=[compromisso.pk],
            ),
        },
    )


# -------------------------
# CRUD DE MOVIMENTACOES
# -------------------------


# LISTA AS MOVIMENTACOES
def movimentacao_listar(request):
    movimentacoes = Movimentacao.objects.select_related(
        "conta_origem",
        "conta_destino",
        "categoria",
        "compromisso_financeiro",
    ).order_by("-data", "-hora").filter(usuario=request.usuario)

    return render(
        request,
        "financeiro/movimentacoes/listar.html",
        {"movimentacoes": movimentacoes},
    )


# DETALHA UMA MOVIMENTACAO
def movimentacao_detalhar(request, pk):
    movimentacao = get_object_or_404(
        Movimentacao.objects.select_related(
            "usuario",
            "conta_origem",
            "conta_destino",
            "categoria",
            "compromisso_financeiro",
        ),
        pk=pk,
        usuario=request.usuario,
    )

    return render(
        request,
        "financeiro/movimentacoes/detalhar.html",
        {"movimentacao": movimentacao},
    )


# CRIA UMA MOVIMENTACAO
def movimentacao_criar(request):
    if request.method == "POST":
        form = MovimentacaoForm(
            request.POST, instance=Movimentacao(usuario=request.usuario))

        if form.is_valid():
            movimentacao = form.save()

            messages.success(
                request,
                "Movimentação cadastrada com sucesso.",
            )

            return redirect(
                "financeiro:movimentacao_detalhar",
                pk=movimentacao.pk,
            )
    else:
        form = MovimentacaoForm(instance=Movimentacao(usuario=request.usuario))

    return render(
        request,
        "form.html",
        {
            "titulo": "Cadastrar movimentação",
            "form": form,
            "cancelar_url": reverse("financeiro:movimentacao_listar"),
        },
    )


# EDITA UMA MOVIMENTACAO
def movimentacao_editar(request, pk):
    movimentacao = get_object_or_404(
        Movimentacao,
        pk=pk,
        usuario=request.usuario,
    )

    if request.method == "POST":
        form = MovimentacaoForm(
            request.POST,
            instance=movimentacao,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Movimentação atualizada com sucesso.",
            )

            return redirect(
                "financeiro:movimentacao_detalhar",
                pk=movimentacao.pk,
            )
    else:
        form = MovimentacaoForm(instance=movimentacao)

    return render(
        request,
        "form.html",
        {
            "titulo": "Editar movimentação",
            "form": form,
            "cancelar_url": reverse(
                "financeiro:movimentacao_detalhar",
                args=[movimentacao.pk],
            ),
        },
    )


# EXCLUI UMA MOVIMENTACAO
def movimentacao_excluir(request, pk):
    movimentacao = get_object_or_404(
        Movimentacao,
        pk=pk,
        usuario=request.usuario,
    )

    if request.method == "POST":
        movimentacao.delete()

        messages.success(
            request,
            "Movimentação excluída com sucesso.",
        )

        return redirect("financeiro:movimentacao_listar")

    return render(
        request,
        "confirmar_exclusao.html",
        {
            "titulo": "Excluir movimentação",
            "objeto": movimentacao,
            "cancelar_url": reverse(
                "financeiro:movimentacao_detalhar",
                args=[movimentacao.pk],
            ),
        },
    )