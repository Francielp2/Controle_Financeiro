from .acoes import ACOES
from .distribuidor import CONSULTAS


# Retorna os esquemas das duas ferramentas oferecidas ao modelo.
def obter_ferramentas():
    return [
        {
            "type": "function",
            "name": "consultar_financas",
            "description": "Escolhe uma consulta financeira permitida.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {
                        "type": "string",
                        "enum": list(CONSULTAS),
                    },
                    "argumentos_json": {
                        "type": "string",
                        "description": (
                            "Objeto JSON com os filtros da consulta. "
                            "Não inclua usuario."
                        ),
                    },
                },
                "required": ["nome", "argumentos_json"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        {
            "type": "function",
            "name": "propor_acao",
            "description": "Valida e prepara um cadastro para confirmação do usuário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "acao": {
                        "type": "string",
                        "enum": list(ACOES),
                    },
                    "dados_json": {
                        "type": "string",
                        "description": (
                            "Objeto JSON com os campos do formulário. "
                            "Use IDs nos vínculos e não inclua usuario."
                        ),
                    },
                },
                "required": ["acao", "dados_json"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    ]
