# Sistema Web de Controle Financeiro

Sistema web desenvolvido em Python e Django para apoiar o controle financeiro pessoal. O projeto tem como objetivo centralizar o acompanhamento de finanças, servindo como base para funcionalidades como organização de receitas, despesas, categorias e relatórios.

Este repositório contém a estrutura inicial da aplicação Django, a configuração do projeto, dependências e documentação de apoio com diagramas.

## Sumário

- [Sobre o projeto](#sobre-o-projeto)
- [Tecnologias utilizadas](#tecnologias-utilizadas)
- [Funcionalidades previstas](#funcionalidades-previstas)
- [Pré-requisitos](#pré-requisitos)
- [Como executar o projeto](#como-executar-o-projeto)
- [Acesso ao painel administrativo](#acesso-ao-painel-administrativo)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Documentação técnica](#documentação-técnica)
- [Comandos úteis](#comandos-úteis)
- [Boas práticas de configuração](#boas-práticas-de-configuração)

## Sobre o projeto

O **Sistema Web de Controle Financeiro** foi criado para a disciplina de PSW e utiliza o framework Django para fornecer uma base segura, organizada e escalável para uma aplicação financeira.

No estado atual, o projeto possui:

- Configuração inicial do Django.
- Banco de dados SQLite para desenvolvimento local.
- Painel administrativo padrão do Django.
- Arquivo de dependências Python.
- Arquivo de exemplo para variáveis de ambiente.
- Diagramas de caso de uso e de classes na pasta `docs/`.

## Tecnologias utilizadas

- Python 3.12
- Django 6.1
- SQLite
- Git
- GitHub

## Funcionalidades previstas

O sistema foi planejado para apoiar o gerenciamento de finanças pessoais. As funcionalidades esperadas para evolução do projeto incluem:

- Cadastro e autenticação de usuários.
- Registro de receitas.
- Registro de despesas.
- Classificação de movimentações por categoria.
- Consulta de saldo financeiro.
- Visualização de histórico financeiro.
- Relatórios e indicadores de receitas e despesas.
- Administração dos dados pelo painel administrativo do Django.

## Pré-requisitos

Antes de executar o projeto, verifique se você possui os seguintes itens instalados:

- Python 3.12 ou superior.
- Git.
- `pip`, gerenciador de pacotes do Python.
- Ambiente virtual Python, recomendado para isolar as dependências do projeto.

## Como executar o projeto

Clone o repositório:

```bash
git clone URL_DO_REPOSITORIO
```

Acesse a pasta do projeto:

```bash
cd Projeto_Final_PSW_Controle_Financeiro
```

Crie um ambiente virtual:

```bash
python3 -m venv venv
```

Ative o ambiente virtual:

```bash
source venv/bin/activate
```

No Windows, use:

```bash
venv\Scripts\activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Crie o arquivo `.env` com base no arquivo de exemplo:

```bash
cp .env.example .env
```

Execute as migrações do banco de dados:

```bash
python manage.py migrate
```

Inicie o servidor de desenvolvimento:

```bash
python manage.py runserver
```

Acesse a aplicação no navegador:

```text
http://127.0.0.1:8000/
```

## Acesso ao painel administrativo

O projeto já possui a rota padrão do painel administrativo do Django:

```text
http://127.0.0.1:8000/admin/
```

Para acessar o painel, crie um superusuário:

```bash
python manage.py createsuperuser
```

Informe usuário, e-mail e senha quando solicitado. Depois, execute o servidor e acesse `/admin/`.

## Estrutura do projeto

```text
Projeto_Final_PSW_Controle_Financeiro/
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── docs/
│   └── diagramas/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

Principais arquivos:

- `manage.py`: utilitário de linha de comando do Django.
- `config/settings.py`: configurações principais do projeto.
- `config/urls.py`: configuração das rotas da aplicação.
- `requirements.txt`: dependências necessárias para executar o projeto.
- `.env.example`: modelo para variáveis de ambiente.
- `docs/diagramas/`: diagramas técnicos do sistema.

## Documentação técnica

A pasta `docs/diagramas/` contém arquivos de apoio à modelagem do sistema:

- Diagrama de casos de uso.
- Diagrama de classes.
- Versões em `.drawio`, `.pdf` e `.png`.

Esses arquivos ajudam a entender os atores, responsabilidades e entidades previstas para a evolução do sistema.

## Comandos úteis

Verificar se a configuração do Django está válida:

```bash
python manage.py check
```

Criar novas migrações após alterações nos modelos:

```bash
python manage.py makemigrations
```

Aplicar migrações no banco de dados:

```bash
python manage.py migrate
```

Executar o servidor local:

```bash
python manage.py runserver
```

Criar usuário administrador:

```bash
python manage.py createsuperuser
```

## Boas práticas de configuração

- Não versionar arquivos sensíveis, como `.env` e `db.sqlite3`.
- Manter o ambiente virtual fora do controle de versão.
- Usar o arquivo `.env.example` apenas como referência.
- Alterar a `SECRET_KEY` em ambientes reais de produção.
- Desativar `DEBUG` em produção.
- Configurar `ALLOWED_HOSTS` corretamente antes de publicar o sistema.

## Status do projeto

Projeto em desenvolvimento acadêmico. A base Django está criada e pronta para receber os aplicativos internos responsáveis pelas regras de negócio do controle financeiro.
