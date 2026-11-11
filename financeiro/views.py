from datetime import datetime
from itertools import cycle

from django.contrib import messages
from django.db.models import F, Q, Sum
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format, number_format
from django.contrib.auth.decorators import login_required
from .concorrencia import salvar_formulario_com_tratamento, excluir_com_tratamento
from .consultas import (
    compromissos_pendentes,
    evolucao_mensal,
    periodo_do_mes,
    saldo_por_conta,
    totais_por_categoria,
)

from .forms import (
    CategoriaForm,
    CompromissoFinanceiroForm,
    ContaForm,
    MovimentacaoForm,
)
from .models import (
    Categoria,
    CompromissoFinanceiro,
    Conta,
    Movimentacao,
    dinheiro,
)
from .decorators import perfil_obrigatorio


def _grafico_por_categoria(usuario, mes, mes_padrao, tipo, cor):
    try:
        mes_selecionado = datetime.strptime(mes, "%Y-%m").date()
    except ValueError:
        mes_selecionado = mes_padrao

    inicio, fim = periodo_do_mes(mes_selecionado)
    totais = totais_por_categoria(usuario, inicio, fim, tipo)
    return inicio.isoformat()[:7], {
        "cores": [cor],
        "horizontal": True,
        "altura": max(288, 32 * len(totais) + 60),
        "categorias": [item["categoria"] for item in totais],
        "series": [{
            "name": f"{tipo.label}s",
            "data": [int(item["total"] * 100) for item in totais],
        }],
    }


def _grafico_saldo_por_conta(usuario):
    saldos = saldo_por_conta(usuario)
    saldos["contas"].sort(key=lambda conta: conta["conta"].casefold())
    cores_positivas = cycle(("primary", "azure", "teal", "indigo", "orange", "green", "yellow"))
    series = []
    cores = []
    detalhes = []

    for conta in saldos["contas"]:
        saldo = conta["saldo"]
        conta["saldo_formatado"] = f"R$ {number_format(saldo, decimal_pos=2, force_grouping=True)}"
        if saldo > 0:
            conta["cor"] = next(cores_positivas)
        elif saldo < 0:
            conta["cor"] = "red"
        else:
            conta["cor"] = "secondary"

        if saldo:
            series.append(int(abs(saldo) * 100))
            cores.append(f"var(--tblr-{conta['cor']})")
            detalhes.append({"conta": conta["conta"], "saldo": conta["saldo_formatado"]})

    return saldos, {"series": series, "cores": cores, "detalhes": detalhes}


def _series_compromissos_em_aberto(usuario, dias):
    grupos = compromissos_pendentes(usuario, dias)
    restante = F("valor_total") - F("valor_pago_recebido")
    totais = [
        grupos[grupo].aggregate(
            pagar=Sum(restante, filter=Q(tipo=CompromissoFinanceiro.Tipo.PAGAR)),
            receber=Sum(restante, filter=Q(tipo=CompromissoFinanceiro.Tipo.RECEBER)),
        )
        for grupo in ("atrasados", "proximos")
    ]

    return [
        {"name": "A pagar", "data": [int(dinheiro(total["pagar"]) * 100) for total in totais]},
        {"name": "A receber", "data": [int(dinheiro(total["receber"]) * 100) for total in totais]},
    ]


