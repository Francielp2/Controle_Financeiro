from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, Sum
from django.db.models.functions import Lower
from django.utils import timezone
from collections import Counter

from usuarios.models import Usuario


def dinheiro(valor):
    return Decimal(str(valor or "0")).quantize(Decimal("0.01"))

# MODELO DE CONTA FINANCEIRA


class Conta(models.Model):
    # TIPOS DE CONTA DISPONIVEIS
    class Tipo(models.TextChoices):
        CORRENTE = "CORRENTE", "Conta corrente"
        CAIXINHA = "CAIXINHA", "Investimento/Caixinha"

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="contas",
    )

    nome = models.CharField(
        max_length=100,
    )

    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
    )

    saldo_inicial = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    ativa = models.BooleanField(
        default=True,
    )

    data_criacao = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                "usuario",
                Lower("nome"),
                name="conta_usuario_nome_unico",
            ),
        ]

    # CALCULA O SALDO ATUAL DA CONTA
    @property
    def saldo_atual(self):
        entradas = (
            self.movimentacoes_destino.aggregate(total=Sum("valor"))["total"]
            or Decimal("0.00")
        )

        saidas = (
            self.movimentacoes_origem.aggregate(total=Sum("valor"))["total"]
            or Decimal("0.00")
        )

        return dinheiro(self.saldo_inicial + entradas - saidas)

    # VERIFICA SE A CONTA POSSUI MOVIMENTACOES
    def possui_movimentacoes(self):
        return (
            self.movimentacoes_origem.exists()
            or self.movimentacoes_destino.exists()
        )

    # Bloqueia Alterações que comprometem os registros vinculados

    def validar_alteracoes_com_vinculos(self):
        if not self.pk:
            return

        conta_anterior = Conta.objects.filter(pk=self.pk).first()

        if conta_anterior is None:
            return

        possui_movimentacoes = self.possui_movimentacoes()

        possui_vinculos = (
            possui_movimentacoes or self.compromissos.exists()
        )

        erros = []

        if (
            possui_vinculos and self.usuario_id != conta_anterior.usuario_id
        ):
            erros.append(
                "O proprietário da conta não pode ser alterado porque existem movimentações ou compromissos vinculados"
            )

        if (
            possui_movimentacoes and self.saldo_inicial != conta_anterior.saldo_inicial
        ):

            erros.append(
                "O saldo inicial não pode ser alterado porque existem movimentações vinculadas à conta"
            )
        if erros:
            raise ValidationError(erros)
    # VALIDA REGRAS DA CONTA

    def clean(self):
        super().clean()

        self.validar_alteracoes_com_vinculos()

        if self.usuario_id and self.nome:
            conta_existente = Conta.objects.filter(
                usuario=self.usuario,
                nome__iexact=self.nome,
            ).exclude(pk=self.pk)

            if conta_existente.exists():
                raise ValidationError(
                    {"nome": "Já existe uma conta com este nome."})

    # SALVA A CONTA APOS VALIDACAO
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    # REPRESENTACAO EM TEXTO DA CONTA
    def __str__(self):
        return self.nome


