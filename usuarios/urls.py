from django.urls import path

from . import views


app_name = "usuarios"


# ROTAS DO APLICATIVO USUARIOS
urlpatterns = [
    path(
        "",
        views.usuario_listar,
        name="usuario_listar",
    ),
    path(
        "criar/",
        views.usuario_criar,
        name="usuario_criar",
    ),
    path(
        "<int:pk>/",
        views.usuario_detalhar,
        name="usuario_detalhar",
    ),
    path(
        "<int:pk>/editar/",
        views.usuario_editar,
        name="usuario_editar",
    ),
    path(
        "<int:pk>/excluir/",
        views.usuario_excluir,
        name="usuario_excluir",
    ),
]