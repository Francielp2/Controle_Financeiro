# AVISO: Estes testes foram elaborados com auxílio de Inteligência Artificial.
# Não houve revisão humana individual de todos os casos.
# Sua aprovação não garante ausência de defeitos; revise-os ao mudar as regras.
"""Disputas reais em SQLite arquivo: sem mocks da lógica e sem sleeps."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from decimal import Decimal
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import connections, transaction, OperationalError
from django.test import TransactionTestCase
from financeiro.models import Movimentacao, CompromissoFinanceiro
from financeiro.concorrencia import eh_erro_de_concorrencia
from .base import DadosMixin


class ConcorrenciaSQLiteTests(DadosMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        db = connections["default"]
        if db.vendor != "sqlite" or "memory" in str(db.settings_dict["NAME"]):
            self.skipTest("Exige SQLite em arquivo: --settings=config.test_settings")
        self.assertEqual(db.settings_dict["OPTIONS"]["transaction_mode"], "IMMEDIATE")

    def disputar(self, *operacoes):
        # A barreira inicia operações com conexões independentes. Apenas erros
        # de validação esperados são retornados; erros imprevistos sobem no future.
        barreira = Barrier(len(operacoes))
        def executar(operacao):
            db = connections["default"]
            db.ensure_connection()
            identidade = id(db.connection)
            try:
                barreira.wait(timeout=8)
                try:
                    operacao()
                    return ("ok", identidade)
                except ValidationError:
                    return ("validacao", identidade)
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=len(operacoes)) as pool:
            futures = [pool.submit(executar, op) for op in operacoes]
            resultados = [f.result(timeout=12) for f in futures]
        self.assertEqual(len({identidade for _, identidade in resultados}), len(operacoes))
        return sorted(status for status, _ in resultados)

    def verificar(self, c, valores, inicial="10"):
        c.refresh_from_db()
        self.assertEqual(sorted(c.movimentacoes.values_list("valor", flat=True)), sorted(Decimal(str(v)) for v in valores))
        self.assertEqual(c.valor_pago_recebido, Decimal(inicial) + sum(Decimal(str(v)) for v in valores))
        self.assertLessEqual(c.valor_pago_recebido, c.valor_total)
        self.assertEqual(self.conta.saldo_atual, 100 - sum(Movimentacao.objects.values_list("valor", flat=True)))

    def test_dois_pagamentos_excedentes(self):
        """Duas conexões disputam restante 90; apenas um pagamento de 60 pode persistir."""
        c = self.compromisso()
        self.assertEqual(self.disputar(lambda: self.movimento(compromisso_financeiro=c, valor=60),
                                      lambda: self.movimento(compromisso_financeiro=c, valor=60)), ["ok", "validacao"])
        self.verificar(c, [60])

    def test_dois_pagamentos_permitidos(self):
        """Pagamentos concorrentes cuja soma cabe no restante persistem uma única vez cada."""
        c = self.compromisso()
        self.assertEqual(self.disputar(lambda: self.movimento(compromisso_financeiro=c, valor=40),
                                      lambda: self.movimento(compromisso_financeiro=c, valor=50)), ["ok", "ok"])
        self.verificar(c, [40, 50])

    def test_duas_edicoes_disputam_restante(self):
        """Edições concorrentes excluem o próprio valor antigo sem ultrapassar o total."""
        c = self.compromisso()
        a, b = self.movimento(compromisso_financeiro=c), self.movimento(compromisso_financeiro=c)
        def editar(m):
            m.valor = 60
            m.save()
        self.assertEqual(self.disputar(lambda: editar(a), lambda: editar(b)), ["ok", "validacao"])
        self.verificar(c, [20, 60])

    def test_trocas_simultaneas(self):
        """Trocas em direções opostas recalculam ambos os compromissos sem perder vínculos."""
        a, b = self.compromisso(), self.compromisso()
        ma, mb = self.movimento(compromisso_financeiro=a, valor=20), self.movimento(compromisso_financeiro=b, valor=30)
        def trocar(m, destino):
            m.compromisso_financeiro = destino
            m.save()
        self.assertEqual(self.disputar(lambda: trocar(ma, b), lambda: trocar(mb, a)), ["ok", "ok"])
        self.verificar(a, [30])
        self.verificar(b, [20])

    def test_reducao_concorre_com_pagamento(self):
        """Reduzir total e pagar usam estado bloqueado; apenas uma alteração incompatível vence."""
        c = self.compromisso()
        antigo = CompromissoFinanceiro.objects.get(pk=c.pk)
        def reduzir():
            antigo.valor_total = 50
            antigo.save(update_fields=["valor_total"])
        self.assertEqual(self.disputar(reduzir, lambda: self.movimento(compromisso_financeiro=c, valor=60)), ["ok", "validacao"])
        c.refresh_from_db()
        if c.valor_total == 50:
            self.verificar(c, [])
        else:
            self.assertEqual(c.valor_total, 100)
            self.verificar(c, [60])

    def test_exclusao_compromisso_concorre_pagamento(self):
        """Excluir compromisso preserva pagamento já confirmado ou rejeita vínculo já excluído."""
        c = self.compromisso()
        pk = c.pk
        # Cada thread possui sua instância, evitando compartilhar mutações Python.
        copia = CompromissoFinanceiro.objects.get(pk=pk)
        resultado = self.disputar(lambda: copia.delete(), lambda: self.movimento(compromisso_financeiro=c, valor=20))
        self.assertIn(resultado, (["ok", "ok"], ["ok", "validacao"]))
        self.assertFalse(CompromissoFinanceiro.objects.filter(pk=pk).exists())
        self.assertFalse(Movimentacao.objects.exclude(compromisso_financeiro=None).exists())
        self.assertEqual(Movimentacao.objects.count(), 1 if resultado == ["ok", "ok"] else 0)
        self.assertEqual(self.conta.saldo_atual, 80 if Movimentacao.objects.exists() else 100)

    def test_exclusao_concorre_edicao(self):
        """Excluir e editar o mesmo pagamento nunca ressuscitam registro ou acumulado."""
        c = self.compromisso()
        m = self.movimento(compromisso_financeiro=c)
        copia = Movimentacao.objects.get(pk=m.pk)
        def editar():
            copia.valor = 30
            copia.save()
        resultado = self.disputar(lambda: m.delete(), editar)
        self.assertIn(resultado, (["ok", "ok"], ["ok", "validacao"]))
        self.verificar(c, [])

    def test_exclusoes_repetidas(self):
        """Duas exclusões da mesma movimentação têm um vencedor e não subtraem duas vezes."""
        c = self.compromisso()
        m = self.movimento(compromisso_financeiro=c)
        copia = Movimentacao.objects.get(pk=m.pk)
        self.assertEqual(self.disputar(lambda: m.delete(), lambda: copia.delete()), ["ok", "validacao"])
        self.verificar(c, [])

    def test_lotes_sobrepostos(self):
        """Lotes do admin com interseção removem a união e preservam o inicial."""
        c = self.compromisso()
        ids = [self.movimento(compromisso_financeiro=c).pk for _ in range(3)]
        ma = admin.site._registry[Movimentacao]
        self.assertEqual(self.disputar(lambda: ma.delete_queryset(None, Movimentacao.objects.filter(pk__in=ids[:2])),
                                      lambda: ma.delete_queryset(None, Movimentacao.objects.filter(pk__in=ids[1:]))), ["ok", "ok"])
        self.verificar(c, [])

    def test_objeto_carregado_antes_de_pagamento(self):
        """Compromisso antigo não permite pagamento além do restante atualizado por outra conexão."""
        c = self.compromisso()
        def pagar():
            try:
                self.movimento(compromisso_financeiro=c, valor=80)
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(pagar).result(timeout=8)
        with self.assertRaises(ValidationError):
            self.movimento(compromisso_financeiro=c, valor=20)
        self.verificar(c, [80])

    def test_timeout_real_bloqueio(self):
        """Conexão independente esgota busy_timeout real sem deixar pagamento parcial."""
        c = self.compromisso()
        def tentar():
            db = connections["default"]
            try:
                with db.cursor() as cursor:
                    cursor.execute("PRAGMA busy_timeout = 100")
                try:
                    self.movimento(compromisso_financeiro=c)
                except OperationalError as erro:
                    return eh_erro_de_concorrencia(erro)
                return False
            finally:
                db.close()
        # IMMEDIATE mantém a reserva enquanto a outra conexão tenta iniciar escrita.
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                self.assertTrue(pool.submit(tentar).result(timeout=5))
        self.verificar(c, [])

    def test_espera_liberacao_bloqueio(self):
        """Operação iniciada sob reserva de escrita termina após liberação sem duplicar."""
        c = self.compromisso()
        tentativa = Event()
        def tentar():
            db = connections["default"]
            def observar(execute, sql, params, many, context):
                if sql.startswith("BEGIN"):
                    tentativa.set()
                return execute(sql, params, many, context)
            try:
                with db.execute_wrapper(observar):
                    self.movimento(compromisso_financeiro=c)
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                futuro = pool.submit(tentar)
                self.assertTrue(tentativa.wait(timeout=5))
                self.assertFalse(futuro.done())
            futuro.result(timeout=8)
        self.verificar(c, [20])

    def test_excluir_pagamento_concorre_novo_pagamento(self):
        """Exclusão de pagamento e novo pagamento mantêm acumulado correto em qualquer ordem."""
        c = self.compromisso()
        m = self.movimento(compromisso_financeiro=c, valor=60)
        resultado = self.disputar(lambda: m.delete(), lambda: self.movimento(compromisso_financeiro=c, valor=50))
        self.assertIn(resultado, (["ok", "ok"], ["ok", "validacao"]))
        self.verificar(c, [50] if resultado == ["ok", "ok"] else [])
