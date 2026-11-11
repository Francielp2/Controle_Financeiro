# AVISO: Estes testes foram elaborados com auxílio de Inteligência Artificial.
# Não houve revisão humana individual de todos os casos.
# Sua aprovação não garante ausência de defeitos; revise-os ao mudar as regras.
import json
from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from financeiro import consultas as q
from .base import DadosMixin, HOJE


class ConsultasTests(DadosMixin, TestCase):
    def test_periodos_calendario(self):
        """Calcula fevereiro comum/bissexto e dezembro sem depender da data real."""
        for data, inicio, fim in ((date(2024, 2, 15), date(2024, 2, 1), date(2024, 2, 29)),
                                  (date(2023, 2, 28), date(2023, 2, 1), date(2023, 2, 28)),
                                  (date(2023, 12, 31), date(2023, 12, 1), date(2023, 12, 31))):
            with self.subTest(data=data):
                self.assertEqual(q.periodo_do_mes(data), (inicio, fim))
        self.assertEqual(q.periodo_do_mes(), (HOJE, date(2024, 3, 31)))

    def test_totais_limites_transferencia_isolamento(self):
        """Limites inclusivos e transferências não distorcem entradas e saídas do período."""
        self.movimento(valor=12, data=date(2024, 2, 1))
        self.movimento(valor=8, data=date(2024, 2, 29))
        self.movimento(valor=900, data=date(2024, 1, 31))
        self.movimento(valor=700, data=HOJE)
        self.movimento(tipo="ENTRADA", conta_origem=None, conta_destino=self.conta, categoria=self.entrada, valor=50, data=date(2024, 2, 15))
        self.movimento(tipo="TRANSFERENCIA", categoria=None, conta_destino=self.destino, valor=100, data=date(2024, 2, 10))
        self.movimento(usuario=self.outro, conta_origem=self.alheia, categoria=None, valor=999, data=date(2024, 2, 15))
        inicio, fim = date(2024, 2, 1), date(2024, 2, 29)
        self.assertEqual(q.resumo_periodo(self.u, inicio, fim), {"entradas": Decimal("50"), "saidas": Decimal("20"), "resultado": Decimal("30")})
        self.assertEqual(q.totais_por_categoria(self.u, inicio, fim, "SAIDA"), [{"categoria": "Despesas", "total": Decimal("20")}])
        self.assertEqual(q.movimentacoes_filtradas(self.u, inicio, fim, conta=self.destino).count(), 1)
        self.assertEqual(q.movimentacoes_filtradas(self.u, inicio, fim, categoria=self.cat).count(), 2)
        self.assertFalse(q.movimentacoes_filtradas(self.u, conta=self.alheia).exists())

    def test_saldos_ativas(self):
        """Saldo por conta soma somente contas ativas do proprietário."""
        self.movimento(valor=150)
        self.destino.ativa = False
        self.destino.save()
        self.assertEqual(q.saldo_por_conta(self.u), {"contas": [{"conta": "Principal", "tipo": "Conta corrente", "saldo": Decimal("-50")}], "total": Decimal("-50")})

    def test_evolucao_meses_vazios_e_virada(self):
        """Evolução inclui meses vazios na ordem e atravessa a virada do ano."""
        self.movimento(valor=7, data=date(2023, 12, 31))
        dados = q.evolucao_mensal(self.u, meses=4)
        self.assertEqual([d["mes"] for d in dados], [date(2023, 12, 1), date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1)])
        self.assertEqual([d["resultado"] for d in dados], [Decimal("-7"), 0, 0, 0])
        self.assertEqual(q.evolucao_mensal(self.u, meses=0), [])
        self.assertEqual(len(q.evolucao_mensal(self.u, meses=1)), 1)

    def test_pendencias_limites_e_quitados(self):
        """Pendências incluem hoje e sétimo dia, excluindo quitados e terceiros."""
        atrasado = self.compromisso(data_vencimento=HOJE - timedelta(days=1))
        hoje = self.compromisso()
        limite = self.compromisso(data_vencimento=HOJE + timedelta(days=7))
        self.compromisso(data_vencimento=HOJE + timedelta(days=8))
        self.compromisso(valor_pago_recebido_inicial=100, data_vencimento=HOJE - timedelta(days=1))
        self.compromisso(usuario=self.outro, conta=None, categoria=None)
        resultado = q.compromissos_pendentes(self.u)
        self.assertEqual(list(resultado["atrasados"]), [atrasado])
        self.assertEqual(set(resultado["proximos"]), {hoje, limite})
        self.assertEqual(list(q.compromissos_pendentes(self.u, dias=0)["proximos"]), [hoje])

    def test_ultimas_limites_serializacao(self):
        """Últimas respeitam ordem/limite e produzem estruturas JSON sem Decimal ou objetos."""
        antigo = self.movimento(data=date(2024, 2, 29), categoria=None)
        novo = self.movimento(valor=Decimal("0.01"), categoria=None)
        self.assertEqual(list(q.ultimas_movimentacoes(self.u, 1)), [novo])
        self.assertEqual(list(q.ultimas_movimentacoes(self.u, 0)), [])
        self.assertEqual(list(q.ultimas_movimentacoes(self.u, 20)), [novo, antigo])
        with self.assertRaises(ValueError):
            list(q.ultimas_movimentacoes(self.u, -1))
        dados = q.ultimas_movimentacoes_para_agente(self.u, 1)
        self.assertEqual(dados[0]["valor"], "0.01")
        self.assertEqual(dados[0]["data"], "2024-03-01")
        self.assertIsNone(dados[0]["categoria"])
        self.assertIsNone(dados[0]["conta_destino"])
        self.assertIsNone(dados[0]["compromisso"])
        self.assertEqual(json.loads(json.dumps(dados)), dados)

    def test_serializacao_compromisso_opcionais(self):
        """Serializa inicial/acumulado/restante e relacionamentos opcionais de forma simples."""
        c = self.compromisso(conta=None, categoria=None)
        dados = q.compromisso_para_dict(c)
        self.assertEqual((dados["valor_total"], dados["valor_pago_recebido"], dados["valor_restante"]), ("100.00", "10.00", "90.00"))
        self.assertIsNone(dados["conta"])
        self.assertIsNone(dados["categoria"])
        conjunto = q.compromissos_pendentes_para_agente(self.u)
        self.assertEqual(conjunto, {"atrasados": [], "proximos": [dados]})
        self.assertEqual(json.loads(json.dumps(conjunto)), conjunto)

    def test_sem_dados(self):
        """Ausência de movimentações retorna totais zero e listas vazias."""
        self.assertEqual(q.resumo_periodo(self.u, HOJE, HOJE), dict(entradas=0, saidas=0, resultado=0))
        self.assertEqual(q.totais_por_categoria(self.u, HOJE, HOJE, "SAIDA"), [])
        self.assertEqual(q.ultimas_movimentacoes_para_agente(self.u), [])
