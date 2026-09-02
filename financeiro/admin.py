from django.contrib import admin

from .models import (
    Conta,
    Categoria,
    CompromissoFinanceiro,
    Movimentacao,
)


# ADMINISTRACAO DE CONTAS
@admin.register(Conta)
class ContaAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "usuario",
        "tipo",
        "saldo_inicial",
        "mostrar_saldo_atual",
        "ativa",
    )

    list_filter = (
        "tipo",
        "ativa",
    )

    search_fields = (
        "nome",
        "usuario__email",
        "usuario__first_name",
        "usuario__last_name",
    )

    readonly_fields = (
        "data_criacao",
        "mostrar_saldo_atual",
    )

    list_select_related = ("usuario",)

    # EXIBE O SALDO ATUAL DA CONTA
    @admin.display(description="Saldo atual")
    def mostrar_saldo_atual(self, conta):
        return conta.saldo_atual

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "usuario",
        "tipo",
        "ativa",
        "data_criacao",
    )

    list_filter = (
        "tipo",
        "ativa",
    )

    search_fields = (
        "nome",
        "descricao",
        "usuario__email",
    )

    readonly_fields = ("data_criacao",)

    list_select_related = ("usuario",)


@admin.register(CompromissoFinanceiro)
class CompromissoFinanceiroAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "usuario",
        "tipo",
        "valor_total",
        "valor_pago_recebido",
        "mostrar_valor_restante",
        "data_vencimento",
        "status",
    )

    list_filter = (
        "tipo",
        "status",
        "data_vencimento",
    )

    search_fields = (
        "titulo",
        "pessoa",
        "descricao",
        "usuario__email",
    )

    readonly_fields = (
        "data_criacao",
        "status",
        "mostrar_valor_restante",
    )

    list_select_related = (
        "usuario",
        "conta",
        "categoria",
    )

    date_hierarchy = "data_vencimento"

    @admin.display(description="Valor restante")
    def mostrar_valor_restante(self, compromisso):
        return compromisso.valor_restante()


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "usuario",
        "tipo",
        "valor",
        "conta_origem",
        "conta_destino",
        "categoria",
        "data",
        "hora",
    )

    list_filter = (
        "tipo",
        "data",
        "categoria",
    )

    search_fields = (
        "descricao",
        "usuario__email",
        "conta_origem__nome",
        "conta_destino__nome",
        "categoria__nome",
    )

    readonly_fields = (
        "criado_em",
        "atualizado_em",
    )

    list_select_related = (
        "usuario",
        "conta_origem",
        "conta_destino",
        "categoria",
        "compromisso_financeiro",
    )

    date_hierarchy = "data"

    ordering = (
        "-data",
        "-hora",
    )