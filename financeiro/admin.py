from django.contrib import admin

from .models import (
    Conta,
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