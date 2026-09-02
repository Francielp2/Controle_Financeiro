from django.urls import path

from financeiro import views


app_name = "financeiro"


# ROTAS DO APLICATIVO FINANCEIRO
urlpatterns = [
    path(
        "",
        views.inicio,
        name="inicio",
    ),

    # ROTAS DE CONTAS
    path(
        "contas/",
        views.conta_listar,
        name="conta_listar",
    ),
    path(
        "contas/criar/",
        views.conta_criar,
        name="conta_criar",
    ),
    path(
        "contas/<int:pk>/",
        views.conta_detalhar,
        name="conta_detalhar",
    ),
    path(
        "contas/<int:pk>/editar/",
        views.conta_editar,
        name="conta_editar",
    ),
    path(
        "contas/<int:pk>/excluir/",
        views.conta_excluir,
        name="conta_excluir",
    ),

    # ROTAS DE CATEGORIAS
    path(
        "categorias/",
        views.categoria_listar,
        name="categoria_listar",
    ),
    path(
        "categorias/criar/",
        views.categoria_criar,
        name="categoria_criar",
    ),
    path(
        "categorias/<int:pk>/",
        views.categoria_detalhar,
        name="categoria_detalhar",
    ),
    path(
        "categorias/<int:pk>/editar/",
        views.categoria_editar,
        name="categoria_editar",
    ),
    path(
        "categorias/<int:pk>/excluir/",
        views.categoria_excluir,
        name="categoria_excluir",
    ),

    # ROTAS DE COMPROMISSOS
    path(
        "compromissos/",
        views.compromisso_listar,
        name="compromisso_listar",
    ),
    path(
        "compromissos/criar/",
        views.compromisso_criar,
        name="compromisso_criar",
    ),
    path(
        "compromissos/<int:pk>/",
        views.compromisso_detalhar,
        name="compromisso_detalhar",
    ),
    path(
        "compromissos/<int:pk>/editar/",
        views.compromisso_editar,
        name="compromisso_editar",
    ),
    path(
        "compromissos/<int:pk>/excluir/",
        views.compromisso_excluir,
        name="compromisso_excluir",
    ),

    # ROTAS DE MOVIMENTACOES
    path(
        "movimentacoes/",
        views.movimentacao_listar,
        name="movimentacao_listar",
    ),
    path(
        "movimentacoes/criar/",
        views.movimentacao_criar,
        name="movimentacao_criar",
    ),
    path(
        "movimentacoes/<int:pk>/",
        views.movimentacao_detalhar,
        name="movimentacao_detalhar",
    ),
    path(
        "movimentacoes/<int:pk>/editar/",
        views.movimentacao_editar,
        name="movimentacao_editar",
    ),
    path(
        "movimentacoes/<int:pk>/excluir/",
        views.movimentacao_excluir,
        name="movimentacao_excluir",
    ),
]
