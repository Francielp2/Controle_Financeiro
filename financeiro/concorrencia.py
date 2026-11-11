# ESSE ARQUIVO TRATA CONCORRÊNCIA DE ACESSO AO BANCO DE DADOS EM CASOS DE MULTIPLAS REQUISIÇÕES SIMULTANEAS

from django.core.exceptions import ValidationError
from django.db import OperationalError, transaction
from django.contrib import messages


MENSAGEM_CONCORRENCIA = (
    "Não foi possível concluir porque outra operação está "
    "utilizando os dados. Confira as informações e tente novamente."
)


def eh_erro_de_concorrencia(erro):
    """Identifica disputas conhecidas sem esconder outros erros do banco."""
    causa = erro.__cause__ or erro

    # PROTEÇÃO CONTRA CONCORRÊNCIA — SQLite:
    # códigos básicos 5 e 6 indicam banco ou recurso bloqueado.
    codigo_sqlite = getattr(causa, "sqlite_errorcode", None)

    if codigo_sqlite is not None:
        return (codigo_sqlite & 0xFF) in {5, 6}

    # PROTEÇÃO CONTRA CONCORRÊNCIA — PostgreSQL:
    # falha de serialização, impasse ou bloqueio indisponível.
    codigo_postgres = (
        getattr(causa, "sqlstate", None)
        or getattr(causa, "pgcode", None)
    )

    return codigo_postgres in {"40001", "40P01", "55P03"}


def salvar_formulario_com_tratamento(form):
    """Retorna True somente quando a gravação termina com sucesso."""
    try:
        # PROTEÇÃO CONTRA CONCORRÊNCIA:
        # validação e gravação ficam na mesma transação.
        # Os modelos continuam responsáveis pelos bloqueios dos registros.
        with transaction.atomic():
            if not form.is_valid():
                return False

            form.save()

        return True

    except ValidationError as erro:
        # Uma regra pode falhar durante o save(), mesmo após a primeira
        # validação. Exibe a mensagem geral sem depender de campos editáveis.
        form.add_error(None, erro.messages)
        return False

    except OperationalError as erro:
        # PROTEÇÃO CONTRA CONCORRÊNCIA:
        # trata a disputa somente depois de sair da transação,
        # quando suas alterações já foram desfeitas.
        if not eh_erro_de_concorrencia(erro):
            raise

        form.add_error(None, MENSAGEM_CONCORRENCIA)
        return False


def excluir_com_tratamento(request, objeto):
    """Retorna True somente quando a exclusão termina com sucesso."""
    try:
        # PROTEÇÃO CONTRA CONCORRÊNCIA:
        # os modelos coordenam os bloqueios; esta transação garante
        # que uma falha desfaça toda a operação antes de ser apresentada.
        with transaction.atomic():
            objeto.delete()

        return True

    except ValidationError as erro:
        messages.error(request, " ".join(erro.messages))
        return False

    except OperationalError as erro:
        # PROTEÇÃO CONTRA CONCORRÊNCIA:
        # mostra uma mensagem apenas para disputas conhecidas.
        # Outros erros continuam sendo propagados.
        if not eh_erro_de_concorrencia(erro):
            raise

        messages.error(request, MENSAGEM_CONCORRENCIA)
        return False