# VIEW DA PAGINA INICIAL
@login_required
@perfil_obrigatorio
def inicio(request):
    periodos_mensais = (3, 6, 12)
    periodo_fluxo = request.GET.get("meses_fluxo", "6")
    meses_fluxo = int(periodo_fluxo) if periodo_fluxo in {"3", "6", "12"} else 6
    fluxo = evolucao_mensal(request.usuario, meses=meses_fluxo)

    periodo_resultado = request.GET.get("meses_resultado", "6")
    meses_resultado = int(periodo_resultado) if periodo_resultado in {"3", "6", "12"} else 6
    resultado = fluxo if meses_resultado == meses_fluxo else evolucao_mensal(
        request.usuario, meses=meses_resultado,
    )
    valores_resultado = [int(item["resultado"] * 100) for item in resultado]
    verde = "var(--tblr-green)"
    vermelho = "var(--tblr-red)"

    inicio_mes, fim_mes = periodo_do_mes()
    mes_saidas, dados_saidas = _grafico_por_categoria(
        request.usuario, request.GET.get("mes_saidas", ""), inicio_mes, Movimentacao.Tipo.SAIDA, vermelho,
    )
    mes_entradas, dados_entradas = _grafico_por_categoria(
        request.usuario, request.GET.get("mes_entradas", ""), inicio_mes, Movimentacao.Tipo.ENTRADA, verde,
    )
    saldos_contas, dados_saldos = _grafico_saldo_por_conta(request.usuario)
    prazos_compromissos = (7, 15, 30)
    prazo_compromissos = request.GET.get("dias_compromissos", "7")
    dias_compromissos = {str(dias): dias for dias in prazos_compromissos}.get(prazo_compromissos, 7)
    series_compromissos = _series_compromissos_em_aberto(request.usuario, dias_compromissos)

    contexto = {
        "quantidade_contas": request.usuario.contas.count(),
        "quantidade_categorias": request.usuario.categorias.count(),
        "quantidade_compromissos": request.usuario.compromissos.filter(
            data_vencimento__range=(inicio_mes, fim_mes),
        ).count(),
        "quantidade_movimentacoes": request.usuario.movimentacoes.filter(
            data__range=(inicio_mes, fim_mes),
        ).count(),
        "periodos_mensais": periodos_mensais,
        "meses_fluxo": meses_fluxo,
        "meses_resultado": meses_resultado,
        "dados_fluxo": {
            "cores": [verde, vermelho],
            "meses": [date_format(item["mes"], "M/y") for item in fluxo],
            "series": [
                {"name": "Entradas", "data": [int(item["entradas"] * 100) for item in fluxo]},
                {"name": "Saídas", "data": [int(item["saidas"] * 100) for item in fluxo]},
            ],
        },
        "dados_resultado": {
            "cores": [verde],
            "faixas_cores": [
                {"from": min(-1, min(valores_resultado)), "to": -1, "color": vermelho},
            ],
            "meses": [date_format(item["mes"], "M/y") for item in resultado],
            "series": [
                {"name": "Resultado", "data": valores_resultado},
            ],
        },
        "mes_saidas": mes_saidas,
        "dados_saidas": dados_saidas,
        "mes_entradas": mes_entradas,
        "dados_entradas": dados_entradas,
        "saldos_contas": saldos_contas,
        "dados_saldos": dados_saldos,
        "prazos_compromissos": prazos_compromissos,
        "dias_compromissos": dias_compromissos,
        "tem_compromissos_em_aberto": any(any(serie["data"]) for serie in series_compromissos),
        "dados_compromissos": {
            "cores": [vermelho, verde],
            "meses": ["Vencidos", "A vencer"],
            "series": series_compromissos,
        },
        "filtros_dashboard": tuple(request.GET.lists()),
    }

    return render(
        request,
        "financeiro/inicio.html",
        contexto,
    )


# -------------------------
# CRUD DE CONTAS
# -------------------------


# LISTA AS CONTAS CADASTRADAS
@login_required
@perfil_obrigatorio
def conta_listar(request):
    contas = Conta.objects.filter(usuario=request.usuario).order_by("nome")

    return render(
        request,
        "financeiro/contas/listar.html",
        {"contas": contas},
    )


# DETALHA UMA CONTA
@login_required
@perfil_obrigatorio
def conta_detalhar(request, pk):
    conta = get_object_or_404(
        Conta.objects.select_related("usuario"),
        pk=pk,
        usuario=request.usuario
    )

    movimentacoes = Movimentacao.objects.filter(
        Q(conta_origem=conta)
        | Q(conta_destino=conta)
    ).select_related(
        "conta_origem",
        "conta_destino",
        "categoria",
    ).order_by("-data", "-hora")

    return render(
        request,
        "financeiro/contas/detalhar.html",
        {
            "conta": conta,
            "movimentacoes": movimentacoes,
        },
    )


