from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
import re


def erro_validacao_cpf(cpf):
    cpf = re.sub(r"\D", "", cpf or "")
    if not cpf:
        return "O CPF é obrigatório."

    if len(cpf) != 11:
        return "O CPF deve possuir 11 dígitos."

    if cpf == cpf[0] * 11:
        return "CPF inválido."

    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digito_1 = (soma * 10) % 11

    if digito_1 == 10:
        digito_1 = 0

    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digito_2 = (soma * 10) % 11

    if digito_2 == 10:
        digito_2 = 0

    if cpf[-2:] != f"{digito_1}{digito_2}":
        return "CPF inválido."

    return None

# MODELO DE USUARIO DO SISTEMA


class Usuario(User):
    cpf = models.CharField(
        max_length=11,
        unique=True,
        verbose_name="CPF",
    )

    rg = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="RG",
    )

    telefone = models.CharField(
        max_length=20,
        verbose_name="Telefone",
    )

    def clean(self):
        super().clean()

        # Email
        if not self.email:
            raise ValidationError({"email": "O e-mail é obrigatório."})

        email_existente = User.objects.filter(email__iexact=self.email).exclude(
            pk=self.pk
        )

        if email_existente.exists():
            raise ValidationError({"email": "Este e-mail já está cadastrado."})

        erro_cpf = erro_validacao_cpf(self.cpf)

        if erro_cpf:
            raise ValidationError({"cpf": erro_cpf})

       # RG
        rg_limpo = re.sub(r"[^A-Za-z0-9]", "", self.rg or "")

        if not rg_limpo:
            raise ValidationError({"rg": "O RG é obrigatório."})

        # Telefone
        telefone_limpo = re.sub(r"\D", "", self.telefone or "")

        if not telefone_limpo:
            raise ValidationError({"telefone": "O telefone é obrigatório."})

        if len(telefone_limpo) not in (10, 11):
            raise ValidationError({
                "telefone": "O telefone deve possuir 10 ou 11 dígitos."
            })

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()

        self.cpf = re.sub(r"\D", "", self.cpf or "")
        self.rg = re.sub(
            r"[^A-Za-z0-9]",
            "",
            self.rg or ""
        ).upper()
        self.telefone = re.sub(r"\D", "", self.telefone or "")

        # EMAIL USADO COMO USERNAME INTERNO DO DJANGO
        self.username = self.email

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.email
