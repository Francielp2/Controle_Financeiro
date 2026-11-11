# AVISO: Estes testes foram elaborados com auxílio de Inteligência Artificial.
# Não houve revisão humana individual de todos os casos.
# Sua aprovação não garante ausência de defeitos; revise-os ao mudar as regras.
import json
from unittest.mock import patch
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from financeiro.forms import ContaForm, CategoriaForm, CompromissoFinanceiroForm, MovimentacaoForm
from financeiro.models import Conta, Categoria, CompromissoFinanceiro, Movimentacao
from .base import DadosMixin, HOJE


class FormulariosTests(DadosMixin, TestCase):
    def test_querysets_isolados(self):
        """Cada relacionamento exclui terceiros e novos vínculos inativos."""
        c = self.compromisso()
        self.destino.ativa = False
        self.destino.save()
        form = MovimentacaoForm(instance=Movimentacao(usuario=self.u))
        for campo in ("conta_origem", "conta_destino"):
            self.assertEqual(list(form.fields[campo].queryset), [self.conta])
        self.assertEqual(set(form.fields["categoria"].queryset), {self.cat, self.entrada})
        mapa = json.loads(form.fields["compromisso_financeiro"].widget.attrs["data-categorias-compromissos"])
        self.assertEqual(mapa, {str(c.pk): str(self.cat.pk)})

    def test_inativo_mantido_so_no_campo_original(self):
        """Origem inativa de edição não é oferecida como novo destino."""
        m = self.movimento()
        self.conta.ativa = False
        self.conta.save()
        f = MovimentacaoForm(instance=m)
        self.assertIn(self.conta, f.fields["conta_origem"].queryset)
        self.assertNotIn(self.conta, f.fields["conta_destino"].queryset)

    def test_disabled_conta_categoria_resiste_adulteracao(self):
        """POST não altera saldo inicial nem tipo bloqueados pelo vínculo."""
        self.movimento()
        f = ContaForm(dict(nome="Principal", tipo="CORRENTE", saldo_inicial="999", ativa="on"), instance=self.conta)
        self.assertTrue(f.is_valid(), f.errors)
        f.save()
        self.assertEqual(self.conta.saldo_inicial, 100)
        f = CategoriaForm(dict(nome="Despesas", tipo="ENTRADA", ativa="on"), instance=self.cat)
        self.assertTrue(f.is_valid(), f.errors)
        f.save()
        self.assertEqual(self.cat.tipo, "SAIDA")

    def test_disabled_compromisso_resiste_adulteracao(self):
        """Campos bloqueados usam o inicial do formulário apesar de IDs adulterados."""
        c = self.compromisso()
        self.movimento(compromisso_financeiro=c)
        dados = dict(titulo="Editado", tipo="RECEBER", conta=self.alheia.pk, categoria=self.entrada.pk,
                     valor_total="150", valor_pago_recebido_inicial="999", data_vencimento="2024-03-02")
        f = CompromissoFinanceiroForm(dados, instance=c)
        self.assertTrue(f.is_valid(), f.errors)
        f.save()
        c.refresh_from_db()
        self.assertEqual((c.tipo, c.conta_id, c.categoria_id, c.valor_pago_recebido_inicial, c.titulo),
                         ("PAGAR", self.conta.pk, self.cat.pk, 10, "Editado"))

    def test_datas_edicao_e_estatico(self):
        """Inputs de edição usam ISO e o formulário inclui o script de categoria."""
        m = self.movimento()
        c = self.compromisso()
        self.assertIn('value="2024-03-01"', str(MovimentacaoForm(instance=m)["data"]))
        self.assertIn('value="2024-03-01"', str(CompromissoFinanceiroForm(instance=c)["data_vencimento"]))
        self.assertIn("financeiro/js/categoria_compromisso.js", str(MovimentacaoForm(instance=m).media))


