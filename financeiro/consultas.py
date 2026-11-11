from datetime import timedelta
import calendar
from django.db.models import F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from .models import Movimentacao, CompromissoFinanceiro, Conta, dinheiro


def periodo_do_mes(data=None):
    if data is None:
        data = timezone.localdate()

    inicio = data.replace(day=1)

    ultimo_dia = calendar.monthrange(
        data.year,
        data.month,
    )[1]

    fim = data.replace(day=ultimo_dia)

    return inicio, fim


def movimentacoes_filtradas(
        usuario,
        inicio=None,
        fim=None,
        tipo=None,
        conta=None,
        categoria=None
):
    movimentacoes = Movimentacao.objects.filter(usuario=usuario)

    if inicio is not None:
        movimentacoes = movimentacoes.filter(data__gte=inicio)

    if fim is not None:
        movimentacoes = movimentacoes.filter(data__lte=fim)

    if categoria is not None:
        movimentacoes = movimentacoes.filter(categoria=categoria)

    if tipo is not None:
        movimentacoes = movimentacoes.filter(tipo=tipo)

    if conta is not None:
        movimentacoes = movimentacoes.filter(
            Q(conta_origem=conta) | Q(conta_destino=conta)
        )

    return (
        movimentacoes.select_related(
            "conta_origem",
            "conta_destino",
            "categoria",
            "compromisso_financeiro",
        ).order_by("-data", "-hora")
    )


def valor_para_texto(valor):
    return str(dinheiro(valor))


def movimentacao_para_dict(movimentacao):
    return {
        "id": movimentacao.id,
        "tipo": movimentacao.tipo,
        "tipo_nome": movimentacao.get_tipo_display(),
        "valor": valor_para_texto(movimentacao.valor),
        "descricao": movimentacao.descricao,
        "data": movimentacao.data.isoformat(),
        "hora": movimentacao.hora.isoformat() if movimentacao.hora else None,
        "conta_origem": (
            movimentacao.conta_origem.nome
            if movimentacao.conta_origem
            else None
        ),
        "conta_destino": (
            movimentacao.conta_destino.nome
            if movimentacao.conta_destino
            else None
        ),
        "categoria": (
            movimentacao.categoria.nome
            if movimentacao.categoria
            else None
        ),
        "compromisso": (
            movimentacao.compromisso_financeiro.titulo
            if movimentacao.compromisso_financeiro
            else None
        ),
    }


def compromisso_para_dict(compromisso):
    return {
        "id": compromisso.id,
        "titulo": compromisso.titulo,
        "tipo": compromisso.tipo,
        "tipo_nome": compromisso.get_tipo_display(),
        "valor_total": valor_para_texto(compromisso.valor_total),
        "valor_pago_recebido": valor_para_texto(compromisso.valor_pago_recebido),
        "valor_restante": valor_para_texto(compromisso.valor_restante()),
        "data_vencimento": compromisso.data_vencimento.isoformat(),
        "situacao": compromisso.situacao,
        "situacao_nome": compromisso.situacao_display,
        "conta": compromisso.conta.nome if compromisso.conta else None,
        "categoria": compromisso.categoria.nome if compromisso.categoria else None,
        "pessoa": compromisso.pessoa,
        "descricao": compromisso.descricao,
    }


def resumo_periodo(usuario, inicio, fim):
    resumo = movimentacoes_filtradas(
        usuario,
        inicio,
        fim,
    ).aggregate(
        entradas=Sum(
            "valor",
            filter=Q(tipo=Movimentacao.Tipo.ENTRADA)),

        saidas=Sum(
            "valor",
            filter=Q(tipo=Movimentacao.Tipo.SAIDA)),
    )

    entradas = dinheiro(resumo["entradas"])
    saidas = dinheiro(resumo["saidas"])

    return {
        "entradas": entradas,
        "saidas": saidas,
        "resultado": dinheiro(entradas - saidas),
    }


