const dadosSaldos = JSON.parse(document.getElementById("dados-saldos").textContent);

// Base visual: Traffic sources, da seção Circular charts do Tabler.
const graficoSaldos = new ApexCharts(document.getElementById("grafico-saldos"), {
    chart: {
        type: "pie",
        height: 240,
        fontFamily: "inherit",
        sparkline: { enabled: true },
        animations: { enabled: false },
    },
    series: dadosSaldos.series,
    colors: dadosSaldos.cores,
    stroke: { colors: ["var(--tblr-card-bg)"], width: 2 },
    dataLabels: { enabled: false },
    legend: { show: false },
    tooltip: {
        custom: ({ seriesIndex }) => {
            const detalhe = dadosSaldos.detalhes[seriesIndex];
            const descricao = document.createElement("div");
            const nome = document.createElement("div");
            const saldo = document.createElement("div");

            nome.className = "apexcharts-tooltip-title";
            nome.textContent = detalhe.conta;
            saldo.className = "px-2 py-1 fw-semibold";
            saldo.textContent = detalhe.saldo;
            descricao.append(nome, saldo);
            return descricao;
        },
    },
});

graficoSaldos.render();
