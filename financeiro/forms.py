from django import forms
from django.db.models import Q

from .models import (
    Conta,
    Categoria,
    CompromissoFinanceiro,
    Movimentacao,
)
import json


def filtrar_vinculos_ativos(form):
    instance = form.instance

    anterior = (
        type(instance).objects.filter(pk=instance.pk).first()
        if instance.pk
        else None
    )

    for nome in ("conta", "conta_origem", "conta_destino", "categoria"):
        if nome not in form.fields:
            continue

        anterior_id = (
            getattr(anterior, f"{nome}_id", None)
            if anterior is not None
            else None
        )

        campo = form.fields[nome]
        campo.queryset = campo.queryset.filter(
            Q(ativa=True) | Q(pk=anterior_id)
        )

        # FORMULARIO DE CONTAS

# DISPONIBILIZA A CATEGORIA DOS COMPROMISSOS PERMITIDOS NO FORMULÁRIO


def configurar_categoria_do_compromisso(form):
    if (
        "compromisso_financeiro" not in form.fields
        or "categoria" not in form.fields
    ):
        return

    campo = form.fields["compromisso_financeiro"]

    categorias = {
        str(pk): str(categoria_id) if categoria_id is not None else ""
        for pk, categoria_id in campo.queryset.values_list(
            "pk",
            "categoria_id",
        )
    }

    # No admin, o select pode estar dentro de um widget com botoes relacionados.
    widget = getattr(campo.widget, "widget", campo.widget)

    widget.attrs["data-categorias-compromissos"] = json.dumps(categorias)


class ContaForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk and self.instance.possui_movimentacoes():
            self.fields["saldo_inicial"].disabled = True
            self.fields["saldo_inicial"].help_text = (
                "O saldo inicial não pode ser alterado porque existem movimentações vinculadas à conta. "
            )
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.possui_vinculos():
            self.fields["tipo"].disabled = True
            self.fields["tipo"].help_text = (
                "O tipo não pode ser alterado porque existem movimentações ou compromissos vinculados. "
            )


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

            self.fields["conta"].queryset = contas
            self.fields["categoria"].queryset = categorias

        if self.instance.pk and self.instance.movimentacoes.exists():
            campos_bloqueados = (
                "tipo",
                "conta",
                "categoria",
                "valor_pago_recebido_inicial",
            )

            for campo in campos_bloqueados:
                self.fields[campo].disabled = True
                self.fields[campo].help_text = (
                    "Este campo não pode ser alterado porque existem movimentações vinculadas ao compromisso"
                )

        filtrar_vinculos_ativos(self)
        configurar_categoria_do_compromisso(self)

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

            self.fields["conta_origem"].queryset = contas
            self.fields["conta_destino"].queryset = contas
            self.fields["categoria"].queryset = categorias
            self.fields["compromisso_financeiro"].queryset = compromissos

        filtrar_vinculos_ativos(self)
        configurar_categoria_do_compromisso(self)

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
            "data": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
            "hora": forms.TimeInput(attrs={"type": "time"}),
        }

    class Media:
        js = ("financeiro/js/categoria_compromisso.js",)

# FORMULARIO BASE DO ADMIN PARA FILTRAR VINCULOS INATIVOS


class VinculosAtivosAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        filtrar_vinculos_ativos(self)
        configurar_categoria_do_compromisso(self)

    class Media:
        js = ("financeiro/js/categoria_compromisso.js",)
