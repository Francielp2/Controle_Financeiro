from django import forms

from .models import (
    Conta,
    Categoria,
    CompromissoFinanceiro,
    Movimentacao,
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

# FORMULARIO DE COMPROMISSOS FINANCEIROS
class CompromissoFinanceiroForm(forms.ModelForm):
    # CONFIGURACAO DO MODELO COMPROMISSO FINANCEIRO
    class Meta:
        model = CompromissoFinanceiro
        fields = (
            "usuario",
            "conta",
            "categoria",
            "titulo",
            "descricao",
            "pessoa",
            "tipo",
            "valor_total",
            "valor_pago_recebido",
            "data_vencimento",
        )

        widgets = {
            "data_vencimento": forms.DateInput(attrs={"type": "date"}),
        }


# FORMULARIO DE MOVIMENTACOES
class MovimentacaoForm(forms.ModelForm):
    # CONFIGURACAO DO MODELO MOVIMENTACAO
    class Meta:
        model = Movimentacao
        fields = (
            "usuario",
            "tipo",
            "valor",
            "descricao",
            "data",
            "hora",
            "conta_origem",
            "conta_destino",
            "categoria",
            "compromisso_financeiro",
        )

        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "hora": forms.TimeInput(attrs={"type": "time"}),
        }