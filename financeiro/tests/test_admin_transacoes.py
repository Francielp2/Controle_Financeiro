# AVISO: Estes testes foram elaborados com auxílio de Inteligência Artificial.
# Não houve revisão humana individual de todos os casos.
# Sua aprovação não garante ausência de defeitos; revise-os ao mudar as regras.
from unittest.mock import patch
from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.db import connection, OperationalError
from django.test import TestCase, TransactionTestCase, RequestFactory
from django.urls import reverse
from financeiro.models import Conta, Categoria, CompromissoFinanceiro, Movimentacao
from financeiro.concorrencia import eh_erro_de_concorrencia, salvar_formulario_com_tratamento, MENSAGEM_CONCORRENCIA
from financeiro.forms import MovimentacaoForm
from .base import DadosMixin


def erro_bloqueio():
    erro = OperationalError("Bloqueio sintético")
    erro.sqlite_errorcode = 5
    return erro


def request_admin(user):
    request = RequestFactory().post("/admin/financeiro/movimentacao/")
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


class AdminTests(DadosMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.root = User.objects.create_superuser(username="root", email="root@example.invalid", password="senha-sintetica")
        self.request = request_admin(self.root)

    def test_readonly_formularios_reais(self):
        """Admin gera campos readonly de cada modelo segundo seus vínculos."""
        c = self.compromisso()
        self.movimento(compromisso_financeiro=c)
        for modelo, obj, bloqueados in ((Conta, self.conta, {"usuario", "saldo_inicial"}),
                                        (Categoria, self.cat, {"usuario", "tipo"}),
                                        (CompromissoFinanceiro, c, {"usuario", "tipo", "conta", "categoria", "valor_pago_recebido_inicial", "valor_pago_recebido"})):
            ma = admin.site._registry[modelo]
            with self.subTest(modelo=modelo.__name__):
                self.assertTrue(bloqueados.issubset(set(ma.get_readonly_fields(self.request, obj))))
                campos = ma.get_form(self.request, obj).base_fields
                self.assertTrue(bloqueados.isdisjoint(campos))
                cadastro = ma.get_form(self.request).base_fields
                self.assertIn("usuario", cadastro)
        ma = admin.site._registry[CompromissoFinanceiro]
        self.assertEqual(ma.mostrar_situacao(c), "Parcial")
        self.assertNotIn("status", ma.get_form(self.request, c).base_fields)

    def test_admin_vinculos_inativos_e_script(self):
        """Formulário gerado no admin mantém vínculo inativo e inclui metadados/script."""
        c = self.compromisso()
        m = self.movimento(compromisso_financeiro=c)
        self.conta.ativa = False
        self.conta.save()
        ma = admin.site._registry[Movimentacao]
        f = ma.get_form(self.request, m)(instance=m)
        self.assertIn(self.conta, f.fields["conta_origem"].queryset)
        self.assertNotIn(self.conta, f.fields["conta_destino"].queryset)
        self.assertIn("data-categorias-compromissos", f.fields["compromisso_financeiro"].widget.widget.attrs)
        self.assertIn("categoria_compromisso.js", str(f.media))

    def test_permissoes_admin_http(self):
        """Admin rejeita comum e staff sem permissão, mas permite superusuário."""
        url = reverse("admin:financeiro_movimentacao_changelist")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.u)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.u.is_staff = True
        self.u.save()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.root)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_lote_admin_recalcula_inicial(self):
        """Exclusão em lote do admin preserva inicial e restaura saldo da conta."""
        c = self.compromisso()
        self.movimento(compromisso_financeiro=c)
        self.movimento(compromisso_financeiro=c)
        admin.site._registry[Movimentacao].delete_queryset(self.request, Movimentacao.objects.all())
        self.acumulado(c, "10")
        self.assertEqual(self.conta.saldo_atual, 100)

    def test_lote_compromissos_preserva_movimentos(self):
        """Lote de compromissos remove vínculos sem apagar pagamentos ou alterar saldo."""
        c = self.compromisso()
        m = self.movimento(compromisso_financeiro=c)
        admin.site._registry[CompromissoFinanceiro].delete_queryset(self.request, CompromissoFinanceiro.objects.all())
        m.refresh_from_db()
        self.assertIsNone(m.compromisso_financeiro_id)
        self.assertEqual(self.conta.saldo_atual, 80)

    def test_rollback_lote_http_auditoria(self):
        """Falha no segundo item desfaz o lote inteiro, inclusive logs de auditoria."""
        c = self.compromisso()
        a = self.movimento(compromisso_financeiro=c)
        b = self.movimento(compromisso_financeiro=c)
        original = Movimentacao.delete
        def excluir(obj, *args, **kwargs):
            if obj.pk == b.pk:
                raise ValidationError("Falha sintética no segundo item")
            return original(obj, *args, **kwargs)
        self.client.force_login(self.root)
        with patch.object(Movimentacao, "delete", excluir):
            r = self.client.post(reverse("admin:financeiro_movimentacao_changelist"),
                                 {"action": "delete_selected", "_selected_action": [a.pk, b.pk], "post": "yes"}, follow=True)
        self.assertEqual(Movimentacao.objects.count(), 2)
        self.acumulado(c, "50")
        self.assertEqual(self.conta.saldo_atual, 60)
        self.assertEqual(LogEntry.objects.count(), 0)
        avisos = list(r.context["messages"])
        self.assertTrue(any(m.level == messages.ERROR for m in avisos))
        self.assertFalse(any(m.level == messages.SUCCESS for m in avisos))

    def test_exclusao_individual_http(self):
        """Confirmação GET preserva movimento; POST exclui e registra auditoria."""
        c = self.compromisso()
        m = self.movimento(compromisso_financeiro=c)
        self.client.force_login(self.root)
        url = reverse("admin:financeiro_movimentacao_delete", args=[m.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(Movimentacao.objects.exists())
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 302)
        self.acumulado(c, "10")
        self.assertEqual(LogEntry.objects.count(), 1)

    def test_erros_banco_desconhecidos_propagados(self):
        """Admin não oculta erro operacional que não representa concorrência."""
        ma = admin.site._registry[Movimentacao]
        def falhar():
            raise OperationalError("Tabela ausente sintética")
        with self.assertRaises(OperationalError):
            ma._executar_com_tratamento(self.request, falhar)

    def test_classificacao_erros(self):
        """Classifica códigos SQLite estendidos e PostgreSQL sem validar servidor PostgreSQL."""
        for codigo in (5, 6, 261, 517):
            erro = OperationalError("sintético")
            erro.sqlite_errorcode = codigo
            self.assertTrue(eh_erro_de_concorrencia(erro))
        for codigo in ("40001", "40P01", "55P03"):
            causa = Exception("sintético")
            causa.sqlstate = codigo
            erro = OperationalError("sintético")
            erro.__cause__ = causa
            self.assertTrue(eh_erro_de_concorrencia(erro))
        self.assertFalse(eh_erro_de_concorrencia(OperationalError("database is locked")))


class FalhasTransacaoTests(DadosMixin, TransactionTestCase):
    def test_formulario_falha_inicio(self):
        """Bloqueio simulado ao iniciar transação retorna erro e não chama save."""
        f = MovimentacaoForm(self.post_movimento(), instance=Movimentacao(usuario=self.u))
        with patch.object(connection, "_start_transaction_under_autocommit", side_effect=erro_bloqueio()), patch.object(f, "save", wraps=f.save) as save:
            self.assertFalse(salvar_formulario_com_tratamento(f))
        save.assert_not_called()
        self.assertIn(MENSAGEM_CONCORRENCIA, str(f.non_field_errors()))
        self.assertEqual(Movimentacao.objects.count(), 0)

    def test_formulario_falha_commit(self):
        """Falha simulada no commit desfaz escrita real e não repete pagamento."""
        c = self.compromisso()
        f = MovimentacaoForm(self.post_movimento(compromisso_financeiro=c.pk), instance=Movimentacao(usuario=self.u))
        # _commit é chamado após save real; a exceção causa rollback real do SQLite.
        with patch.object(connection, "_commit", side_effect=erro_bloqueio()), patch.object(f, "save", wraps=f.save) as save:
            self.assertFalse(salvar_formulario_com_tratamento(f))
        self.assertEqual(save.call_count, 1)
        self.assertEqual(Movimentacao.objects.count(), 0)
        self.acumulado(c, "10")
        self.assertEqual(self.conta.saldo_atual, 100)
        self.assertIn(MENSAGEM_CONCORRENCIA, str(f.non_field_errors()))

    def test_interface_falha_commit_sem_sucesso(self):
        """View conserva POST e exibe erro quando o commit de pagamento falha."""
        self.client.force_login(self.u)
        with patch.object(connection, "_commit", side_effect=erro_bloqueio()):
            r = self.client.post(reverse("financeiro:movimentacao_criar"), self.post_movimento())
        self.assertEqual(r.status_code, 200)
        self.assertIn(MENSAGEM_CONCORRENCIA, str(r.context["form"].errors))
        self.assertFalse(any(m.level == messages.SUCCESS for m in r.context["messages"]))
        self.assertEqual(Movimentacao.objects.count(), 0)

    def test_admin_falha_commit_sem_sucesso_e_com_rollback_auditoria(self):
        """Commit falho no admin desfaz dados/logs e deve retirar sucesso já enfileirado."""
        root = User.objects.create_superuser(username="root", email="root@example.invalid", password="sintetica")
        request = request_admin(root)
        ma = admin.site._registry[Movimentacao]
        def executar():
            m = self.movimento()
            LogEntry.objects.create(user=root, content_type=ContentType.objects.get_for_model(Movimentacao),
                                    object_id=str(m.pk), object_repr="Sintético", action_flag=CHANGE)
            ma.message_user(request, "Sucesso sintético", messages.SUCCESS)
        with patch.object(connection, "_commit", side_effect=erro_bloqueio()):
            resposta = ma._executar_com_tratamento(request, executar)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Movimentacao.objects.count(), 0)
        self.assertEqual(LogEntry.objects.count(), 0)
        avisos = list(request._messages)
        self.assertTrue(any(m.level == messages.ERROR for m in avisos))
        self.assertFalse(any(m.level == messages.SUCCESS for m in avisos), "Rollback não pode anunciar sucesso")

    def test_formulario_erro_desconhecido(self):
        """Erro operacional desconhecido no save propaga e desfaz a transação."""
        f = MovimentacaoForm(self.post_movimento(), instance=Movimentacao(usuario=self.u))
        with patch.object(f, "save", side_effect=OperationalError("Falha sintética desconhecida")), self.assertRaises(OperationalError):
            salvar_formulario_com_tratamento(f)
        self.assertFalse(Movimentacao.objects.exists())

    def test_exclusao_falha_inicio(self):
        """Falha simulada ao iniciar exclusão preserva objeto e emite só erro."""
        from financeiro.concorrencia import excluir_com_tratamento
        m = self.movimento()
        request = request_admin(self.u)
        with patch.object(connection, "_start_transaction_under_autocommit", side_effect=erro_bloqueio()):
            self.assertFalse(excluir_com_tratamento(request, m))
        self.assertTrue(Movimentacao.objects.filter(pk=m.pk).exists())
        self.assertEqual([aviso.level for aviso in request._messages], [messages.ERROR])

    def test_exclusao_falha_commit(self):
        """Falha simulada no commit da exclusão restaura movimento, saldo e acumulado."""
        from financeiro.concorrencia import excluir_com_tratamento
        c = self.compromisso()
        m = self.movimento(compromisso_financeiro=c)
        pk = m.pk
        request = request_admin(self.u)
        with patch.object(connection, "_commit", side_effect=erro_bloqueio()):
            self.assertFalse(excluir_com_tratamento(request, m))
        self.assertTrue(Movimentacao.objects.filter(pk=pk).exists())
        self.acumulado(c, "30")
        self.assertEqual(self.conta.saldo_atual, 80)
        self.assertEqual([aviso.level for aviso in request._messages], [messages.ERROR])

    def test_admin_falha_inicio(self):
        """Admin não executa ação nem emite sucesso quando BEGIN falha."""
        request = request_admin(self.u)
        ma = admin.site._registry[Movimentacao]
        with patch.object(connection, "_start_transaction_under_autocommit", side_effect=erro_bloqueio()), patch.object(Movimentacao, "save") as save:
            resposta = ma._executar_com_tratamento(request, lambda: self.movimento())
        save.assert_not_called()
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual([aviso.level for aviso in request._messages], [messages.ERROR])
