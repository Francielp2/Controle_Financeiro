# AVISO: Estes testes foram elaborados com auxílio de Inteligência Artificial.
# Não houve revisão humana individual de todos os casos.
# Sua aprovação não garante ausência de defeitos; revise-os ao mudar as regras.
"""Configuração isolada: nunca abre o banco de desenvolvimento."""
from .settings import *
import atexit
import shutil
import tempfile
from pathlib import Path

_TEST_DIR = Path(tempfile.mkdtemp(prefix="controle-regressao-"))
atexit.register(shutil.rmtree, _TEST_DIR, ignore_errors=True)
SECRET_KEY = "somente-testes-sinteticos-sem-uso-em-producao"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": _TEST_DIR / "nao-utilizado.sqlite3",
    "TEST": {"NAME": str(_TEST_DIR / "testes.sqlite3")},
    "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 2},
}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