def saldo_por_conta(usuario):
    contas_ativas = Conta.objects.filter(
        usuario=usuario,
        ativa=True,
    )

    contas = []
    total = dinheiro(0)

    for conta in contas_ativas:
        saldo = dinheiro(conta.saldo_atual)

        contas.append({
            "conta": conta.nome,
            "tipo": conta.get_tipo_display(),
            "saldo": saldo,
        })

        total += saldo

    return {
        "contas": contas,
        "total": dinheiro(total),
    }


def totais_por_categoria(usuario, inicio, fim, tipo):
    dados = (
        movimentacoes_filtradas(
            usuario,
            inicio,
            fim,
            tipo=tipo,
        )

        .values("categoria__nome")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    )

    return [
        {
            "categoria":  item["categoria__nome"] or "Sem categoria",
            "total": dinheiro(item["total"]),
        }
        for item in dados
    ]


def evolucao_mensal(usuario, meses=6):
    hoje = timezone.localdate()

    total_meses = hoje.year * 12 + (hoje.month - 1)
    total_meses -= meses - 1

    ano_inicial, mes_inicial = divmod(total_meses, 12)
    mes_inicial += 1

    inicio = hoje.replace(
        year=ano_inicial,
        month=mes_inicial,
        day=1,
    )

    dados = (
        Movimentacao.objects.filter(
            usuario=usuario,
            data__gte=inicio,
        )
        .annotate(mes=TruncMonth("data"))
        .values("mes")
        .annotate(
            entradas=Sum(
                "valor",
                filter=Q(tipo=Movimentacao.Tipo.ENTRADA)),

            saidas=Sum(
                "valor",
                filter=Q(tipo=Movimentacao.Tipo.SAIDA)),
        )
        .order_by("mes")
    )

    totais = {
        item["mes"]: {
            "entradas": dinheiro(item["entradas"]),
            "saidas": dinheiro(item["saidas"]),
        }
        for item in dados
    }

    resultado = []

    for i in range(meses):
        total = total_meses + i
        ano, mes = divmod(total, 12)
        mes += 1

        data_mes = inicio.replace(
            year=ano,
            month=mes,
            day=1,
        )

        valores = totais.get(
            data_mes,
            {
                "entradas": dinheiro(0),
                "saidas": dinheiro(0),
            },
        )

        resultado.append({
            "mes": data_mes,
            "entradas": dinheiro(valores["entradas"]),
            "saidas": dinheiro(valores["saidas"]),
            "resultado": dinheiro(valores["entradas"] - valores["saidas"]),
        })

    return resultado


def compromissos_pendentes(usuario, dias=7):
    hoje = timezone.localdate()
    limite = hoje + timedelta(days=dias)

    pendentes = CompromissoFinanceiro.objects.filter(
        usuario=usuario,
        valor_pago_recebido__lt=F("valor_total"),
    )

    atrasados = pendentes.filter(
        data_vencimento__lt=hoje,
    ).order_by("data_vencimento")

    proximos = pendentes.filter(
        data_vencimento__range=(hoje, limite),
    ).order_by("data_vencimento")

    return {
        "atrasados": atrasados,
        "proximos": proximos,
    }


def ultimas_movimentacoes(usuario, limite=10):
    return movimentacoes_filtradas(usuario=usuario)[:limite]


def compromissos_pendentes_para_agente(usuario, dias=7):
    compromissos = compromissos_pendentes(usuario, dias)

    return {
        "atrasados": [
            compromisso_para_dict(compromisso)
            for compromisso in compromissos["atrasados"]
        ],

        "proximos": [
            compromisso_para_dict(compromisso)
            for compromisso in compromissos["proximos"]
        ],
    }


def ultimas_movimentacoes_para_agente(usuario, limite=10):
    return [
        movimentacao_para_dict(movimentacao)
        for movimentacao in ultimas_movimentacoes(usuario, limite)
    ]
