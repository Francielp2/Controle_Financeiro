from django.urls import path

from . import views


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
    ) 
]