# CRIA UMA CONTA
@login_required
@perfil_obrigatorio
def conta_criar(request):
    if request.method == "POST":

        form = ContaForm(request.POST, instance=Conta(usuario=request.usuario))

        if salvar_formulario_com_tratamento(form):
            conta = form.instance

            messages.success(
                request,
                "Conta cadastrada com sucesso.",
            )

            return redirect(
                "financeiro:conta_detalhar",
                pk=conta.pk,
            )
    else:
        form = ContaForm(instance=Conta(usuario=request.usuario))

    return render(
        request,
        "form.html",
        {
            "titulo": "Cadastrar conta",
            "form": form,
            "cancelar_url": reverse("financeiro:conta_listar"),
        },
    )


# EDITA UMA CONTA
@login_required
@perfil_obrigatorio
def conta_editar(request, pk):
    conta = get_object_or_404(Conta, pk=pk, usuario=request.usuario)

    if request.method == "POST":
        form = ContaForm(
            request.POST,
            instance=conta,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Conta atualizada com sucesso.",
            )

            return redirect(
                "financeiro:conta_detalhar",
                pk=conta.pk,
            )
    else:
        form = ContaForm(instance=conta)

    return render(
        request,
        "form.html",
        {
            "titulo": "Editar conta",
            "form": form,
            "cancelar_url": reverse(
                "financeiro:conta_detalhar",
                args=[conta.pk],
            ),
        },
    )


# EXCLUI UMA CONTA
@login_required
@perfil_obrigatorio
def conta_excluir(request, pk):
    conta = get_object_or_404(Conta, pk=pk, usuario=request.usuario)

    if request.method == "POST":
        try:
            conta.delete()

            messages.success(
                request,
                "Conta excluída com sucesso.",
            )

            return redirect("financeiro:conta_listar")

        except ProtectedError:
            messages.error(
                request,
                "A conta não pode ser excluída porque possui "
                "movimentações ou compromissos relacionados.",
            )

            return redirect(
                "financeiro:conta_detalhar",
                pk=conta.pk,
            )

    return render(
        request,
        "confirmar_exclusao.html",
        {
            "titulo": "Excluir conta",
            "objeto": conta,
            "cancelar_url": reverse(
                "financeiro:conta_detalhar",
                args=[conta.pk],
            ),
        },
    )

# -------------------------
# CRUD DE CATEGORIAS
# -------------------------


# LISTA AS CATEGORIAS CADASTRADAS
@login_required
@perfil_obrigatorio
def categoria_listar(request):
    categorias = Categoria.objects.filter(
        usuario=request.usuario).order_by("nome")

    return render(
        request,
        "financeiro/categorias/listar.html",
        {"categorias": categorias},
    )


# DETALHA UMA CATEGORIA
@login_required
@perfil_obrigatorio
def categoria_detalhar(request, pk):
    categoria = get_object_or_404(
        Categoria.objects.select_related("usuario"),
        pk=pk,
        usuario=request.usuario,
    )

    return render(
        request,
        "financeiro/categorias/detalhar.html",
        {
            "categoria": categoria,
            "movimentacoes": categoria.movimentacoes.all().order_by(
                "-data",
                "-hora",
            ),
            "compromissos": categoria.compromissos.all().order_by(
                "-data_vencimento"
            ),
        },
    )


# CRIA UMA CATEGORIA
@login_required
@perfil_obrigatorio
def categoria_criar(request):
    if request.method == "POST":
        form = CategoriaForm(
            request.POST, instance=Categoria(usuario=request.usuario))

        if salvar_formulario_com_tratamento(form):
            categoria = form.instance

            messages.success(
                request,
                "Categoria cadastrada com sucesso.",
            )

            return redirect(
                "financeiro:categoria_detalhar",
                pk=categoria.pk,
            )
    else:
        form = CategoriaForm(instance=Categoria(usuario=request.usuario))

    return render(
        request,
        "form.html",
        {
            "titulo": "Cadastrar categoria",
            "form": form,
            "cancelar_url": reverse("financeiro:categoria_listar"),
        },
    )


