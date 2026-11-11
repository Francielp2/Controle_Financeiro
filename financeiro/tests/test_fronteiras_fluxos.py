# AVISO: Estes testes foram elaborados com auxílio de Inteligência Artificial.
# Não houve revisão humana individual de todos os casos.
# Sua aprovação não garante ausência de defeitos; revise-os ao mudar as regras.
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase
from django.urls import reverse
from financeiro.models import Conta, Categoria, CompromissoFinanceiro, Movimentacao
from .base import DadosMixin, HOJE


class FronteirasTests(DadosMixin, TestCase):
    def test_maior_valor_e_menor_centavo(self):
        """Aceita maior valor representável e menor centavo positivo sem arredondar indevidamente."""
        self.movimento(valor=Decimal("9999999999.99"))
        self.movimento(valor=Decimal("0.01"))
        self.assertEqual(self.conta.saldo_atual, Decimal("-9999999900.00"))

    def test_campos_texto_tamanhos(self):
        """Comprimentos máximos são aceitos e o primeiro caractere excedente é rejeitado."""
        for modelo, dados, campo, tamanho in (
            (Conta, dict(usuario=self.u, tipo="CORRENTE"), "nome", 100),
            (Categoria, dict(usuario=self.u, tipo="SAIDA"), "nome", 100),
            (CompromissoFinanceiro, dict(usuario=self.u, tipo="PAGAR", valor_total=1, data_vencimento=HOJE), "titulo", 150),
            (Movimentacao, dict(usuario=self.u, tipo="SAIDA", valor=1, conta_origem=self.conta, data=HOJE), "descricao", 255)):
            with self.subTest(modelo=modelo.__name__):
                obj = modelo.objects.create(**dados, **{campo: "x" * tamanho})
                self.assertEqual(len(getattr(obj, campo)), tamanho)
                setattr(obj, campo, "x" * (tamanho + 1))
                with self.assertRaises(ValidationError):
                    obj.save()

    def test_compromisso_relacionamentos_incompativeis(self):
        """Compromisso recusa proprietário alheio, tipo de categoria incompatível e escolhas inválidas."""
        cat_alheia = Categoria.objects.create(usuario=self.outro, nome="Outra", tipo="SAIDA")
        for dados in (dict(conta=self.alheia), dict(categoria=cat_alheia), dict(categoria=self.entrada),
                      dict(tipo="RECEBER"), dict(tipo="INVALIDO"), dict(valor_total=0), dict(titulo="")):
            with self.subTest(dados=dados), self.assertRaises(ValidationError):
                self.compromisso(**dados)

    def test_movimento_compromisso_incompativel(self):
        """Movimento recusa compromisso de terceiro, tipo incompatível, conta divergente ou transferência vinculada."""
        c = self.compromisso()
        alheio = self.compromisso(usuario=self.outro, conta=self.alheia, categoria=None)
        receber = self.compromisso(tipo="RECEBER", categoria=self.entrada)
        for dados in (dict(compromisso_financeiro=alheio), dict(compromisso_financeiro=receber),
                      dict(compromisso_financeiro=c, conta_origem=self.destino),
                      dict(compromisso_financeiro=c, tipo="TRANSFERENCIA", categoria=None, conta_destino=self.destino)):
            with self.subTest(dados=dados), self.assertRaises(ValidationError):
                self.movimento(**dados)

    def test_compromisso_inativo_mantido_novo_proibido(self):
        """Compromisso mantém seus vínculos desativados, mas cadastro não pode adotá-los."""
        c = self.compromisso()
        self.conta.ativa = self.cat.ativa = False
        self.conta.save()
        self.cat.save()
        c.titulo = "Editado"
        c.save()
        with self.assertRaises(ValidationError):
            self.compromisso()
        c.conta = c.categoria = None
        c.save()
        c.refresh_from_db()
        self.assertIsNone(c.conta)
        self.assertIsNone(c.categoria)

    def test_exclusao_obsoleta_usa_vinculo_atual(self):
        """Excluir cópia anterior à troca recalcula o compromisso atual e não o antigo."""
        a, b = self.compromisso(), self.compromisso()
        m = self.movimento(compromisso_financeiro=a)
        copia = Movimentacao.objects.get(pk=m.pk)
        m.compromisso_financeiro = b
        m.save()
        copia.delete()
        self.acumulado(a, "10")
        self.acumulado(b, "10")
        self.assertEqual(self.conta.saldo_atual, 100)

    def test_rollback_edicao_excedente(self):
        """Edição excedente não muda movimento, saldo nem acumulado."""
        c = self.compromisso()
        m = self.movimento(compromisso_financeiro=c)
        m.valor = 91
        with self.assertRaises(ValidationError):
            m.save()
        m.refresh_from_db()
        self.assertEqual(m.valor, 20)
        self.acumulado(c, "30")
        self.assertEqual(self.conta.saldo_atual, 80)

    def test_rollback_troca_excedente(self):
        """Troca para compromisso sem restante mantém vínculo e os dois acumulados."""
        a = self.compromisso()
        b = self.compromisso(valor_pago_recebido_inicial=90)
        m = self.movimento(compromisso_financeiro=a)
        m.compromisso_financeiro = b
        with self.assertRaises(ValidationError):
            m.save()
        m.refresh_from_db()
        self.assertEqual(m.compromisso_financeiro_id, a.pk)
        self.acumulado(a, "30")
        self.acumulado(b, "90")

    def test_update_fields_nao_persiste_relacao_invalida(self):
        """Salvamento parcial valida o estado que será persistido, evitando saída com destino."""
        m = self.movimento()
        # Em memória é uma entrada válida; apenas destino seria escrito, deixando
        # no banco uma saída com origem E destino. A validação precisa rejeitar isso.
        m.tipo = "ENTRADA"
        m.conta_origem = None
        m.conta_destino = self.destino
        m.categoria = self.entrada
        with self.assertRaises(ValidationError):
            m.save(update_fields=["conta_destino"])
        m.refresh_from_db()
        self.assertIsNone(m.conta_destino)

    def test_compromisso_parcial_inicial_recalcula_derivados(self):
        """Alterar só inicial recalcula acumulado/status e não altera saldo bancário."""
        c = self.compromisso()
        c.valor_pago_recebido_inicial = 100
        c.save(update_fields=["valor_pago_recebido_inicial"])
        c.refresh_from_db()
        self.assertEqual((c.valor_pago_recebido, c.status), (100, "QUITADO"))
        self.assertEqual(self.conta.saldo_atual, 100)

    def test_compromisso_lista_vazia_excluido(self):
        """No-op parcial não ressuscita compromisso já removido por outra instância."""
        c = self.compromisso()
        CompromissoFinanceiro.objects.get(pk=c.pk).delete()
        with self.assertNumQueries(0):
            c.save(update_fields=[])
        self.assertFalse(CompromissoFinanceiro.objects.exists())

    def test_rollback_transacao_explicita(self):
        """Falha posterior ao pagamento desfaz movimento e recálculo na mesma transação."""
        c = self.compromisso()
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.movimento(compromisso_financeiro=c)
                raise RuntimeError("Falha sintética")
        self.acumulado(c, "10")
        self.assertFalse(Movimentacao.objects.exists())
        self.assertEqual(self.conta.saldo_atual, 100)


