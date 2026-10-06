from django.urls import path
from django.contrib.auth import views as auth_views

# importando as views do aplicativo usuarios
from . import views
from .forms import (
    LoginForm,
)


app_name = "usuarios"


# ROTAS DO APLICATIVO USUARIOS
urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="usuarios/login.html",
            authentication_form=LoginForm, redirect_authenticated_user=True,), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.usuario_listar, name="usuario_listar"),
    path("criar/", views.usuario_criar, name="usuario_criar"),
    path("<int:pk>/", views.usuario_detalhar, name="usuario_detalhar"),
    path("<int:pk>/editar/", views.usuario_editar, name="usuario_editar"),
    path("<int:pk>/excluir/", views.usuario_excluir, name="usuario_excluir"),
]