# EDITA UMA CATEGORIA
@login_required
@perfil_obrigatorio
def categoria_editar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk, usuario=request.usuario)

    if request.method == "POST":
        form = CategoriaForm(
            request.POST,
            instance=categoria,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Categoria atualizada com sucesso.",
            )

            return redirect(
                "financeiro:categoria_detalhar",
                pk=categoria.pk,
            )
    else:
        form = CategoriaForm(instance=categoria)

    return render(
        request,
        "form.html",
        {
            "titulo": "Editar categoria",
            "form": form,
            "cancelar_url": reverse(
                "financeiro:categoria_detalhar",
                args=[categoria.pk],
            ),
        },
    )


# EXCLUI UMA CATEGORIA
@login_required
@perfil_obrigatorio
def categoria_excluir(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk, usuario=request.usuario)

    if request.method == "POST":
        try:
            categoria.delete()

            messages.success(
                request,
                "Categoria excluída com sucesso.",
            )

            return redirect("financeiro:categoria_listar")

        except ProtectedError:
            messages.error(
                request,
                "A categoria não pode ser excluída porque "
                "possui registros relacionados.",
            )

            return redirect(
                "financeiro:categoria_detalhar",
                pk=categoria.pk,
            )

    return render(
        request,
        "confirmar_exclusao.html",
        {
            "titulo": "Excluir categoria",
            "objeto": categoria,
            "cancelar_url": reverse(
                "financeiro:categoria_detalhar",
                args=[categoria.pk],
            ),
        },
    )

# -------------------------
# VIEW DE COMPROMISSOS
# -------------------------


# LISTA OS COMPROMISSOS FINANCEIROS
@login_required
@perfil_obrigatorio
def compromisso_listar(request):
    compromissos = CompromissoFinanceiro.objects.select_related(
        "conta",
        "categoria",
    ).order_by("-data_vencimento").filter(usuario=request.usuario)

    return render(
        request,
        "financeiro/compromissos/listar.html",
        {"compromissos": compromissos},
    )


# DETALHA UM COMPROMISSO FINANCEIRO
@login_required
@perfil_obrigatorio
def compromisso_detalhar(request, pk):
    compromisso = get_object_or_404(
        CompromissoFinanceiro.objects.select_related(
            "usuario",
            "conta",
            "categoria",
        ),
        pk=pk,
        usuario=request.usuario,
    )

    return render(
        request,
        "financeiro/compromissos/detalhar.html",
        {
            "compromisso": compromisso,
            "movimentacoes": compromisso.movimentacoes.all().order_by(
                "-data",
                "-hora",
            ),
        },
    )


# CRIA UM COMPROMISSO FINANCEIRO
@login_required
@perfil_obrigatorio
def compromisso_criar(request):
    if request.method == "POST":
        form = CompromissoFinanceiroForm(
            request.POST, instance=CompromissoFinanceiro(usuario=request.usuario))

        if salvar_formulario_com_tratamento(form):
            compromisso = form.instance

            messages.success(
                request,
                "Compromisso cadastrado com sucesso.",
            )

            return redirect(
                "financeiro:compromisso_detalhar",
                pk=compromisso.pk,
            )
    else:
        form = CompromissoFinanceiroForm(
            instance=CompromissoFinanceiro(usuario=request.usuario))

    return render(
        request,
        "form.html",
        {
            "titulo": "Cadastrar compromisso",
            "form": form,
            "cancelar_url": reverse("financeiro:compromisso_listar"),
        },
    )


