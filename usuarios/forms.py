from django import forms
from django.contrib.auth.forms import (
    UserChangeForm,
    UserCreationForm,
)

from .models import Usuario


# FORMULARIO DE CRIACAO DE USUARIOS
class UsuarioCreationForm(UserCreationForm):
    # CONFIGURACAO DO MODELO USUARIO
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = (
            "email",
            "first_name",
            "last_name",
            "cpf",
            "rg",
            "telefone",
        )


# FORMULARIO DE ALTERACAO DE USUARIOS NO ADMIN
class UsuarioChangeForm(UserChangeForm):
    """
    Formulário utilizado pelo Django Admin.
    """

    # CONFIGURACAO DO MODELO USUARIO
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = "__all__"


# FORMULARIO DE EDICAO DE USUARIOS NO CRUD
class UsuarioUpdateForm(forms.ModelForm):
    """
    Formulário usado no CRUD comum.
    Não altera a senha.
    """

    # CONFIGURACAO DO MODELO USUARIO
    class Meta:
        model = Usuario
        fields = (
            "email",
            "first_name",
            "last_name",
            "cpf",
            "rg",
            "telefone",
        )