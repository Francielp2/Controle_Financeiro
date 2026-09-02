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