# EDITA UM COMPROMISSO FINANCEIRO
@login_required
@perfil_obrigatorio
def compromisso_editar(request, pk):
    compromisso = get_object_or_404(
        CompromissoFinanceiro,
        pk=pk,
        usuario=request.usuario,
    )

    if request.method == "POST":
        form = CompromissoFinanceiroForm(
            request.POST,
            instance=compromisso,
        )

        if salvar_formulario_com_tratamento(form):

            messages.success(
                request,
                "Compromisso atualizado com sucesso.",
            )

            return redirect(
                "financeiro:compromisso_detalhar",
                pk=compromisso.pk,
            )
    else:
        form = CompromissoFinanceiroForm(instance=compromisso)

    return render(
        request,
        "form.html",
        {
            "titulo": "Editar compromisso",
            "form": form,
            "cancelar_url": reverse(
                "financeiro:compromisso_detalhar",
                args=[compromisso.pk],
            ),
        },
    )


# EXCLUI UM COMPROMISSO FINANCEIRO
@login_required
@perfil_obrigatorio
def compromisso_excluir(request, pk):
    compromisso = get_object_or_404(
        CompromissoFinanceiro,
        pk=pk,
        usuario=request.usuario
    )

    if request.method == "POST":
        if excluir_com_tratamento(request, compromisso):
            messages.success(
                request,
                "Compromisso excluído com sucesso.",
            )

        return redirect("financeiro:compromisso_listar")

    return render(
        request,
        "confirmar_exclusao.html",
        {
            "titulo": "Excluir compromisso",
            "objeto": compromisso,
            "cancelar_url": reverse(
                "financeiro:compromisso_detalhar",
                args=[compromisso.pk],
            ),
        },
    )


# REGISTRA PAGAMENTO OU RECEBIMENTO DO COMPROMISSO
@login_required
@perfil_obrigatorio
def compromisso_registrar_movimentacao(request, pk):
    compromisso = get_object_or_404(
        CompromissoFinanceiro.objects.select_related(
            "conta",
            "categoria",
        ),
        pk=pk,
        usuario=request.usuario,
    )

    if compromisso.esta_quitado():
        messages.info(request, "Este compromisso já está quitado.")
        return redirect(
            "financeiro:compromisso_detalhar",
            pk=compromisso.pk,
        )

    if (
        compromisso.conta_id and not compromisso.conta.ativa
    ) or (
        compromisso.categoria_id and not compromisso.categoria.ativa
    ):
        messages.error(
            request,
            "Este compromisso possui conta ou categoria inativa. "
            "Regularize o vínculo antes de registrar a movimentação.",
        )
        return redirect(
            "financeiro:compromisso_detalhar",
            pk=compromisso.pk,
        )

    eh_pagamento = compromisso.tipo == CompromissoFinanceiro.Tipo.PAGAR
    titulo = (
        "Registrar pagamento"
        if eh_pagamento
        else "Registrar recebimento"
    )

    agora = timezone.localtime()

    movimentacao = Movimentacao(
        usuario=request.usuario,
        compromisso_financeiro=compromisso,
        tipo=(
            Movimentacao.Tipo.SAIDA
            if eh_pagamento
            else Movimentacao.Tipo.ENTRADA
        ),
        valor=compromisso.valor_restante(),
        categoria=compromisso.categoria,
        conta_origem=compromisso.conta if eh_pagamento else None,
        conta_destino=compromisso.conta if not eh_pagamento else None,
        descricao=f"{titulo}: {compromisso.titulo}",
        data=agora.date(),
        hora=agora.time().replace(second=0, microsecond=0),
    )

    form = MovimentacaoForm(
        request.POST if request.method == "POST" else None,
        instance=movimentacao,
    )

    form.fields["tipo"].disabled = True
    form.fields["compromisso_financeiro"].disabled = True

    if request.method == "POST" and salvar_formulario_com_tratamento(form):

        messages.success(
            request,
            "Pagamento registrado com sucesso."
            if eh_pagamento
            else "Recebimento registrado com sucesso.",
        )

        return redirect(
            "financeiro:compromisso_detalhar",
            pk=compromisso.pk,
        )

    return render(
        request,
        "form.html",
        {
            "titulo": f"{titulo}: {compromisso.titulo}",
            "form": form,
            "cancelar_url": reverse(
                "financeiro:compromisso_detalhar",
                args=[compromisso.pk],
            ),
        },
    )


