# AVISO: Estes testes foram elaborados com auxílio de Inteligência Artificial.
# Não houve revisão humana individual de todos os casos.
# Sua aprovação não garante ausência de defeitos; revise-os ao mudar as regras.
"""Fábricas sintéticas compartilhadas; nenhum acesso a dados reais."""
from datetime import date, time
from decimal import Decimal
from unittest.mock import patch
from usuarios.models import Usuario
from financeiro.models import Conta, Categoria, CompromissoFinanceiro, Movimentacao

HOJE = date(2024, 3, 1)

def cpf_sintetico(numero):
    base = f"{numero:09d}"
    for tamanho in (9, 10):
        resto = sum(int(n) * (tamanho + 1 - i) for i, n in enumerate(base)) * 10 % 11
        base += str(0 if resto == 10 else resto)
    return base

def usuario(numero=1, **kwargs):
    dados = dict(email=f"pessoa{numero}@example.invalid", cpf=cpf_sintetico(numero),
                 rg=f"TESTE{numero}", telefone="00000000000", first_name="Sintético")
    dados.update(kwargs)
    obj = Usuario(**dados)
    obj.set_password("Senha-sintetica!482")
    obj.save()
    return obj

class DadosMixin:
    def setUp(self):
        super().setUp()
        relogio = patch("django.utils.timezone.localdate", return_value=HOJE)
        relogio.start()
        self.addCleanup(relogio.stop)
        self.u = usuario()
        self.outro = usuario(2)
        self.conta = Conta.objects.create(usuario=self.u, nome="Principal", tipo="CORRENTE", saldo_inicial=100)
        self.destino = Conta.objects.create(usuario=self.u, nome="Reserva", tipo="CAIXINHA")
        self.alheia = Conta.objects.create(usuario=self.outro, nome="Terceiro", tipo="CORRENTE")
        self.cat = Categoria.objects.create(usuario=self.u, nome="Despesas", tipo="SAIDA")
        self.entrada = Categoria.objects.create(usuario=self.u, nome="Receitas", tipo="ENTRADA")

    def compromisso(self, **kwargs):
        dados = dict(usuario=self.u, titulo="Obrigação sintética", tipo="PAGAR",
                     valor_total=Decimal("100"), valor_pago_recebido_inicial=Decimal("10"),
                     data_vencimento=HOJE, conta=self.conta, categoria=self.cat)
        dados.update(kwargs)
        return CompromissoFinanceiro.objects.create(**dados)

    def movimento(self, **kwargs):
        dados = dict(usuario=self.u, tipo="SAIDA", valor=Decimal("20"),
                     data=HOJE, hora=time(12), conta_origem=self.conta, categoria=self.cat)
        dados.update(kwargs)
        return Movimentacao.objects.create(**dados)

    def post_movimento(self, **kwargs):
        dados = dict(tipo="SAIDA", valor="20.00", descricao="Teste", data="2024-03-01",
                     hora="12:00", conta_origem=str(self.conta.pk), conta_destino="",
                     categoria=str(self.cat.pk), compromisso_financeiro="")
        dados.update(kwargs)
        return dados

    def acumulado(self, compromisso, esperado):
        compromisso.refresh_from_db()
        self.assertEqual(compromisso.valor_pago_recebido, Decimal(esperado))