# MODELO DE CATEGORIA FINANCEIRA
class Categoria(models.Model):
    # TIPOS DE CATEGORIA DISPONIVEIS
    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada"
        SAIDA = "SAIDA", "Saída"

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="categorias",
    )

    nome = models.CharField(
        max_length=100,
    )

    descricao = models.TextField(
        blank=True,
    )

    ativa = models.BooleanField(
        default=True,
    )

    tipo = models.CharField(
        max_length=10,
        choices=Tipo.choices,
    )

    data_criacao = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                "usuario",
                Lower("nome"),
                "tipo",
                name="categoria_usuario_nome_tipo_unico",
            ),
        ]

    #  VERIFICA SE A CATEGORIA POSSUI REGISTROS VINCULADOS

    def possui_vinculos(self):
        if not self.pk:
            return False

        return (
            self.movimentacoes.exists() or self.compromissos.exists()
        )

    # BLOQUEIA ALTERAÇÕES QUE COMPROMETEM OS REGISTROS VINCULADOS
    def validar_alteracoes_com_vinculos(self):
        if not self.possui_vinculos():
            return

        categoria_anterior = Categoria.objects.filter(pk=self.pk).first()

        if categoria_anterior is None:
            return

        erros = []

        if self.usuario_id != categoria_anterior.usuario_id:
            erros.append(
                "O proprietário da categoria não pode ser alterado porque existem movimentações ou compromissos vinculados. "
            )

        if self.tipo != categoria_anterior.tipo:
            erros.append(
                "O tipo da categoria não pode ser alterado porque existem movimentações ou compromissos vinculados. "
            )

        if erros:
            raise ValidationError(erros)

    # VALIDA REGRAS DA CATEGORIA

    def clean(self):
        super().clean()

        self.validar_alteracoes_com_vinculos()

        if self.usuario_id and self.nome and self.tipo:
            categoria_existente = Categoria.objects.filter(
                usuario=self.usuario,
                nome__iexact=self.nome,
                tipo=self.tipo,
            ).exclude(pk=self.pk)

            if categoria_existente.exists():
                raise ValidationError(
                    {"nome": "Esta categoria já está cadastrada."})

    # SALVA A CATEGORIA APOS VALIDACAO
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    # REPRESENTACAO EM TEXTO DA CATEGORIA
    def __str__(self):
        return f"{self.nome} — {self.get_tipo_display()}"


