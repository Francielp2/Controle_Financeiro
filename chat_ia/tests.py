import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from financeiro.models import Categoria
from financeiro.tests.base import usuario

from .acoes import criar_acao_pendente
from .models import AcaoPendente, PRAZO_CHAT, TarefaChat


class TarefasChatTests(TestCase):
    def setUp(self):
        self.usuario = usuario()
        self.client.force_login(self.usuario)
        self.pagina = reverse("chat_ia:pagina")
        self.conversar = reverse("chat_ia:conversar")
        self.gerenciar = reverse("chat_ia:gerenciar_tarefa")
        self.confirmar = reverse("chat_ia:confirmar")

    def _enviar(self, tarefa, texto):
        return self.client.post(
            self.conversar,
            data=json.dumps({"tarefa_id": str(tarefa.pk), "mensagem": texto}),
            content_type="application/json",
        )

    def test_contexto_fica_na_tarefa_e_usa_so_sete_mensagens(self):
        self.client.get(self.pagina)
        primeira = TarefaChat.objects.get(usuario=self.usuario)
        contextos = []

        def resposta(_usuario, mensagem, historico):
            contextos.append(historico)
            return {"resposta": f"Resposta: {mensagem}", "resultados": [], "historico": []}

        with patch("chat_ia.views.responder", side_effect=resposta):
            for numero in range(5):
                self.assertEqual(self._enviar(primeira, f"Mensagem {numero}").status_code, 200)

            self.assertEqual(len(contextos[-1]), 7)
            self.assertEqual(contextos[-1][0]["content"], "Resposta: Mensagem 0")
            pagina_reaberta = self.client.get(self.pagina)
            self.assertContains(pagina_reaberta, "Resposta: Mensagem 4")

            self.client.post(self.gerenciar, {"operacao": "nova"})
            segunda = TarefaChat.objects.get(usuario=self.usuario, encerrada_em__isnull=True)
            self.assertNotEqual(primeira.pk, segunda.pk)
            self.assertEqual(self._enviar(primeira, "Mensagem antiga").status_code, 409)
            self.assertEqual(self._enviar(segunda, "Outro assunto").status_code, 200)
            self.assertEqual(contextos[-1], [])

            self.client.post(self.gerenciar, {
                "operacao": "retomar", "tarefa_id": str(primeira.pk)
            })
            self.assertEqual(self._enviar(primeira, "De volta").status_code, 200)
            self.assertEqual(len(contextos[-1]), 7)
            self.assertNotIn("Outro assunto", str(contextos[-1]))

    def test_previa_e_confirmacao_sobrevivem_a_navegacao(self):
        self.client.get(self.pagina)
        tarefa = TarefaChat.objects.get(usuario=self.usuario)
        proposta = criar_acao_pendente(
            self.usuario, "cadastrar_categoria", {"nome": "Lazer", "tipo": "SAIDA"}
        )
        with patch("chat_ia.views.responder", return_value={
            "resposta": "Preparei a categoria Lazer para sua confirmação.",
            "resultados": [{"ferramenta": "propor_acao", "dados": proposta}],
            "historico": [],
        }):
            self.assertEqual(self._enviar(tarefa, "Crie Lazer").status_code, 200)

        pagina_reaberta = self.client.get(self.pagina)
        previa = pagina_reaberta.context["mensagens_iniciais"][1]["exibicao"]["previas"][0]
        self.assertEqual(previa["situacao"], "pendente")
        self.assertEqual(previa["id_acao"], proposta["id_acao"])

        self.client.post(self.gerenciar, {"operacao": "nova"})
        self.client.post(self.gerenciar, {
            "operacao": "retomar", "tarefa_id": str(tarefa.pk)
        })
        previa_retomada = self.client.get(self.pagina).context[
            "mensagens_iniciais"
        ][1]["exibicao"]["previas"][0]
        self.assertEqual(previa_retomada["situacao"], "pendente")

        resposta = self.client.post(
            self.confirmar,
            data=json.dumps({"tarefa_id": str(tarefa.pk), "id_acao": proposta["id_acao"]}),
            content_type="application/json",
        )
        self.assertTrue(resposta.json()["confirmada"])
        self.assertTrue(Categoria.objects.filter(usuario=self.usuario, nome="Lazer", ativa=True).exists())
        mensagens = self.client.get(self.pagina).context["mensagens_iniciais"]
        self.assertEqual(mensagens[1]["exibicao"]["previas"][0]["situacao"], "confirmada")
        self.assertEqual(mensagens[-1]["papel"], "sistema")
        self.assertIn("ID", mensagens[-1]["contexto"])

    def test_tarefas_antigas_e_acoes_vencidas_sao_removidas(self):
        self.client.get(self.pagina)
        antiga = TarefaChat.objects.get(usuario=self.usuario)
        proposta = criar_acao_pendente(
            self.usuario, "cadastrar_categoria", {"nome": "Teste", "tipo": "SAIDA"}
        )
        self.client.post(self.gerenciar, {"operacao": "nova"})
        atual = TarefaChat.objects.get(usuario=self.usuario, encerrada_em__isnull=True)
        limite = timezone.now() - PRAZO_CHAT - timedelta(minutes=1)
        TarefaChat.objects.filter(pk=antiga.pk).update(encerrada_em=limite)
        AcaoPendente.objects.filter(pk=proposta["id_acao"]).update(criada_em=limite)

        self.client.get(self.pagina)
        self.assertFalse(TarefaChat.objects.filter(pk=antiga.pk).exists())
        self.assertTrue(TarefaChat.objects.filter(pk=atual.pk).exists())
        self.assertFalse(AcaoPendente.objects.filter(pk=proposta["id_acao"]).exists())

    def test_nao_exibe_nem_retoma_tarefa_de_outro_usuario(self):
        outro = usuario(2)
        alheia = TarefaChat.objects.create(
            usuario=outro,
            titulo="Assunto reservado",
            mensagens=[{"papel": "usuario", "texto": "Mensagem reservada"}],
        )
        resposta = self.client.get(self.pagina)
        self.assertNotContains(resposta, "Assunto reservado")
        self.assertNotContains(resposta, "Mensagem reservada")
        tentativa = self.client.post(self.gerenciar, {
            "operacao": "retomar", "tarefa_id": str(alheia.pk)
        })
        self.assertEqual(tentativa.status_code, 404)