class ViewsTests(DadosMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.u)

    def test_rotas_get_nao_gravam_e_isolam(self):
        """CRUD GET não escreve e IDs alheios ou inexistentes retornam 404."""
        objetos = {"conta": self.conta, "categoria": self.cat,
                   "compromisso": self.compromisso(), "movimentacao": self.movimento()}
        contagens = [m.objects.count() for m in (Conta, Categoria, CompromissoFinanceiro, Movimentacao)]
        for nome, obj in objetos.items():
            for acao in ("listar", "criar", "detalhar", "editar", "excluir"):
                args = [obj.pk] if acao in ("detalhar", "editar", "excluir") else []
                url = reverse(f"financeiro:{nome}_{acao}", args=args)
                with self.subTest(nome=nome, acao=acao):
                    self.assertEqual(self.client.get(url).status_code, 200)
                    if args:
                        self.client.force_login(self.outro)
                        for metodo in (self.client.get, self.client.post):
                            self.assertEqual(metodo(url).status_code, 404)
                            self.assertEqual(metodo(reverse(f"financeiro:{nome}_{acao}", args=[999999])).status_code, 404)
                        self.client.force_login(self.u)
        self.assertEqual(contagens, [m.objects.count() for m in (Conta, Categoria, CompromissoFinanceiro, Movimentacao)])

    def test_login_e_perfil_obrigatorios(self):
        """Anônimos vão ao login e User sem perfil vai ao admin."""
        self.client.logout()
        for nome in ("inicio", "conta_listar", "categoria_criar", "compromisso_criar", "movimentacao_criar"):
            r = self.client.get(reverse(f"financeiro:{nome}"))
            self.assertEqual(r.status_code, 302)
            self.assertIn(reverse("usuarios:login"), r.url)
        user = User.objects.create_user(username="sem-perfil")
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("financeiro:inicio")), reverse("admin:index"), fetch_redirect_response=False)

    def test_listagens_filtram_usuario(self):
        """Listagens e painel retornam apenas os dados do usuário autenticado."""
        c, m = self.compromisso(), self.movimento()
        for nome, chave, esperado in (("conta", "contas", {self.conta, self.destino}), ("categoria", "categorias", {self.cat, self.entrada}),
                                      ("compromisso", "compromissos", {c}), ("movimentacao", "movimentacoes", {m})):
            with self.subTest(nome=nome):
                self.assertEqual(set(self.client.get(reverse(f"financeiro:{nome}_listar")).context[chave]), esperado)
        self.assertEqual(self.client.get(reverse("financeiro:inicio")).context["quantidade_contas"], 2)

    def test_movimento_criar_editar_excluir(self):
        """Fluxo HTTP grava uma vez, edita valor e exclui restaurando o saldo."""
        r = self.client.post(reverse("financeiro:movimentacao_criar"), self.post_movimento())
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Movimentacao.objects.count(), 1)
        self.assertEqual(self.conta.saldo_atual, 80)
        m = Movimentacao.objects.get()
        r = self.client.post(reverse("financeiro:movimentacao_editar", args=[m.pk]), self.post_movimento(valor="30"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Movimentacao.objects.count(), 1)
        self.assertEqual(self.conta.saldo_atual, 70)
        self.assertEqual(self.client.post(reverse("financeiro:movimentacao_excluir", args=[m.pk])).status_code, 302)
        self.assertEqual(self.conta.saldo_atual, 100)

    def test_invalido_preserva_post_sem_gravar(self):
        """Valor inválido ou conta adulterada preserva formulário e não movimenta saldo."""
        for alteracao in (dict(valor="-1"), dict(conta_origem=self.alheia.pk), dict(conta_origem=999999)):
            with self.subTest(alteracao=alteracao):
                dados = self.post_movimento(**alteracao)
                r = self.client.post(reverse("financeiro:movimentacao_criar"), dados)
                self.assertEqual(r.status_code, 200)
                self.assertTrue(r.context["form"].errors)
                self.assertEqual(r.context["form"].data["valor"], dados["valor"])
                self.assertFalse(Movimentacao.objects.exists())
                self.assertFalse(any(m.level == messages.SUCCESS for m in r.context["messages"]))

    def test_save_validation_error_na_interface(self):
        """Validação tardia aparece no formulário sem sucesso ou gravação parcial."""
        with patch.object(Movimentacao, "save", side_effect=ValidationError("Conflito sintético")):
            r = self.client.post(reverse("financeiro:movimentacao_criar"), self.post_movimento())
        self.assertEqual(r.status_code, 200)
        self.assertIn("Conflito sintético", str(r.context["form"].non_field_errors()))
        self.assertFalse(Movimentacao.objects.exists())

    def test_pagamento_preenchimento_parcial_quitado(self):
        """Registrar pagamento preenche restante e ignora adulteração dos campos disabled."""
        c = self.compromisso()
        url = reverse("financeiro:compromisso_registrar_movimentacao", args=[c.pk])
        r = self.client.get(url)
        self.assertEqual(r.context["form"].instance.valor, 90)
        self.assertFalse(Movimentacao.objects.exists())
        r = self.client.post(url, self.post_movimento(tipo="ENTRADA", compromisso_financeiro="99999"))
        self.assertEqual(r.status_code, 302)
        self.acumulado(c, "30")
        m = Movimentacao.objects.get()
        self.assertEqual((m.tipo, m.compromisso_financeiro_id), ("SAIDA", c.pk))
        self.client.post(url, self.post_movimento(valor="70"))
        self.acumulado(c, "100")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.post(url, self.post_movimento(valor="1")).status_code, 302)
        self.assertEqual(Movimentacao.objects.count(), 2)

    def test_pagamento_inativo(self):
        """Conta inativa impede novo pagamento e retorna mensagem de erro."""
        c = self.compromisso()
        self.conta.ativa = False
        self.conta.save()
        url = reverse("financeiro:compromisso_registrar_movimentacao", args=[c.pk])
        for metodo in (self.client.get, self.client.post):
            self.assertEqual(metodo(url).status_code, 302)
        self.assertFalse(Movimentacao.objects.exists())

    def test_exclusao_protegida_mensagem(self):
        """Excluir conta ou categoria vinculada informa erro e mantém os registros."""
        self.movimento()
        for nome, obj in (("conta", self.conta), ("categoria", self.cat)):
            r = self.client.post(reverse(f"financeiro:{nome}_excluir", args=[obj.pk]), follow=True)
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())
            self.assertTrue(any(m.level == messages.ERROR for m in r.context["messages"]))

    def test_csrf_representativo(self):
        """POST financeiro sem token é rejeitado antes de gravar."""
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.u)
        self.assertEqual(client.post(reverse("financeiro:movimentacao_criar"), self.post_movimento()).status_code, 403)
        self.assertFalse(Movimentacao.objects.exists())

    def test_conta_erro_tardio_e_tratado(self):
        """Erro de validação surgido no save da conta deve voltar ao formulário."""
        with patch.object(Conta, "save", side_effect=ValidationError("Conflito sintético")):
            r = self.client.post(reverse("financeiro:conta_criar"), dict(nome="Nova", tipo="CORRENTE", saldo_inicial="0", ativa="on"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("Conflito sintético", str(r.context["form"].errors))