class FluxosCRUDTests(DadosMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.u)

    def test_conta_categoria_crud(self):
        """CRUD completo de conta/categoria grava uma vez e permite exclusão sem vínculos."""
        for nome, modelo, dados in (("conta", Conta, dict(nome="Nova", tipo="CORRENTE", saldo_inicial="-1", ativa="on")),
                                    ("categoria", Categoria, dict(nome="Nova", tipo="ENTRADA", descricao="Texto", ativa="on"))):
            antes = modelo.objects.count()
            r = self.client.post(reverse(f"financeiro:{nome}_criar"), dados)
            self.assertEqual(r.status_code, 302)
            self.assertEqual(modelo.objects.count(), antes + 1)
            obj = modelo.objects.get(nome="Nova")
            dados["nome"] = "Editada"
            self.assertEqual(self.client.post(reverse(f"financeiro:{nome}_editar", args=[obj.pk]), dados).status_code, 302)
            obj.refresh_from_db()
            self.assertEqual(obj.nome, "Editada")
            self.assertEqual(self.client.post(reverse(f"financeiro:{nome}_excluir", args=[obj.pk])).status_code, 302)
            self.assertEqual(modelo.objects.count(), antes)

    def test_compromisso_receber_fluxo_completo(self):
        """Cadastro, edição, recebimento parcial e exclusão preservam saldo e movimento."""
        dados = dict(titulo="Receita", tipo="RECEBER", conta=self.conta.pk, categoria=self.entrada.pk,
                     valor_total="200", valor_pago_recebido_inicial="50", data_vencimento="2024-03-03")
        self.assertEqual(self.client.post(reverse("financeiro:compromisso_criar"), dados).status_code, 302)
        c = CompromissoFinanceiro.objects.get()
        self.assertEqual(self.conta.saldo_atual, 100)
        dados["titulo"] = "Receita editada"
        self.assertEqual(self.client.post(reverse("financeiro:compromisso_editar", args=[c.pk]), dados).status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.titulo, "Receita editada")
        url = reverse("financeiro:compromisso_registrar_movimentacao", args=[c.pk])
        f = self.client.get(url).context["form"]
        self.assertEqual((f.instance.tipo, f.instance.valor, f.instance.conta_destino_id), ("ENTRADA", 150, self.conta.pk))
        post = self.post_movimento(tipo="ENTRADA", conta_origem="", conta_destino=self.conta.pk, categoria=self.entrada.pk, valor="60")
        self.assertEqual(self.client.post(url, post).status_code, 302)
        self.acumulado(c, "110")
        self.assertEqual(self.conta.saldo_atual, 160)
        self.assertEqual(self.client.post(reverse("financeiro:compromisso_excluir", args=[c.pk])).status_code, 302)
        m = Movimentacao.objects.get()
        self.assertIsNone(m.compromisso_financeiro_id)
        self.assertEqual(self.conta.saldo_atual, 160)

    def test_categoria_erro_tardio_tratado(self):
        """Categoria com ValidationError no save deve reapresentar dados, sem erro 500."""
        with patch.object(Categoria, "save", side_effect=ValidationError("Conflito sintético")):
            r = self.client.post(reverse("financeiro:categoria_criar"), dict(nome="Nova", tipo="SAIDA", ativa="on"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors)
