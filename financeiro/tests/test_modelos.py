# AVISO: Estes testes foram elaborados com auxílio de Inteligência Artificial.
# Não houve revisão humana individual de todos os casos.
# Sua aprovação não garante ausência de defeitos; revise-os ao mudar as regras.
from datetime import timedelta, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone
from financeiro.models import Conta, Categoria, CompromissoFinanceiro, Movimentacao, dinheiro
from .base import DadosMixin, HOJE


class IntegridadeTests(DadosMixin, TestCase):
    def test_saldos_ciclo_completo(self):
        """Entrada, saída, transferência, edição e exclusão produzem saldos independentes."""
        self.movimento(tipo="ENTRADA", conta_origem=None, conta_destino=self.conta, categoria=self.entrada, valor=50)
        saida = self.movimento(valor=200)
        transferencia = self.movimento(tipo="TRANSFERENCIA", categoria=None, conta_destino=self.destino, valor=25)
        self.assertEqual(self.conta.saldo_atual, Decimal("-75"))
        self.assertEqual(self.destino.saldo_atual, Decimal("25"))
        saida.valor = 100
        saida.save()
        self.assertEqual(self.conta.saldo_atual, Decimal("25"))
        transferencia.delete()
        self.assertEqual(self.conta.saldo_atual, Decimal("50"))
        self.assertEqual(self.destino.saldo_atual, 0)

    def test_unicidade_conta_categoria(self):
        """Nomes ignoram caixa dentro do proprietário e do tipo aplicável."""
        for modelo, dados in ((Conta, dict(nome="PRINCIPAL", tipo="CORRENTE")),
                              (Categoria, dict(nome="DESPESAS", tipo="SAIDA"))):
            with self.subTest(modelo=modelo.__name__), self.assertRaises(ValidationError):
                modelo.objects.create(usuario=self.u, **dados)
        Categoria.objects.create(usuario=self.u, nome="DESPESAS", tipo="ENTRADA")
        Conta.objects.create(usuario=self.outro, nome="Principal", tipo="CORRENTE")

    def test_campos_obrigatorios_choices_precisao(self):
        """Rejeita campos vazios, choices desconhecidos e valores além da precisão."""
        for campo, valor in (("nome", ""), ("nome", "x" * 101), ("tipo", "INVALIDO"),
                             ("saldo_inicial", Decimal("0.001")), ("saldo_inicial", Decimal("10000000000"))):
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ValidationError):
                obj = Conta(usuario=self.u, nome="Nova", tipo="CORRENTE")
                setattr(obj, campo, valor)
                obj.save()
        for valor in (0, -1, Decimal("0.001"), Decimal("10000000000")):
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                self.movimento(valor=valor)

    def test_matriz_relacionamentos_movimentacao(self):
        """Valida contas obrigatórias, proibidas, propriedade e compatibilidade de categoria."""
        casos = [dict(conta_origem=None), dict(conta_destino=self.destino),
                 dict(conta_origem=self.alheia), dict(categoria=self.entrada),
                 dict(tipo="ENTRADA", conta_origem=None, conta_destino=None),
                 dict(tipo="ENTRADA", conta_destino=self.destino),
                 dict(tipo="ENTRADA", conta_origem=None, conta_destino=self.destino),
                 dict(tipo="TRANSFERENCIA", conta_destino=self.conta, categoria=None),
                 dict(tipo="TRANSFERENCIA", conta_destino=self.destino),
                 dict(tipo="TRANSFERENCIA", conta_destino=None, categoria=None),
                 dict(tipo="INVALIDO")]
        for dados in casos:
            with self.subTest(dados=dados), self.assertRaises(ValidationError):
                self.movimento(**dados)
        self.assertEqual(Movimentacao.objects.count(), 0)

    def test_protecao_exclusao(self):
        """Contas e categorias vinculadas não podem ser excluídas individualmente ou em lote."""
        self.movimento()
        for obj in (self.conta, self.cat):
            for lote in (False, True):
                with self.subTest(modelo=type(obj).__name__, lote=lote), self.assertRaises(ProtectedError):
                    (type(obj).objects.filter(pk=obj.pk) if lote else obj).delete()

    def test_bloqueios_conta_categoria(self):
        """Vínculos bloqueiam proprietário, saldo inicial e tipo de categoria."""
        self.compromisso()
        for obj, campo, valor in ((self.conta, "usuario", self.outro), (self.cat, "usuario", self.outro), (self.cat, "tipo", "ENTRADA")):
            with self.subTest(campo=campo), self.assertRaises(ValidationError):
                setattr(obj, campo, valor)
                obj.save()
            obj.refresh_from_db()
        self.conta.saldo_inicial = 200
        self.conta.save()  # Compromisso sozinho não bloqueia o saldo inicial.
        self.movimento()
        self.conta.saldo_inicial = 300
        with self.assertRaises(ValidationError):
            self.conta.save()

    def test_inativos_excecao_por_campo(self):
        """Preserva origem inativa já vinculada, mas proíbe reutilizá-la como destino."""
        mov = self.movimento()
        self.conta.ativa = False
        self.conta.save()
        self.cat.ativa = False
        self.cat.save()
        mov.descricao = "Mantido"
        mov.save()
        with self.assertRaises(ValidationError):
            self.movimento()
        mov.tipo, mov.conta_origem, mov.conta_destino, mov.categoria = "ENTRADA", None, self.conta, None
        with self.assertRaises(ValidationError):
            mov.save()

    def test_limites_datas(self):
        """Hoje e passado são aceitos, futuro é exclusivo dos compromissos."""
        self.movimento(data=HOJE - timedelta(days=1))
        self.movimento(data=HOJE)
        with self.assertRaises(ValidationError):
            self.movimento(data=HOJE + timedelta(days=1))
        self.compromisso(data_vencimento=HOJE + timedelta(days=365))

    def test_padrao_data_local_na_virada_utc(self):
        """O padrão usa a data da Bahia mesmo quando o UTC já está no dia seguinte."""
        # O default guarda a função original; controla-se now, não apenas localdate.
        with timezone.override("America/Bahia"), patch("django.utils.timezone.now", return_value=datetime(2024, 3, 1, 1, tzinfo=dt_timezone.utc)):
            self.assertEqual(Movimentacao().data.isoformat(), "2024-02-29")

    def test_constraints_sem_validacao_modelo(self):
        """UPDATE direto ainda respeita constraints de valor positivo e unicidade."""
        mov = self.movimento()
        c = self.compromisso()
        for modelo, pk, alteracao in ((Movimentacao, mov.pk, {"valor": 0}),
                                     (CompromissoFinanceiro, c.pk, {"valor_total": -1}),
                                     (CompromissoFinanceiro, c.pk, {"valor_pago_recebido": -1}),
                                     (Conta, self.destino.pk, {"nome": "PRINCIPAL"})):
            with self.subTest(alteracao=alteracao), self.assertRaises(IntegrityError), transaction.atomic():
                modelo.objects.filter(pk=pk).update(**alteracao)

    def test_dinheiro(self):
        """Normaliza nulos, negativos e arredondamentos sem aritmética binária esperada."""
        for valor, esperado in ((None, "0.00"), ("1.005", "1.00"), ("1.015", "1.02"), (-5, "-5.00"), (0.1, "0.10")):
            with self.subTest(valor=valor):
                self.assertEqual(dinheiro(valor), Decimal(esperado))


