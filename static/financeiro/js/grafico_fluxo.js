const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const formatarCentavos = (valor) => moeda.format(valor / 100);

// Bases visuais do Tabler: Traffic summary e Horizontal bars.
for (const elemento of document.querySelectorAll("[data-grafico-barras]")) {
    const dados = JSON.parse(document.getElementById(elemento.dataset.graficoBarras).textContent);
    const horizontal = dados.horizontal ?? false;
    const grafico = new ApexCharts(elemento, {
        chart: {
            type: "bar",
            fontFamily: "inherit",
            foreColor: "var(--tblr-secondary-color)",
            height: dados.altura ?? 288,
            parentHeightOffset: 0,
            toolbar: { show: false },
            animations: { enabled: false },
        },
        colors: dados.cores,
        plotOptions: {
            bar: { horizontal, columnWidth: "50%", colors: { ranges: dados.faixas_cores ?? [] } },
        },
        dataLabels: { enabled: false },
        grid: { borderColor: "var(--tblr-border-color)", strokeDashArray: 4 },
        series: dados.series,
        xaxis: horizontal
            ? { categories: dados.categorias, labels: { formatter: formatarCentavos }, tooltip: { enabled: false } }
            : { categories: dados.meses },
        yaxis: horizontal ? {} : { labels: { formatter: formatarCentavos } },
        tooltip: { x: { show: !horizontal }, y: { formatter: formatarCentavos } },
    });

    grafico.render();
}