# MODELO DE COMPROMISSO FINANCEIRO
class CompromissoFinanceiro(models.Model):
    # TIPOS DE COMPROMISSO DISPONIVEIS
    class Tipo(models.TextChoices):
        PAGAR = "PAGAR", "A pagar"
        RECEBER = "RECEBER", "A receber"

    # STATUS DO COMPROMISSO
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        PARCIAL = "PARCIAL", "Parcial"
        QUITADO = "QUITADO", "Quitado"
        ATRASADO = "ATRASADO", "Atrasado"

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="compromissos",
    )

    conta = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        related_name="compromissos",
        null=True,
        blank=True,
    )

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="compromissos",
        null=True,
        blank=True,
    )

    titulo = models.CharField(
        max_length=150,
    )

    descricao = models.TextField(
        blank=True,
    )

    pessoa = models.CharField(
        max_length=150,
        blank=True,
    )

    tipo = models.CharField(
        max_length=10,
        choices=Tipo.choices,
    )

    valor_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    valor_pago_recebido_inicial = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Valor pago/recebido antes do cadastro",
        help_text=(
            "Valor já pago ou recebido antes do cadastro desse compromisso. "
            "Não altera o saldo das contas. "
        ),
    )

    valor_pago_recebido = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    data_criacao = models.DateTimeField(
        auto_now_add=True,
    )

    data_vencimento = models.DateField()

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDENTE,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(valor_total__gt=0),
                name="compromisso_valor_total_positivo",
            ),
            models.CheckConstraint(
                condition=Q(valor_pago_recebido__gte=0),
                name="compromisso_valor_pago_recebido_nao_negativo",
            ),
        ]

    # CALCULA O VALOR RESTANTE
    def valor_restante(self):
        restante = self.valor_total - self.valor_pago_recebido
        return max(restante, Decimal("0.00"))

    # Recalcula o acumulado a partir so inicial e das movimentações

    def recalcular_valor_pago(self):
        self.save(update_fields=["valor_pago_recebido",  "status"])

    # VERIFICA SE O COMPROMISSO ESTA QUITADO

    def esta_quitado(self):
        return self.valor_pago_recebido >= self.valor_total

    # VERIFICA SE O COMPROMISSO ESTA VENCIDO
    def esta_vencido(self):
        return (
            self.data_vencimento < timezone.localdate()
            and not self.esta_quitado()
        )

    @property
    def situacao(self):
        if self.esta_quitado():
            return self.Status.QUITADO

        if self.esta_vencido():
            return self.Status.ATRASADO

        if self.valor_pago_recebido > 0:
            return self.Status.PARCIAL

        return self.Status.PENDENTE

    @property
    def situacao_display(self):
        return self.Status(self.situacao).label

    # PERMITE MANTER VINCULOS INATIVOS MAS IMPEDE A CRIAÇÃO DE NOVOS VINCULOS COM CONTAS OU CATEGORIAS INATIVAS

    def validar_registros_ativos(self):
        anterior = (
            CompromissoFinanceiro.objects.filter(
                pk=self.pk).first() if self.pk else None
        )

        erros = {}

        for campo in ("conta", "categoria"):
            registro_id = getattr(self, f"{campo}_id")

            if registro_id is None:
                continue

            anterior_id = (
                getattr(
                    anterior, f"{campo}_id") if anterior is not None else None
            )

            if registro_id == anterior_id:
                continue

            if not getattr(self, campo).ativa:
                erros[campo] = (
                    "Não é possível selecionar um registro inativo. Só é possível manter registros inativos já vinculados."
                )
        if erros:
            raise ValidationError(erros)

    # BLOQUEIA ALTERAÇÕES QUE COMPROMETEM REGISTROS VINCULADOS

    def validar_alteracoes_com_vinculos(self):
        if not self.pk or not self.movimentacoes.exists():
            return

        compromisso_anterior = (
            CompromissoFinanceiro.objects.filter(pk=self.pk).first()
        )

        if compromisso_anterior is None:
            return

        campos_bloqueados = (
            ("usuario_id", "O proprietário"),
            ("tipo", "O tipo"),
            ("conta_id", "A conta"),
            ("categoria_id", "A categoria"),
        )

        erros = []

        for campo, nome in campos_bloqueados:
            if getattr(self, campo) != getattr(compromisso_anterior, campo):
                erros.append(
                    f"{nome} não pode ser alterado porque existem movimentações relacionadas ao compromisso")

        if erros:
            raise ValidationError(erros)

    # VALIDA REGRAS DO COMPROMISSO

    def clean(self):
        super().clean()

        self.validar_alteracoes_com_vinculos()

        if self.valor_total is not None and self.valor_total <= 0:
            raise ValidationError(
                {"valor_total": "O valor deve ser maior que zero."}
            )

        if (
            self.valor_pago_recebido_inicial is not None
            and self.valor_pago_recebido_inicial < 0
        ):
            raise ValidationError(
                {
                    "valor_pago_recebido_inicial": (
                        "O valor inicial não pode ser negativo."
                    )
                }
            )

        total_movimentacoes = Decimal("0.00")

        if self.pk:
            movimentacoes = self.movimentacoes.all()

            if movimentacoes.exists():
                valor_inicial_anterior = (
                    CompromissoFinanceiro.objects
                    .values_list("valor_pago_recebido_inicial", flat=True)
                    .get(pk=self.pk)
                )

                if (
                    self.valor_pago_recebido_inicial
                    != valor_inicial_anterior
                ):
                    raise ValidationError(
                        {
                            "valor_pago_recebido_inicial": (
                                "Este valor não pode ser alterado porque "
                                "já existem movimentações vinculadas."
                            )
                        }
                    )

                total_movimentacoes = (
                    movimentacoes.aggregate(total=Sum("valor"))["total"]
                    or Decimal("0.00")
                )

        if self.valor_pago_recebido_inicial is not None:
            self.valor_pago_recebido = (
                self.valor_pago_recebido_inicial + total_movimentacoes
            )

            if (
                self.valor_total is not None
                and self.valor_pago_recebido > self.valor_total
            ):
                raise ValidationError(
                    {
                        "valor_total": (
                            "O total do compromisso não pode ser menor "
                            "que o valor inicial mais as movimentações."
                        )
                    }
                )

        if self.conta_id and self.conta.usuario_id != self.usuario_id:
            raise ValidationError(
                {
                    "conta": "A conta deve pertencer ao mesmo usuário."
                }
            )

        if self.categoria_id and self.categoria.usuario_id != self.usuario_id:
            raise ValidationError(
                {
                    "categoria": "A categoria deve pertencer ao mesmo usuário."
                }
            )

        if (
            self.categoria_id
            and self.tipo == self.Tipo.PAGAR
            and self.categoria.tipo != Categoria.Tipo.SAIDA
        ):
            raise ValidationError(
                {
                    "categoria": (
                        "Compromissos a pagar precisam de categoria de saída."
                    )
                }
            )

        if (
            self.categoria_id
            and self.tipo == self.Tipo.RECEBER
            and self.categoria.tipo != Categoria.Tipo.ENTRADA
        ):
            raise ValidationError(
                {
                    "categoria": (
                        "Compromissos a receber precisam de categoria de entrada."
                    )
                }
            )

        self.validar_registros_ativos()

    # ATUALIZA O STATUS DO COMPROMISSO
    def atualizar_status(self):
        self.status = self.situacao

    # PROTEÇÃO CONTRA CONCORRÊNCIA: coordena alterações com pagamentos.
    # O bloqueio precede a validação e o recálculo do compromisso.
    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")

        if update_fields is not None:
            update_fields = set(update_fields)

            # Uma lista vazia significa que nada deve ser salvo.
            if not update_fields:
                return

        with transaction.atomic():
            if not self._state.adding:
                atual = (
                    CompromissoFinanceiro.objects
                    .select_for_update()
                    .filter(pk=self.pk)
                    .first()
                )

                if atual is None:
                    raise ValidationError(
                        "Este compromisso foi excluído. Atualize a página."
                    )

                if update_fields is not None:
                    # PROTEÇÃO CONTRA CONCORRÊNCIA: preserva os valores atuais
                    # dos campos não incluídos em um salvamento parcial.
                    for campo in self._meta.concrete_fields:
                        if campo.primary_key:
                            continue

                        if (
                            campo.name not in update_fields
                            and campo.attname not in update_fields
                        ):
                            setattr(
                                self,
                                campo.attname,
                                getattr(atual, campo.attname),
                            )

            self.full_clean()
            self.atualizar_status()

            if update_fields is not None:
                kwargs["update_fields"] = update_fields | {
                    "valor_pago_recebido",
                    "status",
                }

            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # PROTEÇÃO CONTRA CONCORRÊNCIA:
        # mantém a exclusão e a remoção dos vínculos na mesma transação.
        # No SQLite, BEGIN IMMEDIATE reserva a escrita desde este ponto.
        with transaction.atomic():
            # PROTEÇÃO CONTRA CONCORRÊNCIA:
            # bloqueia primeiro as movimentações, seguindo a ordem
            # utilizada pela edição e pela exclusão de movimentações.
            movimentacoes = list(
                Movimentacao.objects
                .filter(compromisso_financeiro_id=self.pk)
                .order_by("pk")
                .select_for_update()
            )

            ids_bloqueados = {
                movimentacao.pk
                for movimentacao in movimentacoes
            }

            # PROTEÇÃO CONTRA CONCORRÊNCIA:
            # no PostgreSQL, impede que os fluxos de pagamento protegidos
            # alterem este compromisso durante a exclusão.
            atual = (
                CompromissoFinanceiro.objects
                .select_for_update()
                .filter(pk=self.pk)
                .first()
            )

            if atual is None:
                raise ValidationError(
                    "Este compromisso já foi excluído. Atualize a página."
                )

            # PROTEÇÃO CONTRA CONCORRÊNCIA:
            # uma movimentação pode ter sido vinculada enquanto aguardávamos
            # o bloqueio do compromisso. Nesse caso, interrompe a exclusão
            # para não prosseguir com um conjunto incompleto de bloqueios.
            novos_vinculos = (
                Movimentacao.objects
                .filter(compromisso_financeiro_id=atual.pk)
                .exclude(pk__in=ids_bloqueados)
                .exists()
            )

            if novos_vinculos:
                raise ValidationError(
                    "As movimentações deste compromisso foram alteradas "
                    "durante a operação. Atualize a página e tente novamente."
                )

            # Executa a exclusão do Django, preservando as movimentações
            # conforme o on_delete=SET_NULL já definido no relacionamento.
            resultado = super(CompromissoFinanceiro, atual).delete(
                *args,
                **kwargs,
            )

            self.pk = None
            return resultado
    # REPRESENTACAO EM TEXTO DO COMPROMISSO

    def __str__(self):
        return self.titulo


