from django.contrib import admin, messages
from .models import (
    Conta,
    Categoria,
    CompromissoFinanceiro,
    Movimentacao,
)
from django.db import transaction, OperationalError
from django.shortcuts import redirect
from .forms import VinculosAtivosAdminForm
from django.core.exceptions import ValidationError
from .concorrencia import (
    MENSAGEM_CONCORRENCIA,
    eh_erro_de_concorrencia,
)


class ConcorrenciaAdminMixin:
    """Apresenta falhas de concorrência após desfazer a operação."""

    def _executar_com_tratamento(self, request, executar):
        if request.method != "POST":
            return executar()

        try:
            # PROTEÇÃO CONTRA CONCORRÊNCIA:
            # envolve a operação inteira do admin, incluindo ações em lote.
            # O erro é tratado fora do atomic, depois do rollback.
            with transaction.atomic():
                return executar()

        except ValidationError as erro:
            self.message_user(
                request,
                " ".join(erro.messages),
                level=messages.ERROR,
            )

        except OperationalError as erro:
            # PROTEÇÃO CONTRA CONCORRÊNCIA:
            # não esconde problemas de banco que não sejam disputas conhecidas.
            if not eh_erro_de_concorrencia(erro):
                raise

            self.message_user(
                request,
                MENSAGEM_CONCORRENCIA,
                level=messages.ERROR,
            )

        # Redireciona para GET, evitando reenviar automaticamente o POST.
        return redirect(request.path)

    def changeform_view(self, request, *args, **kwargs):
        # Abrange criação e edição no admin.
        executar = super().changeform_view

        return self._executar_com_tratamento(
            request,
            lambda: executar(request, *args, **kwargs),
        )

    def delete_view(self, request, *args, **kwargs):
        # Abrange a confirmação de exclusão individual.
        executar = super().delete_view

        return self._executar_com_tratamento(
            request,
            lambda: executar(request, *args, **kwargs),
        )

    def changelist_view(self, request, *args, **kwargs):
        # Abrange ações da listagem, incluindo exclusão em lote.
        executar = super().changelist_view

        return self._executar_com_tratamento(
            request,
            lambda: executar(request, *args, **kwargs),
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

    def get_readonly_fields(self, request, obj=None):
        campos = tuple(super().get_readonly_fields(request, obj))

        if obj is not None:
            possui_movimentacoes = obj.possui_movimentacoes()

            if possui_movimentacoes or obj.compromissos.exists():
                campos += ("usuario",)

            if possui_movimentacoes:
                campos += ("saldo_inicial",)

        return campos


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

    def get_readonly_fields(self, request, obj=None):
        campos = tuple(super().get_readonly_fields(request, obj))

        if obj is not None and obj.possui_vinculos():
            campos += ("usuario", "tipo")

        return campos


@admin.register(CompromissoFinanceiro)
class CompromissoFinanceiroAdmin(ConcorrenciaAdminMixin, admin.ModelAdmin):
    list_display = (
        "titulo",
        "usuario",
        "tipo",
        "valor_total",
        "valor_pago_recebido",
        "mostrar_valor_restante",
        "data_vencimento",
        "mostrar_situacao"
    )

    list_filter = (
        "tipo",
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
        "mostrar_situacao",
        "mostrar_valor_restante",
        "valor_pago_recebido",
    )

    list_select_related = (
        "usuario",
        "conta",
        "categoria",
    )

    date_hierarchy = "data_vencimento"

    exclude = ("status",)

    form = VinculosAtivosAdminForm

    @admin.display(description="Valor restante")
    def mostrar_valor_restante(self, compromisso):
        return compromisso.valor_restante()

    @admin.display(description="Situação")
    def mostrar_situacao(self, compromisso):
        return compromisso.situacao_display

    def get_readonly_fields(self, request, obj=None):
        campos = tuple(super().get_readonly_fields(request, obj))

        if obj is not None and obj.movimentacoes.exists():
            campos += (
                "usuario",
                "tipo",
                "conta",
                "categoria",
                "valor_pago_recebido_inicial",
            )

        return campos

        # PROTEÇÃO CONTRA CONCORRÊNCIA:
    # prepara os bloqueios de todo o lote antes de excluir compromissos.
    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            compromisso_ids = list(
                queryset.values_list("pk", flat=True)
            )

            # PROTEÇÃO CONTRA CONCORRÊNCIA:
            # segue a ordem usada nos outros fluxos:
            # movimentações por ID, depois compromissos por ID.
            movimentacoes = list(
                Movimentacao.objects
                .filter(compromisso_financeiro_id__in=compromisso_ids)
                .order_by("pk")
                .select_for_update()
            )

            movimentacao_ids = {
                movimentacao.pk
                for movimentacao in movimentacoes
            }

            compromissos = list(
                CompromissoFinanceiro.objects
                .filter(pk__in=compromisso_ids)
                .order_by("pk")
                .select_for_update()
            )

            # PROTEÇÃO CONTRA CONCORRÊNCIA:
            # interrompe se surgiram vínculos enquanto os bloqueios
            # estavam sendo adquiridos, evitando excluir sem protegê-los.
            novos_vinculos = (
                Movimentacao.objects
                .filter(compromisso_financeiro_id__in=compromisso_ids)
                .exclude(pk__in=movimentacao_ids)
                .exists()
            )

            if novos_vinculos:
                raise ValidationError(
                    "As movimentações dos compromissos foram alteradas "
                    "durante a operação. Atualize a página e tente novamente."
                )

            for compromisso in compromissos:
                compromisso.delete()


@admin.register(Movimentacao)
class MovimentacaoAdmin(ConcorrenciaAdminMixin,  admin.ModelAdmin):
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

    form = VinculosAtivosAdminForm

    # PROTEÇÃO CONTRA CONCORRÊNCIA: bloqueia o lote antes das exclusões.
    # Primeiro movimentações por ID, depois compromissos por ID.
    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            # Primeiro bloqueia todas as movimentacoes em ordem fixa.
            # Limpa select_related para nao bloquear contas e categorias.
            movimentacoes = list(
                queryset
                .select_related(None)
                .order_by("pk")
                .select_for_update()
            )

            compromisso_ids = {
                movimentacao.compromisso_financeiro_id
                for movimentacao in movimentacoes
                if movimentacao.compromisso_financeiro_id is not None
            }

            # Depois bloqueia todos os compromissos envolvidos.
            # list() executa a consulta e efetiva os bloqueios.
            list(
                CompromissoFinanceiro.objects
                .filter(pk__in=compromisso_ids)
                .order_by("pk")
                .select_for_update()
            )

            # Reutiliza a exclusao individual e seu recalculo.
            for movimentacao in movimentacoes:
                movimentacao.delete()
