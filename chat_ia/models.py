import uuid

from django.db import models

from usuarios.models import Usuario


# Guarda a ação proposta para que a confirmação seja vinculada ao usuário e usada uma única vez.
class AcaoPendente(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="acoes_pendentes_chat",
    )
    acao = models.CharField(max_length=40)
    dados = models.JSONField()
    criada_em = models.DateTimeField(auto_now_add=True)
    confirmada_em = models.DateTimeField(null=True, blank=True)
    registro_id = models.PositiveBigIntegerField(null=True, blank=True)
