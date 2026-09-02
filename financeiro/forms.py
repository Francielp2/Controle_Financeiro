from django import forms

from .models import (
    Conta,
    Categoria,
)


# FORMULARIO DE CONTAS
class ContaForm(forms.ModelForm):
    # CONFIGURACAO DO MODELO CONTA
    class Meta:
        model = Conta
        fields = (
            "usuario",
            "nome",
            "tipo",
            "saldo_inicial",
            "ativa",
        )

# FORMULARIO DE CATEGORIAS


class CategoriaForm(forms.ModelForm):
    # CONFIGURACAO DO MODELO CATEGORIA
    class Meta:
        model = Categoria
        fields = (
            "usuario",
            "nome",
            "descricao",
            "tipo",
            "ativa",
        )
