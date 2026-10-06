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

    def _init_(self, *args, **kwargs):
        super()._init_(*args, **kwargs)

        if self.instance.usuario_id:
            self.fields["conta"].queryset = Conta.objects.filter(
                usuario_id=self.instance.usuario_id
            )
            self.fields["categoria"].queryset = Categoria.objects.filter(
                usuario_id=self.instance.usuario_id
            )

    # CONFIGURACAO DO MODELO COMPROMISSO FINANCEIRO
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
            "valor_pago_recebido",
            "data_vencimento",
        )

        widgets = {
            "data_vencimento": forms.DateInput(attrs={"type": "date"}),
        }


# FORMULARIO DE MOVIMENTACOES
class MovimentacaoForm(forms.ModelForm):
    # CONFIGURACAO DO MODELO MOVIMENTACAO

    def _init_(self, *args, **kwargs):
        super()._init_(*args, **kwargs)

        if self.instance.usuario_id:
            usuario_id = self.instance.usuario_id

            self.fields["conta_origem"].queryset = Conta.objects.filter(
                usuario_id=usuario_id
            )

            self.fields["conta_destino"].queryset = Conta.objects.filter(
                usuario_id=usuario_id
            )

            self.fields["categoria"].queryset = Categoria.objects.filter(
                usuario_id=usuario_id
            )

            self.fields["compromisso_financeiro"].queryset = (
                CompromissoFinanceiro.objects.filter(
                    usuario_id=usuario_id
                )
            )

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