class MovimentacaoQuerySet(models.QuerySet):
    def delete(self):
        with transaction.atomic():
            movimentacoes = list(
                self.select_related(None).order_by("pk").select_for_update()
            )

            total = 0
            detalhes = Counter()

            for movimetacao in movimentacoes:
                quantidade, contagem = movimetacao.delete()
                total += quantidade
                detalhes.update(contagem)
            return total, dict(detalhes)

# MODELO DE MOVIMENTACAO FINANCEIRA


class Movimentacao(models.Model):
    # TIPOS DE MOVIMENTACAO DISPONIVEIS
    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada"
        SAIDA = "SAIDA", "Saída"
        TRANSFERENCIA = "TRANSFERENCIA", "Transferência interna"

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="movimentacoes",
    )

    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
    )

    valor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    descricao = models.CharField(
        max_length=255,
        blank=True,
    )

    data = models.DateField(
        default=timezone.localdate,
    )

    hora = models.TimeField(
        default=timezone.now,
    )

    conta_origem = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        related_name="movimentacoes_origem",
        null=True,
        blank=True,
    )

    conta_destino = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        related_name="movimentacoes_destino",
        null=True,
        blank=True,
    )

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="movimentacoes",
        null=True,
        blank=True,
    )

    compromisso_financeiro = models.ForeignKey(
        CompromissoFinanceiro,
        on_delete=models.SET_NULL,
        related_name="movimentacoes",
        null=True,
        blank=True,
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
    )

    objects = MovimentacaoQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(valor__gt=0),
                name="movimentacao_valor_positivo",
            ),
        ]

    # VALIDA REGRAS DE TRANSFERENCIA
    def validar_transferencia(self):
        if not self.conta_origem:
            raise ValidationError(
                {"conta_origem": "Informe a conta de origem."})

        if not self.conta_destino:
            raise ValidationError(
                {"conta_destino": "Informe a conta de destino."})

        if self.conta_origem == self.conta_destino:
            raise ValidationError(
                {
                    "conta_destino": (
                        "A conta de destino deve ser diferente da origem."
                    )
                }
            )

        if self.categoria:
            raise ValidationError(
                {
                    "categoria": "Transferências internas não possuem categoria."
                }
            )

    # VALIDA SALDO DISPONIVEL(regra desativada por opção de negócio)
    # def validar_saldo(self):
    #     if not self.conta_origem:
    #         return

    #     saldo_disponivel = self.conta_origem.saldo_atual

    #     # DEVOLVE TEMPORARIAMENTE O VALOR ANTIGO AO SALDO NA EDICAO
    #     if self.pk:
    #         movimentacao_anterior = Movimentacao.objects.filter(
    #             pk=self.pk
    #         ).first()

    #         if (
    #             movimentacao_anterior
    #             and movimentacao_anterior.conta_origem_id
    #             == self.conta_origem_id
    #         ):
    #             saldo_disponivel += movimentacao_anterior.valor

    #     if saldo_disponivel < self.valor:
    #         raise ValidationError(
    #             {"valor": "Saldo insuficiente na conta de origem."})

    # VALIDA COMPROMISSO FINANCEIRO VINCULADO

    def validar_compromisso_financeiro(self):
        if not self.compromisso_financeiro_id:
            return

        compromisso = self.compromisso_financeiro

        if compromisso.usuario_id != self.usuario_id:
            raise ValidationError(
                {
                    "compromisso_financeiro": (
                        "O compromisso deve pertencer ao mesmo usuário."
                    )
                }
            )

        if self.tipo == self.Tipo.TRANSFERENCIA:
            raise ValidationError(
                {
                    "compromisso_financeiro": (
                        "Transferências não possuem compromisso financeiro."
                    )
                }
            )

        if (
            self.tipo == self.Tipo.ENTRADA
            and compromisso.tipo != CompromissoFinanceiro.Tipo.RECEBER
        ):
            raise ValidationError(
                {
                    "compromisso_financeiro": (
                        "Entradas devem estar ligadas a compromissos a receber."
                    )
                }
            )

        if (
            self.tipo == self.Tipo.SAIDA
            and compromisso.tipo != CompromissoFinanceiro.Tipo.PAGAR
        ):
            raise ValidationError(
                {
                    "compromisso_financeiro": (
                        "Saídas devem estar ligadas a compromissos a pagar."
                    )
                }
            )

        if (
            compromisso.categoria_id
            and self.categoria_id != compromisso.categoria_id
        ):
            raise ValidationError(
                {
                    "categoria": (
                        "A categoria deve ser a mesma do compromisso financeiro."
                    )
                }
            )

        if not compromisso.conta_id:
            return

        if (
            self.tipo == self.Tipo.ENTRADA
            and self.conta_destino_id
            and self.conta_destino_id != compromisso.conta_id
        ):
            raise ValidationError(
                {
                    "conta_destino": (
                        "A conta de destino deve ser a mesma do compromisso financeiro."
                    )
                }
            )

        if (
            self.tipo == self.Tipo.SAIDA
            and self.conta_origem_id
            and self.conta_origem_id != compromisso.conta_id
        ):
            raise ValidationError(
                {
                    "conta_origem": (
                        "A conta de origem deve ser a mesma do compromisso financeiro."
                    )
                }
            )

    # PERMITE MANTER VINCULOS INATIVOS MAS NÃO PERMITE CADASTRAR NOVOS VINCULOS INATIVOS
    def validar_registros_ativos(self):
        anterior = (
            Movimentacao.objects.filter(pk=self.pk).first()
            if self.pk
            else None
        )

        erros = {}

        for campo in ("conta_destino", "conta_origem", "categoria"):
            registro_id = (
                getattr(self, f"{campo}_id")
            )

            if registro_id is None:
                continue

            anterior_id = (
                getattr(anterior, f"{campo}_id")
                if anterior is not None
                else None
            )

            if registro_id == anterior_id:
                continue

            if not getattr(self, campo).ativa:
                erros[campo] = (
                    "Não é possível selecionar um registro inativo. Somente um vinculo já existente pode ser mantido inativo"
                )

        if erros:
            raise ValidationError(erros)

    def validar_data_nao_futura(self):
        if self.data and self.data > timezone.localdate():
            raise ValidationError(
                {
                    "data": (
                        "A data da movimentação não pode ser futura. "
                        "Use compromissos para lançamentos futuros."
                    )
                }
            )

    def validar_limite_compromisso(self):
        if not self.compromisso_financeiro_id or self.valor is None:
            return

        compromisso = self.compromisso_financeiro

        outras_movimentacoes = compromisso.movimentacoes.exclude(
            pk=self.pk,
        )

        total_movimentacoes = (
            outras_movimentacoes.aggregate(total=Sum("valor"))["total"]
            or Decimal("0.00")
        )

        total_projetado = (
            compromisso.valor_pago_recebido_inicial + total_movimentacoes + self.valor
        )

        if total_projetado > compromisso.valor_total:
            raise ValidationError(
                {
                    "valor": (
                        "O valor total mais as movimentações não pode superar o total do compromisso"
                    )
                }
            )

    # VALIDA REGRAS DA MOVIMENTACAO

    def clean(self):
        super().clean()

        if self.valor is not None and self.valor <= 0:
            raise ValidationError(
                {"valor": "O valor deve ser maior que zero."})

        self.validar_data_nao_futura()

        if self.conta_origem_id:
            if self.conta_origem.usuario_id != self.usuario_id:
                raise ValidationError(
                    {
                        "conta_origem": (
                            "A conta de origem pertence a outro usuário."
                        )
                    }
                )

        if self.conta_destino_id:
            if self.conta_destino.usuario_id != self.usuario_id:
                raise ValidationError(
                    {
                        "conta_destino": (
                            "A conta de destino pertence a outro usuário."
                        )
                    }
                )

        if self.categoria_id:
            if self.categoria.usuario_id != self.usuario_id:
                raise ValidationError(
                    {
                        "categoria": "A categoria pertence a outro usuário."
                    }
                )

        if self.tipo == self.Tipo.ENTRADA:
            if not self.conta_destino:
                raise ValidationError(
                    {
                        "conta_destino": (
                            "Uma entrada precisa de uma conta de destino."
                        )
                    }
                )

            if self.conta_origem:
                raise ValidationError(
                    {
                        "conta_origem": "Uma entrada não possui conta de origem."
                    }
                )

            if self.categoria and self.categoria.tipo != Categoria.Tipo.ENTRADA:
                raise ValidationError(
                    {
                        "categoria": "A entrada precisa de uma categoria de entrada."
                    }
                )

        elif self.tipo == self.Tipo.SAIDA:
            if not self.conta_origem:
                raise ValidationError(
                    {
                        "conta_origem": "Uma saída precisa de uma conta de origem."
                    }
                )

            if self.conta_destino:
                raise ValidationError(
                    {
                        "conta_destino": "Uma saída não possui conta de destino."
                    }
                )

            if self.categoria and self.categoria.tipo != Categoria.Tipo.SAIDA:
                raise ValidationError(
                    {
                        "categoria": "A saída precisa de uma categoria de saída."
                    }
                )

            # self.validar_saldo()

        elif self.tipo == self.Tipo.TRANSFERENCIA:
            self.validar_transferencia()
            # self.validar_saldo()

        self.validar_compromisso_financeiro()
        self.validar_registros_ativos()
        self.validar_limite_compromisso()

    # PROTEÇÃO CONTRA CONCORRÊNCIA: valida a criação após reservar a escrita
    # no SQLite ou bloquear o compromisso no PostgreSQL.

    def _salvar_nova_movimentacao(self, *args, **kwargs):
        with transaction.atomic():
            compromisso = None

            if self.compromisso_financeiro_id:
                # PostgreSQL: bloqueia o compromisso ate terminar a transacao.
                # SQLite: a reserva de escrita vem do BEGIN IMMEDIATE.
                compromisso = (
                    CompromissoFinanceiro.objects
                    .select_for_update()
                    .filter(pk=self.compromisso_financeiro_id)
                    .first()
                )

                if compromisso is None:
                    raise ValidationError(
                        {
                            "compromisso_financeiro": (
                                "O compromisso selecionado não existe mais."
                            )
                        }
                    )

                # PROTEÇÃO CONTRA CONCORRÊNCIA: descarta a cópia antiga do formulário.
                self.compromisso_financeiro = compromisso

            # PROTEÇÃO CONTRA CONCORRÊNCIA: revalida o limite após o bloqueio.
            self.full_clean()
            resultado = super().save(*args, **kwargs)

            if compromisso is not None:
                compromisso.recalcular_valor_pago()

            return resultado

    # PROTEÇÃO CONTRA CONCORRÊNCIA: coordena edição e troca de compromisso.
    def _salvar_movimentacao_existente(self, *args, **kwargs):
        with transaction.atomic():
            # Busca o registro atual dentro da transacao.
            # No PostgreSQL, impede outra edicao simultanea desta movimentacao.
            anterior = (
                Movimentacao.objects
                .select_for_update()
                .filter(pk=self.pk)
                .first()
            )

            if anterior is None:
                raise ValidationError(
                    "Esta movimentação foi excluída. Atualize a página."
                )

            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                update_fields = set(update_fields)
                for campo in self._meta.concrete_fields:
                    if campo.primary_key:
                        continue
                    if campo.name not in update_fields and campo.attname not in update_fields:
                        setattr(self, campo.attname, getattr(
                            anterior, campo.attname))

            compromisso_ids = {
                anterior.compromisso_financeiro_id,
                self.compromisso_financeiro_id,
            }
            compromisso_ids.discard(None)

            # PROTEÇÃO CONTRA CONCORRÊNCIA: bloqueia por ID para reduzir
            # impasses entre operações que atingem os mesmos compromissos.
            compromissos = {
                compromisso.pk: compromisso
                for compromisso in (
                    CompromissoFinanceiro.objects
                    .select_for_update()
                    .filter(pk__in=compromisso_ids)
                    .order_by("pk")
                )
            }

            if self.compromisso_financeiro_id:
                compromisso = compromissos.get(
                    self.compromisso_financeiro_id
                )

                if compromisso is None:
                    raise ValidationError(
                        {
                            "compromisso_financeiro": (
                                "O compromisso selecionado não existe mais."
                            )
                        }
                    )

                # Usa a versao atualizada nas validacoes.
                self.compromisso_financeiro = compromisso

            self.full_clean()
            resultado = super().save(*args, **kwargs)

            # Ao trocar o vinculo, atualiza tanto o compromisso antigo
            # quanto o novo, dentro da mesma transacao.
            for compromisso in compromissos.values():
                compromisso.recalcular_valor_pago()

            return resultado

    # PROTEÇÃO CONTRA CONCORRÊNCIA: encaminha para os fluxos protegidos.
    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            if not update_fields:
                return
            kwargs["update_fields"] = update_fields

        if self._state.adding:
            return self._salvar_nova_movimentacao(*args, **kwargs)

        return self._salvar_movimentacao_existente(*args, **kwargs)

    # PROTEÇÃO CONTRA CONCORRÊNCIA: exclui usando o vínculo atual do banco.
    def delete(self, *args, **kwargs):
        with transaction.atomic():
            # PROTEÇÃO CONTRA CONCORRÊNCIA: segue a ordem da edição,
            # bloqueando primeiro a movimentação e depois o compromisso.
            atual = (
                Movimentacao.objects
                .select_for_update()
                .filter(pk=self.pk)
                .first()
            )

            if atual is None:
                raise ValidationError(
                    "Esta movimentação já foi excluída. Atualize a página."
                )

            compromisso = None

            if atual.compromisso_financeiro_id:
                compromisso = (
                    CompromissoFinanceiro.objects
                    .select_for_update()
                    .filter(pk=atual.compromisso_financeiro_id)
                    .first()
                )

            # Usa o registro atualizado para realizar a exclusao.
            # Chama o delete do Django, sem repetir este metodo.
            resultado = super(Movimentacao, atual).delete(
                *args,
                **kwargs,
            )

            if compromisso is not None:
                compromisso.recalcular_valor_pago()

            # Mantem o objeto original consistente com sua exclusao.
            self.pk = None

            return resultado

    # REPRESENTACAO EM TEXTO DA MOVIMENTACAO

    def __str__(self):
        return f"{self.get_tipo_display()} — R$ {self.valor:.2f}"
