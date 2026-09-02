from django.contrib import admin
from django.urls import include, path


# ROTAS PRINCIPAIS DO PROJETO
urlpatterns = [
    path("admin/", admin.site.urls),
    path("usuarios/", include("usuarios.urls")),
    path("", include("financeiro.urls")),
]