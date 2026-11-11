from django import forms
from django.contrib.auth.forms import (
    UserChangeForm,
    UserCreationForm,
    AuthenticationForm,
)

from .models import Usuario


class UsuarioMascaraFormMixin(forms.Form):
    cpf = forms.CharField(
        max_length=14,
        widget=forms.TextInput(
            attrs={
                "placeholder": "000.000.000-00",
                "data-mask": "cpf",
            }
        ),
    )

    telefone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(
            attrs={
                "placeholder": "(00) 00000-0000",
                "data-mask": "telefone",
            }
        ),
    )

    def clean_cpf(self):
        cpf = self.cleaned_data["cpf"]
        return "".join(caractere for caractere in cpf if caractere.isdigit())

    def clean_telefone(self):
        telefone = self.cleaned_data["telefone"]
        return "".join(
            caractere for caractere in telefone if caractere.isdigit()
        )


# FORMULARIO DE CRIACAO DE USUARIOS
class UsuarioCreationForm(UsuarioMascaraFormMixin, UserCreationForm):
    # CONFIGURACAO DO MODEl USUARIO
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
class UsuarioUpdateForm(UsuarioMascaraFormMixin, forms.ModelForm):
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


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"

    def clean_username(self):
        email = self.cleaned_data["username"]
        return email.strip().lower()


class UsuarioStaffCreationForm(UsuarioMascaraFormMixin, UserCreationForm):

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = (UsuarioCreationForm.Meta.fields + ("is_staff",))
