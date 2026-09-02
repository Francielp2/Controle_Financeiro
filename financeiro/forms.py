from django import forms

from .models import (
    Conta,
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