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
            "nome",
            "descricao",
            "tipo",
            "ativa",
        )

# FORMULARIO DE COMPROMISSOS FINANCEIROS


class CompromissoFinanceiroForm(forms.ModelForm):
    # CONFIGURACAO DO MODELO COMPROMISSO FINANCEIRO

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.usuario_id:
            contas = Conta.objects.filter(usuario_id=self.instance.usuario_id)
            categorias = Categoria.objects.filter(
                usuario_id=self.instance.usuario_id)

            if not self.instance.pk:
                contas = contas.filter(ativa=True)
                categorias = categorias.filter(ativa=True)

            self.fields["conta"].queryset = contas
            self.fields["categoria"].queryset = categorias

        if self.instance.pk and self.instance.movimentacoes.exists():
            self.fields["valor_pago_recebido_inicial"].disabled = True

    class Meta:
        model = CompromissoFinanceiro
        fields = (
            "conta",
            "categoria",
            "titulo",
            "descricao",
            "pessoa",
            "tipo",
            "valor_total",
            "valor_pago_recebido_inicial",
            "data_vencimento",
        )

        widgets = {
            "data_vencimento": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
        }


# FORMULARIO DE MOVIMENTACOES
class MovimentacaoForm(forms.ModelForm):
    # CONFIGURACAO DO MODELO MOVIMENTACAO

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.usuario_id:
            usuario_id = self.instance.usuario_id

            contas = Conta.objects.filter(usuario_id=usuario_id)
            categorias = Categoria.objects.filter(usuario_id=usuario_id)
            compromissos = CompromissoFinanceiro.objects.filter(
                usuario_id=usuario_id)

            if not self.instance.pk:
                contas = contas.filter(ativa=True)
                categorias = categorias.filter(ativa=True)

            self.fields["conta_origem"].queryset = contas
            self.fields["conta_destino"].queryset = contas
            self.fields["categoria"].queryset = categorias
            self.fields["compromisso_financeiro"].queryset = compromissos

    class Meta:
        model = Movimentacao
        fields = (
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
