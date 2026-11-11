import uuid
from datetime import timedelta

from django.db import models
from django.db.models import Q

from usuarios.models import Usuario


PRAZO_CHAT = timedelta(days=2)


# Guarda uma conversa independente por tarefa e suas mensagens para retomada.
class TarefaChat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name="tarefas_chat"
    )
    titulo = models.CharField(max_length=80, default="Nova tarefa")
    mensagens = models.JSONField(default=list)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)
    encerrada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["usuario"],
                condition=Q(encerrada_em__isnull=True),
                name="uma_tarefa_ativa_por_usuario",
            )
        ]


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