class CompromissosTests(DadosMixin, TestCase):
    def test_pagamento_recebimento_ciclo(self):
        """Inicial não move saldo; pagamentos parciais e integrais recalculam ambos os tipos."""
        for tipo, categoria, movimento_tipo in (("PAGAR", self.cat, "SAIDA"), ("RECEBER", self.entrada, "ENTRADA")):
            with self.subTest(tipo=tipo):
                saldo = self.conta.saldo_atual
                c = self.compromisso(tipo=tipo, categoria=categoria)
                self.assertEqual(self.conta.saldo_atual, saldo)
                kwargs = dict(tipo=movimento_tipo, categoria=categoria, compromisso_financeiro=c)
                if tipo == "RECEBER":
                    kwargs.update(conta_origem=None, conta_destino=self.conta)
                m = self.movimento(**kwargs)
                self.acumulado(c, "30")
                m.valor = 90
                m.save()
                self.acumulado(c, "100")
                self.assertTrue(c.esta_quitado())
                with self.assertRaises(ValidationError):
                    self.movimento(valor=1, **kwargs)
                m.delete()
                self.acumulado(c, "10")
                self.assertEqual(self.conta.saldo_atual, saldo)

    def test_inicial_limites(self):
        """Inicial aceita zero e total, mas nunca negativo ou acima do compromisso."""
        for inicial in (0, 100):
            c = self.compromisso(valor_pago_recebido_inicial=inicial)
            self.acumulado(c, str(inicial))
        for inicial in (-1, 101):
            with self.subTest(inicial=inicial), self.assertRaises(ValidationError):
                self.compromisso(valor_pago_recebido_inicial=inicial)

    def test_situacao_calculada(self):
        """Quitação prevalece sobre vencimento; hoje não conta como atraso."""
        for dias, inicial, esperado in ((-1, 0, "ATRASADO"), (-1, 100, "QUITADO"), (0, 0, "PENDENTE"), (0, 10, "PARCIAL"), (1, 0, "PENDENTE")):
            with self.subTest(dias=dias, inicial=inicial):
                c = self.compromisso(data_vencimento=HOJE + timedelta(days=dias), valor_pago_recebido_inicial=inicial)
                c.status = "INVALIDO"  # Exibição não deve confiar no status persistido.
                self.assertEqual(c.situacao, esperado)

    def test_categoria_obrigatoria_do_compromisso(self):
        """Categoria do compromisso não pode ser omitida ou substituída no pagamento."""
        c = self.compromisso()
        for categoria in (None, self.entrada):
            with self.subTest(categoria=categoria), self.assertRaises(ValidationError):
                self.movimento(compromisso_financeiro=c, categoria=categoria)

    def test_bloqueados_e_editaveis(self):
        """Todos os vínculos e o inicial ficam bloqueados, demais campos continuam editáveis."""
        c = self.compromisso()
        self.movimento(compromisso_financeiro=c)
        for campo, valor in (("usuario", self.outro), ("tipo", "RECEBER"), ("conta", None), ("categoria", None), ("valor_pago_recebido_inicial", 0), ("valor_total", 29)):
            c.refresh_from_db()
            with self.subTest(campo=campo), self.assertRaises(ValidationError):
                setattr(c, campo, valor)
                c.save()
        c.refresh_from_db()
        c.titulo, c.descricao, c.pessoa, c.valor_total = "Novo", "Descrição", "Sintético", 150
        c.data_vencimento = HOJE + timedelta(days=2)
        c.save()
        c.refresh_from_db()
        self.assertEqual((c.titulo, c.descricao, c.pessoa, c.valor_total, c.data_vencimento), ("Novo", "Descrição", "Sintético", 150, HOJE + timedelta(days=2)))

    def test_troca_remocao_e_exclusao_vinculo(self):
        """Troca recalcula os dois compromissos e exclusão preserva movimento e saldo."""
        a, b = self.compromisso(), self.compromisso()
        m = self.movimento(compromisso_financeiro=a)
        m.compromisso_financeiro = b
        m.save()
        self.acumulado(a, "10")
        self.acumulado(b, "30")
        m.compromisso_financeiro = None
        m.save()
        self.acumulado(b, "10")
        m.compromisso_financeiro = a
        m.save()
        a.delete()
        m.refresh_from_db()
        self.assertIsNone(m.compromisso_financeiro)
        self.assertEqual(self.conta.saldo_atual, 80)

    def test_objetos_excluidos_nao_ressuscitam(self):
        """Instâncias antigas de compromisso e movimento rejeitam gravação após exclusão."""
        c = self.compromisso()
        m = self.movimento(compromisso_financeiro=c)
        antigo_m = Movimentacao.objects.get(pk=m.pk)
        antigo_c = CompromissoFinanceiro.objects.get(pk=c.pk)
        m.delete()
        c.delete()
        for antigo in (antigo_m, antigo_c):
            with self.subTest(modelo=type(antigo).__name__), self.assertRaises(ValidationError):
                antigo.save()

    def test_api_antiga_removida(self):
        """Pagamento e recebimento antigos não podem contornar movimentações."""
        for nome in ("registrar_pagamento", "registrar_recebimento"):
            self.assertFalse(hasattr(CompromissoFinanceiro, nome))

    def test_exclusao_queryset_recalcula(self):
        """Exclusão em lote deve preservar inicial e remover pagamentos do acumulado."""
        c = self.compromisso()
        self.movimento(compromisso_financeiro=c)
        self.movimento(compromisso_financeiro=c)
        Movimentacao.objects.filter(compromisso_financeiro=c).delete()
        self.acumulado(c, "10")
        self.assertEqual(self.conta.saldo_atual, 100)


