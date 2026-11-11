# AVISO: Estes testes foram elaborados com auxílio de Inteligência Artificial.
# Não houve revisão humana individual de todos os casos.
# Sua aprovação não garante ausência de defeitos; revise-os ao mudar as regras.
"""JavaScript real no Node com DOM mínimo e, opcionalmente, Chromium nativo."""
import html
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
from unittest import SkipTest
from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase

JS_DIR = Path(__file__).parent / "javascript"


def pagina_navegador():
    """Monta fixture local com scripts reais do Django e formulários comum/admin."""
    scripts = [Path(finders.find(nome)).read_text() for nome in (
        "admin/js/vendor/jquery/jquery.js", "admin/js/jquery.init.js", "admin/js/core.js",
        "admin/js/admin/RelatedObjectLookups.js", "financeiro/js/categoria_compromisso.js")]
    nomes = ["abertura", "selecao", "remocao", "sem_categoria", "indisponivel", "inativa", "adulteracao", "envio", "admin_adicionar_categoria", "admin_adicionar_compromisso"]
    formularios = []
    for nome in nomes:
        formularios.append(f'''<form id="{nome}"><div class="related-widget-wrapper">
<select id="compromisso_{nome}" name="compromisso_financeiro" data-categorias-compromissos='{{"1":"10","2":"20","3":"","4":"999","5":"30"}}'>
<option value=""></option><option value="1" selected>Um</option><option value="2">Dois</option><option value="3">Livre</option><option value="4">Ausente</option><option value="5">Inativa</option></select></div>
<div class="related-widget-wrapper"><select id="categoria_{nome}" name="categoria"><option value=""></option><option value="10">A</option><option value="20">B</option><option value="30" disabled>C</option></select></div></form>''')
    executar = '''document.addEventListener('DOMContentLoaded', () => {
const resultados = {};
for (const [nome, executar] of Object.entries(cenarios)) {
    const formulario = document.getElementById(nome);
    const compromisso = formulario.querySelector('[name="compromisso_financeiro"]');
    const categoria = formulario.querySelector('[name="categoria"]');
    categoria.aviso = categoria.nextElementSibling;
    try { executar({formulario, compromisso, categoria}); resultados[nome] = null; }
    catch (erro) { resultados[nome] = erro.message; }
}
document.getElementById('resultado').textContent = JSON.stringify(resultados);
});'''
    return '<!doctype html><html><head><meta charset="utf-8"></head><body>' + ''.join(formularios) + '<pre id="resultado"></pre>' + ''.join('<script>' + s.replace('</script', '<\\/script') + '</script>' for s in [*scripts, (JS_DIR / "cenarios.js").read_text(), executar]) + '</body></html>'


class JavaScriptDOMTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        node = shutil.which("node")
        if not node:
            raise SkipTest("Node ausente; instalar Node para testes de DOM simulado")
        resultado = subprocess.run([node, str(JS_DIR / "dom_simulado.cjs")], capture_output=True, text=True, timeout=15, check=True)
        cls.resultados = json.loads(resultado.stdout)

    def test_abertura(self):
        """DOM simulado: abertura preenche categoria vinculada."""
        self.assertIsNone(self.resultados["abertura"])

    def test_selecao_troca(self):
        """DOM simulado: troca de compromisso troca e bloqueia categoria."""
        self.assertIsNone(self.resultados["selecao"])

    def test_remocao(self):
        """DOM simulado: remoção restaura opções ativas e limpa seleção."""
        self.assertIsNone(self.resultados["remocao"])

    def test_sem_categoria(self):
        """DOM simulado: compromisso sem categoria permite seleção livre."""
        self.assertIsNone(self.resultados["sem_categoria"])

    def test_indisponivel(self):
        """DOM simulado: categoria ausente informa erro impeditivo."""
        self.assertIsNone(self.resultados["indisponivel"])

    def test_inativa(self):
        """DOM simulado: categoria inativa bloqueia e troca válida limpa erro."""
        self.assertIsNone(self.resultados["inativa"])

    def test_adulteracao(self):
        """DOM simulado: alteração manual mantém categoria do compromisso."""
        self.assertIsNone(self.resultados["adulteracao"])

    def test_envio(self):
        """DOM simulado: campo e opção selecionada permanecem habilitados."""
        self.assertIsNone(self.resultados["envio"])
