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
]
