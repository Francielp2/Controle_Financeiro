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
        ).order_by("-data", "-hora")
    )


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