class SalvamentosParciaisTests(DadosMixin, TestCase):
    def test_compromisso_campos_nao_salvos_e_desatualizados(self):
        """Salvar título não sobrescreve total atualizado nem usa inicial só alterado em memória."""
        c = self.compromisso()
        antigo = CompromissoFinanceiro.objects.get(pk=c.pk)
        c.valor_total = 200
        c.save()
        antigo.titulo = "Somente título"
        antigo.valor_pago_recebido_inicial = 99
        antigo.save(update_fields=["titulo"])
        antigo.refresh_from_db()
        self.assertEqual((antigo.valor_total, antigo.valor_pago_recebido, antigo.titulo), (200, 10, "Somente título"))

    def test_compromisso_nome_attname_e_lista_vazia(self):
        """Relacionamentos aceitam nome e attname; lista vazia não valida nem grava."""
        c = self.compromisso()
        for campo, conta in (("conta", self.destino), ("conta_id", self.conta)):
            setattr(c, "conta", conta)
            c.save(update_fields=[campo])
            c.refresh_from_db()
            self.assertEqual(c.conta_id, conta.pk)
        c.valor_total = -1
        with self.assertNumQueries(0):
            c.save(update_fields=[])
        c.refresh_from_db()
        self.assertEqual(c.valor_total, 100)

    def test_movimento_lista_vazia_nao_valida(self):
        """Lista vazia deve ser um no-op mesmo com estado inválido em memória."""
        m = self.movimento()
        m.valor = -1
        m.save(update_fields=[])
        m.refresh_from_db()
        self.assertEqual(m.valor, 20)

    def test_movimento_campos_fora_update_fields(self):
        """Edição apenas de descrição deve validar o valor persistido, não valor descartado."""
        c = self.compromisso()
        m = self.movimento(compromisso_financeiro=c)
        m.valor = 500
        m.descricao = "Somente descrição"
        m.save(update_fields=["descricao"])
        m.refresh_from_db()
        self.assertEqual((m.valor, m.descricao), (20, "Somente descrição"))
        self.acumulado(c, "30")

    def test_movimento_troca_parcial_nome_attname(self):
        """Trocas parciais por nome e attname recalculam ambos os lados."""
        a, b = self.compromisso(), self.compromisso()
        m = self.movimento(compromisso_financeiro=a)
        for campo, destino, origem in (("compromisso_financeiro", b, a), ("compromisso_financeiro_id", a, b)):
            m.compromisso_financeiro = destino
            m.save(update_fields=[campo])
            self.acumulado(destino, "30")
            self.acumulado(origem, "10")

    def test_movimento_parcial_desatualizado_preserva_vinculo(self):
        """Uma cópia antiga editando descrição deve recalcular o vínculo atual persistido."""
        a, b = self.compromisso(), self.compromisso()
        m = self.movimento(compromisso_financeiro=a)
        antigo = Movimentacao.objects.get(pk=m.pk)
        m.compromisso_financeiro = b
        m.save()
        antigo.descricao = "Texto"
        antigo.save(update_fields=["descricao"])
        antigo.refresh_from_db()
        self.assertEqual(antigo.compromisso_financeiro_id, b.pk)
        self.acumulado(a, "10")
        self.acumulado(b, "30")
