from django.urls import path

from . import views


app_name = "chat_ia"

urlpatterns = [
    path("", views.pagina_chat, name="pagina"),
    path("conversar/", views.conversar, name="conversar"),
]
