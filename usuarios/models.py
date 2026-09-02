from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


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

        if not self.email:
            raise ValidationError({"email": "O e-mail é obrigatório."})

        email_existente = User.objects.filter(
            email__iexact=self.email
        ).exclude(pk=self.pk)

        if email_existente.exists():
            raise ValidationError({"email": "Este e-mail já está cadastrado."})

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()

        # EMAIL USADO COMO USERNAME INTERNO DO DJANGO
        self.username = self.email

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.email
