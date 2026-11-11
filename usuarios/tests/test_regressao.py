# AVISO: Estes testes foram elaborados com auxílio de Inteligência Artificial.
# Não houve revisão humana individual de todos os casos.
# Sua aprovação não garante ausência de defeitos; revise-os ao mudar as regras.
from unittest.mock import patch
from django.contrib.auth.models import User, AnonymousUser
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import TestCase, RequestFactory, Client
from django.urls import reverse
from usuarios.models import Usuario, erro_validacao_cpf
from usuarios.forms import UsuarioCreationForm, UsuarioUpdateForm, LoginForm
from usuarios.utils import usuario_logado
from financeiro.models import Conta, Movimentacao, CompromissoFinanceiro
from financeiro.tests.base import DadosMixin, usuario, cpf_sintetico


def cadastro(numero=3, **kwargs):
    dados = dict(email=f"pessoa{numero}@example.invalid", first_name="Teste", last_name="Sintético",
                 cpf=cpf_sintetico(numero), rg=f"TESTE{numero}", telefone="(00) 00000-0000",
                 password1="Senha-sintetica!482", password2="Senha-sintetica!482")
    dados.update(kwargs)
    return dados


class ModelosFormulariosTests(DadosMixin, TestCase):
    def test_cpf_classes_invalidas(self):
        """CPF rejeita ausência, comprimento, sequências repetidas e verificadores errados."""
        for cpf in (None, "", "abc", "123", "123456789012", *[str(i) * 11 for i in range(10)], cpf_sintetico(3)[:-1] + "9"):
            with self.subTest(cpf=cpf):
                self.assertIsNotNone(erro_validacao_cpf(cpf))
        cpf = cpf_sintetico(3)
        self.assertIsNone(erro_validacao_cpf(cpf))
        self.assertIsNone(erro_validacao_cpf(f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"))

    def test_normalizacao_save(self):
        """Save limpa máscaras, normaliza e-mail/username e RG sem alterar senha."""
        cpf = cpf_sintetico(3)
        u = usuario(3, email="  NOVO@EXAMPLE.INVALID ", cpf=f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}", rg="ab-12.3", telefone="(00) 00000-0000")
        u.refresh_from_db()
        self.assertEqual((u.email, u.username, u.cpf, u.rg, u.telefone), ("novo@example.invalid", "novo@example.invalid", cpf, "AB123", "00000000000"))
        self.assertTrue(u.check_password("Senha-sintetica!482"))
        self.assertNotEqual(u.password, "Senha-sintetica!482")

    def test_unicidade_email_cpf_rg(self):
        """Duplicidades de CPF, RG normalizado e e-mail sem distinguir caixa são rejeitadas."""
        for dados in (dict(email=self.u.email.upper()), dict(cpf=self.u.cpf), dict(rg=self.u.rg.lower())):
            with self.subTest(dados=dados), self.assertRaises(ValidationError):
                usuario(3, **dados)
        User.objects.create_user(username="administrador", email="reservado@example.invalid")
        with self.assertRaises(ValidationError):
            usuario(3, email="RESERVADO@example.invalid")

    def test_obrigatoriedade_formatos_limites(self):
        """Modelo rejeita e-mail/RG/telefone inválidos e comprimentos fora do contrato."""
        for campo, valor in (("email", ""), ("email", "invalido"), ("rg", "..."), ("rg", "x" * 21),
                             ("telefone", ""), ("telefone", "abc"), ("telefone", "0" * 9), ("telefone", "0" * 12)):
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ValidationError):
                usuario(3, **{campo: valor})
        for numero, tamanho in ((3, 10), (4, 11)):
            self.assertEqual(len(usuario(numero, telefone="0" * tamanho).telefone), tamanho)

    def test_senha_confirmacao_e_validadores(self):
        """Cadastro rejeita confirmação diferente, senha curta, numérica e comum."""
        for p1, p2 in (("Senha-sintetica!482", "outra"), ("abc", "abc"), ("12345678901", "12345678901"), ("password", "password")):
            with self.subTest(senha=p1):
                f = UsuarioCreationForm(cadastro(password1=p1, password2=p2))
                self.assertFalse(f.is_valid())
                self.assertTrue("password2" in f.errors or "password1" in f.errors)

    def test_formulario_cadastro_mascaras_hash(self):
        """Formulário aceita máscaras sintéticas e salva hash da senha validada."""
        cpf = cpf_sintetico(3)
        f = UsuarioCreationForm(cadastro(cpf=f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"))
        self.assertTrue(f.is_valid(), f.errors)
        u = f.save()
        self.assertEqual(u.cpf, cpf)
        self.assertTrue(u.check_password("Senha-sintetica!482"))

    def test_edicao_preserva_senha_privilegios(self):
        """Edição cadastral ignora senha, staff, superusuário e permissões adulterados."""
        original = self.u.password
        f = UsuarioUpdateForm(cadastro(1, first_name="Editado", password="intruso", is_staff="on", is_superuser="on", is_active="", user_permissions=[1]), instance=self.u)
        self.assertTrue(f.is_valid(), f.errors)
        f.save()
        self.u.refresh_from_db()
        self.assertEqual(self.u.password, original)
        self.assertFalse(self.u.is_staff)
        self.assertFalse(self.u.is_superuser)
        self.assertTrue(self.u.is_active)
        self.assertEqual(self.u.first_name, "Editado")
        self.assertFalse(self.u.user_permissions.exists())

    def test_usuario_logado_tipos(self):
        """Resolve perfil apenas quando existe Usuario, independentemente de staff."""
        request = RequestFactory().get("/")
        for autenticado, esperado in ((AnonymousUser(), None), (self.u, self.u), (User.objects.create_user(username="semperfil"), None)):
            request.user = autenticado
            self.assertEqual(usuario_logado(request), esperado)
        self.u.is_superuser = True
        self.u.save()
        request.user = self.u
        self.assertEqual(usuario_logado(request), self.u)

    def test_admin_formularios_gerados(self):
        """Admin gera cadastro/edição com senhas e datas somente leitura."""
        request = RequestFactory().get("/")
        request.user = User.objects.create_superuser(username="root", email="root@example.invalid", password="sintetica")
        ma = admin.site._registry[Usuario]
        cadastro_admin = ma.get_form(request)
        edicao = ma.get_form(request, self.u)
        self.assertIn("password1", cadastro_admin.base_fields)
        self.assertNotIn("date_joined", edicao.base_fields)
        self.assertNotIn("last_login", edicao.base_fields)
        self.assertIn("password", edicao.base_fields)


class UsuariosViewsTests(DadosMixin, TestCase):
    def test_cadastro_publico_nao_eleva_privilegios(self):
        """Cadastro público autentica o novo perfil sem aceitar privilégios do POST."""
        r = self.client.post(reverse("usuarios:usuario_criar"), cadastro(is_staff="on", is_superuser="on"))
        self.assertRedirects(r, reverse("financeiro:inicio"))
        u = Usuario.objects.get(email="pessoa3@example.invalid")
        self.assertFalse(u.is_staff)
        self.assertFalse(u.is_superuser)
        self.assertEqual(int(self.client.session["_auth_user_id"]), u.pk)
        self.assertEqual(Usuario.objects.count(), 3)

    def test_cadastro_get_invalido_cancelamento(self):
        """GET e cadastro inválido não escrevem; formulário mantém o e-mail informado."""
        self.assertEqual(self.client.get(reverse("usuarios:usuario_criar")).status_code, 200)
        r = self.client.post(reverse("usuarios:usuario_criar"), cadastro(cpf="invalido"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("cpf", r.context["form"].errors)
        self.assertEqual(r.context["form"].data["email"], "pessoa3@example.invalid")
        self.assertEqual(Usuario.objects.count(), 2)
        self.assertEqual(r.context["cancelar_url"], reverse("usuarios:login"))

    def test_login_logout_invalido_autenticado(self):
        """Login normaliza caixa/espaços, rejeita credenciais erradas e logout exige POST."""
        url = reverse("usuarios:login")
        self.assertEqual(self.client.post(url, dict(username=self.u.email, password="errada")).status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        r = self.client.post(url, dict(username=" " + self.u.email.upper() + " ", password="Senha-sintetica!482"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.get(reverse("usuarios:logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("usuarios:logout")).status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_rotas_permissoes_terceiros(self):
        """Usuário comum acessa próprio CRUD e recebe 403 no CRUD de terceiros."""
        for nome in ("usuario_listar", "perfil", "usuario_detalhar", "usuario_editar", "usuario_excluir"):
            args = [self.u.pk] if nome in ("usuario_detalhar", "usuario_editar", "usuario_excluir") else []
            self.assertEqual(self.client.get(reverse(f"usuarios:{nome}", args=args)).status_code, 302)
        self.client.force_login(self.u)
        for acao in ("detalhar", "editar", "excluir"):
            self.assertEqual(self.client.get(reverse(f"usuarios:usuario_{acao}", args=[self.u.pk])).status_code, 200)
            for metodo in (self.client.get, self.client.post):
                self.assertEqual(metodo(reverse(f"usuarios:usuario_{acao}", args=[self.outro.pk])).status_code, 403)
                self.assertEqual(metodo(reverse(f"usuarios:usuario_{acao}", args=[999999])).status_code, 404)
        self.assertEqual(self.client.get(reverse("usuarios:usuario_listar")).status_code, 302)
        self.assertEqual(self.client.get(reverse("usuarios:usuario_criar")).status_code, 302)

    def test_staff_cadastra_e_edita_terceiros(self):
        """Staff lista perfis e cadastra outro staff, sem permitir superusuário no POST."""
        self.u.is_staff = True
        self.u.save()
        self.client.force_login(self.u)
        self.assertEqual(self.client.get(reverse("usuarios:usuario_listar")).status_code, 200)
        self.assertEqual(self.client.get(reverse("usuarios:usuario_editar", args=[self.outro.pk])).status_code, 200)
        r = self.client.post(reverse("usuarios:usuario_criar"), cadastro(is_staff="on", is_superuser="on"))
        self.assertEqual(r.status_code, 302)
        criado = Usuario.objects.get(email="pessoa3@example.invalid")
        self.assertTrue(criado.is_staff)
        self.assertFalse(criado.is_superuser)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.u.pk)

    def test_exclusao_usuario_dados_financeiros(self):
        """Exclusão própria remove dados financeiros e autenticação sem afetar terceiros."""
        c = self.compromisso()
        self.movimento(compromisso_financeiro=c)
        self.client.force_login(self.u)
        url = reverse("usuarios:usuario_excluir", args=[self.u.pk])
        self.client.get(url)
        self.assertTrue(Usuario.objects.filter(pk=self.u.pk).exists())
        r = self.client.post(url)
        self.assertRedirects(r, reverse("usuarios:login"))
        self.assertFalse(Usuario.objects.filter(pk=self.u.pk).exists())
        self.assertFalse(Movimentacao.objects.exists())
        self.assertFalse(CompromissoFinanceiro.objects.exists())
        self.assertTrue(Conta.objects.filter(pk=self.alheia.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_exclusao_rollback(self):
        """Falha no fim da exclusão restaura usuário, movimentos, compromissos e contas."""
        c = self.compromisso()
        m = self.movimento(compromisso_financeiro=c)
        self.client.force_login(self.u)
        with patch.object(Usuario, "delete", side_effect=RuntimeError("Falha sintética")), self.assertRaises(RuntimeError):
            self.client.post(reverse("usuarios:usuario_excluir", args=[self.u.pk]))
        self.assertTrue(Usuario.objects.filter(pk=self.u.pk).exists())
        self.assertTrue(Movimentacao.objects.filter(pk=m.pk).exists())
        self.assertTrue(Conta.objects.filter(pk=self.conta.pk).exists())
        self.acumulado(c, "30")

    def test_csrf_cadastro(self):
        """Cadastro público sem CSRF não cria usuário."""
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("usuarios:usuario_criar"), cadastro()).status_code, 403)
        self.assertEqual(Usuario.objects.count(), 2)

    def test_perfil_sem_usuario(self):
        """User sem extensão financeira recebe redirecionamento ao admin."""
        self.client.force_login(User.objects.create_user(username="semperfil"))
        self.assertRedirects(self.client.get(reverse("usuarios:perfil")), reverse("admin:index"), fetch_redirect_response=False)

    def test_cadastro_erro_save_tratado(self):
        """Validação tardia de unicidade deve reapresentar cadastro em vez de erro 500."""
        with patch.object(Usuario, "save", side_effect=ValidationError("Duplicidade concorrente")):
            r = self.client.post(reverse("usuarios:usuario_criar"), cadastro())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors)

    def test_edicao_http_preserva_senha(self):
        """Editar cadastro via HTTP mantém senha e ignora privilégios injetados."""
        self.client.force_login(self.u)
        hash_anterior = self.u.password
        resposta = self.client.post(reverse("usuarios:usuario_editar", args=[self.u.pk]),
                                    cadastro(1, first_name="Alterado", is_superuser="on", password="alterada"))
        self.assertEqual(resposta.status_code, 302)
        self.u.refresh_from_db()
        self.assertEqual(self.u.first_name, "Alterado")
        self.assertEqual(self.u.password, hash_anterior)
        self.assertFalse(self.u.is_superuser)

    def test_email_espacos_caixa_formulario(self):
        """Cadastro normaliza espaços e caixa no e-mail recebido pelo formulário."""
        resposta = self.client.post(reverse("usuarios:usuario_criar"), cadastro(email="  NOVO@EXAMPLE.INVALID  "))
        self.assertEqual(resposta.status_code, 302)
        criado = Usuario.objects.get(email="novo@example.invalid")
        self.assertEqual(criado.username, "novo@example.invalid")

    def test_rg_duplicado_normalizado_sem_erro_500(self):
        """RG já cadastrado em outra caixa deve produzir erro de formulário, sem exceção tardia."""
        # Não há mock: is_valid verifica RG antes da normalização feita no save.
        resposta = self.client.post(reverse("usuarios:usuario_criar"), cadastro(rg=self.u.rg.lower()))
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].errors)
        self.assertEqual(Usuario.objects.count(), 2)

    def test_login_inativo(self):
        """Perfil inativo não autentica mesmo com senha correta."""
        self.u.is_active = False
        self.u.save()
        r = self.client.post(reverse("usuarios:login"), dict(username=self.u.email, password="Senha-sintetica!482"))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_staff_exclui_terceiro_mantem_sessao(self):
        """Staff exclui terceiro e retorna à listagem mantendo sua própria sessão."""
        self.u.is_staff = True
        self.u.save()
        self.client.force_login(self.u)
        resposta = self.client.post(reverse("usuarios:usuario_excluir", args=[self.outro.pk]))
        self.assertRedirects(resposta, reverse("usuarios:usuario_listar"))
        self.assertFalse(Usuario.objects.filter(pk=self.outro.pk).exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.u.pk)
