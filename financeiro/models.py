from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from usuarios.models import Usuario


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

    # CALCULA O SALDO ATUAL DA CONTA
    @property
    def saldo_atual(self):
        entradas = self.movimentacoes_destino.aggregate(total=Sum("valor"))[
            "total"
        ] or Decimal("0.00")

        saidas = self.movimentacoes_origem.aggregate(total=Sum("valor"))[
            "total"
        ] or Decimal("0.00")

        return self.saldo_inicial + entradas - saidas

    # VERIFICA SE A CONTA POSSUI MOVIMENTACOES
    def possui_movimentacoes(self):
        return (
            self.movimentacoes_origem.exists()
            or self.movimentacoes_destino.exists()
        )

    # VALIDA REGRAS DA CONTA
    def clean(self):
        super().clean()

        if self.usuario_id and self.nome:
            conta_existente = Conta.objects.filter(
                usuario=self.usuario,
                nome__iexact=self.nome,
            ).exclude(pk=self.pk)

            if conta_existente.exists():
                raise ValidationError({"nome": "Já existe uma conta com este nome."})

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

    # VALIDA REGRAS DA CATEGORIA
    def clean(self):
        super().clean()

        if self.usuario_id and self.nome and self.tipo:
            categoria_existente = Categoria.objects.filter(
                usuario=self.usuario,
                nome__iexact=self.nome,
                tipo=self.tipo,
            ).exclude(pk=self.pk)

            if categoria_existente.exists():
                raise ValidationError({"nome": "Esta categoria já está cadastrada."})

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

    # CALCULA O VALOR RESTANTE
    def valor_restante(self):
        restante = self.valor_total - self.valor_pago_recebido
        return max(restante, Decimal("0.00"))

    # VERIFICA SE O COMPROMISSO ESTA QUITADO
    def esta_quitado(self):
        return self.valor_pago_recebido >= self.valor_total

    # VERIFICA SE O COMPROMISSO ESTA VENCIDO
    def esta_vencido(self):
        return (
            self.data_vencimento < timezone.localdate()
            and not self.esta_quitado()
        )

    # VALIDA REGRAS DO COMPROMISSO
    def clean(self):
        super().clean()

        if self.valor_total is not None and self.valor_total <= 0:
            raise ValidationError({"valor_total": "O valor deve ser maior que zero."})

        if (
            self.valor_pago_recebido is not None
            and self.valor_pago_recebido < 0
        ):
            raise ValidationError({
                "valor_pago_recebido": "O valor não pode ser negativo."
            })

        if (
            self.valor_total is not None
            and self.valor_pago_recebido is not None
            and self.valor_pago_recebido > self.valor_total
        ):
            raise ValidationError({
                "valor_pago_recebido": "O valor registrado não pode superar o total."
            })

        if self.conta_id and self.conta.usuario_id != self.usuario_id:
            raise ValidationError({
                "conta": "A conta deve pertencer ao mesmo usuário."
            })

        if (
            self.categoria_id
            and self.categoria.usuario_id != self.usuario_id
        ):
            raise ValidationError({
                "categoria": "A categoria deve pertencer ao mesmo usuário."
            })

    # ATUALIZA O STATUS DO COMPROMISSO
    def atualizar_status(self):
        if self.esta_quitado():
            self.status = self.Status.QUITADO
        elif self.valor_pago_recebido > 0:
            self.status = self.Status.PARCIAL
        elif self.esta_vencido():
            self.status = self.Status.ATRASADO
        else:
            self.status = self.Status.PENDENTE

    # REGISTRA PAGAMENTO DO COMPROMISSO
    def registrar_pagamento(self, valor):
        if self.tipo != self.Tipo.PAGAR:
            raise ValidationError("Este compromisso não é do tipo a pagar.")

        self.valor_pago_recebido += Decimal(str(valor))
        self.save()

    # REGISTRA RECEBIMENTO DO COMPROMISSO
    def registrar_recebimento(self, valor):
        if self.tipo != self.Tipo.RECEBER:
            raise ValidationError("Este compromisso não é do tipo a receber.")

        self.valor_pago_recebido += Decimal(str(valor))
        self.save()

    # SALVA O COMPROMISSO APOS ATUALIZAR STATUS
    def save(self, *args, **kwargs):
        self.atualizar_status()
        self.full_clean()
        super().save(*args, **kwargs)

    # REPRESENTACAO EM TEXTO DO COMPROMISSO
    def __str__(self):
        return self.titulo


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
        default=timezone.now,
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

    # VALIDA REGRAS DE TRANSFERENCIA
    def validar_transferencia(self):
        if not self.conta_origem:
            raise ValidationError({"conta_origem": "Informe a conta de origem."})

        if not self.conta_destino:
            raise ValidationError({"conta_destino": "Informe a conta de destino."})

        if self.conta_origem == self.conta_destino:
            raise ValidationError({
                "conta_destino": "A conta de destino deve ser diferente da origem."
            })

        if self.categoria:
            raise ValidationError({
                "categoria": "Transferências internas não possuem categoria."
            })

    # VALIDA SALDO DISPONIVEL
    def validar_saldo(self):
        if not self.conta_origem:
            return

        saldo_disponivel = self.conta_origem.saldo_atual

        # DEVOLVE TEMPORARIAMENTE O VALOR ANTIGO AO SALDO NA EDICAO
        if self.pk:
            movimentacao_anterior = Movimentacao.objects.filter(
                pk=self.pk
            ).first()

            if (
                movimentacao_anterior
                and movimentacao_anterior.conta_origem_id
                == self.conta_origem_id
            ):
                saldo_disponivel += movimentacao_anterior.valor

        if saldo_disponivel < self.valor:
            raise ValidationError({"valor": "Saldo insuficiente na conta de origem."})

    # VALIDA REGRAS DA MOVIMENTACAO
    def clean(self):
        super().clean()

        if self.valor is not None and self.valor <= 0:
            raise ValidationError({"valor": "O valor deve ser maior que zero."})

        if self.conta_origem_id:
            if self.conta_origem.usuario_id != self.usuario_id:
                raise ValidationError({
                    "conta_origem": "A conta de origem pertence a outro usuário."
                })

        if self.conta_destino_id:
            if self.conta_destino.usuario_id != self.usuario_id:
                raise ValidationError({
                    "conta_destino": "A conta de destino pertence a outro usuário."
                })

        if self.categoria_id:
            if self.categoria.usuario_id != self.usuario_id:
                raise ValidationError({
                    "categoria": "A categoria pertence a outro usuário."
                })

        if self.tipo == self.Tipo.ENTRADA:
            if not self.conta_destino:
                raise ValidationError({
                    "conta_destino": "Uma entrada precisa de uma conta de destino."
                })

            if self.conta_origem:
                raise ValidationError({
                    "conta_origem": "Uma entrada não possui conta de origem."
                })

            if (
                self.categoria
                and self.categoria.tipo != Categoria.Tipo.ENTRADA
            ):
                raise ValidationError({
                    "categoria": "A entrada precisa de uma categoria de entrada."
                })

        elif self.tipo == self.Tipo.SAIDA:
            if not self.conta_origem:
                raise ValidationError({
                    "conta_origem": "Uma saída precisa de uma conta de origem."
                })

            if self.conta_destino:
                raise ValidationError({
                    "conta_destino": "Uma saída não possui conta de destino."
                })

            if (
                self.categoria
                and self.categoria.tipo != Categoria.Tipo.SAIDA
            ):
                raise ValidationError({
                    "categoria": "A saída precisa de uma categoria de saída."
                })

            self.validar_saldo()

        elif self.tipo == self.Tipo.TRANSFERENCIA:
            self.validar_transferencia()
            self.validar_saldo()

    # SALVA A MOVIMENTACAO APOS VALIDACAO
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    # REPRESENTACAO EM TEXTO DA MOVIMENTACAO
    def __str__(self):
        return f"{self.get_tipo_display()} — R$ {self.valor:.2f}"