# -------------------------
# CRUD DE MOVIMENTACOES
# -------------------------


# LISTA AS MOVIMENTACOES
@login_required
@perfil_obrigatorio
def movimentacao_listar(request):
    movimentacoes = Movimentacao.objects.select_related(
        "conta_origem",
        "conta_destino",
        "categoria",
        "compromisso_financeiro",
    ).order_by("-data", "-hora").filter(usuario=request.usuario)

    return render(
        request,
        "financeiro/movimentacoes/listar.html",
        {"movimentacoes": movimentacoes},
    )


# DETALHA UMA MOVIMENTACAO
@login_required
@perfil_obrigatorio
def movimentacao_detalhar(request, pk):
    movimentacao = get_object_or_404(
        Movimentacao.objects.select_related(
            "usuario",
            "conta_origem",
            "conta_destino",
            "categoria",
            "compromisso_financeiro",
        ),
        pk=pk,
        usuario=request.usuario,
    )

    return render(
        request,
        "financeiro/movimentacoes/detalhar.html",
        {"movimentacao": movimentacao},
    )


# CRIA UMA MOVIMENTACAO
@login_required
@perfil_obrigatorio
def movimentacao_criar(request):
    if request.method == "POST":
        form = MovimentacaoForm(
            request.POST, instance=Movimentacao(usuario=request.usuario))

        if salvar_formulario_com_tratamento(form):
            movimentacao = form.instance

            messages.success(
                request,
                "Movimentação cadastrada com sucesso.",
            )

            return redirect(
                "financeiro:movimentacao_detalhar",
                pk=movimentacao.pk,
            )
    else:
        form = MovimentacaoForm(instance=Movimentacao(usuario=request.usuario))

    return render(
        request,
        "form.html",
        {
            "titulo": "Cadastrar movimentação",
            "form": form,
            "cancelar_url": reverse("financeiro:movimentacao_listar"),
        },
    )


# EDITA UMA MOVIMENTACAO
@login_required
@perfil_obrigatorio
def movimentacao_editar(request, pk):
    movimentacao = get_object_or_404(
        Movimentacao,
        pk=pk,
        usuario=request.usuario,
    )

    if request.method == "POST":
        form = MovimentacaoForm(
            request.POST,
            instance=movimentacao,
        )

        if salvar_formulario_com_tratamento(form):

            messages.success(
                request,
                "Movimentação atualizada com sucesso.",
            )

            return redirect(
                "financeiro:movimentacao_detalhar",
                pk=movimentacao.pk,
            )
    else:
        form = MovimentacaoForm(instance=movimentacao)

    return render(
        request,
        "form.html",
        {
            "titulo": "Editar movimentação",
            "form": form,
            "cancelar_url": reverse(
                "financeiro:movimentacao_detalhar",
                args=[movimentacao.pk],
            ),
        },
    )


# EXCLUI UMA MOVIMENTACAO
@login_required
@perfil_obrigatorio
def movimentacao_excluir(request, pk):
    movimentacao = get_object_or_404(
        Movimentacao,
        pk=pk,
        usuario=request.usuario,
    )

    if request.method == "POST":
        if excluir_com_tratamento(request, movimentacao):
            messages.success(
                request,
                "Movimentação excluída com sucesso.",
            )

        return redirect("financeiro:movimentacao_listar")

    return render(
        request,
        "confirmar_exclusao.html",
        {
            "titulo": "Excluir movimentação",
            "objeto": movimentacao,
            "cancelar_url": reverse(
                "financeiro:movimentacao_detalhar",
                args=[movimentacao.pk],
            ),
        },
    )