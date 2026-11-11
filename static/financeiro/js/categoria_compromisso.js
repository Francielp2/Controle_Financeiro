(() => {
    function iniciar() {
        document.querySelectorAll(
            "select[data-categorias-compromissos]"
        ).forEach((compromisso) => {
            const formulario = compromisso.closest("form");
            const categoria = formulario?.querySelector(
                'select[name="categoria"]'
            );

            if (!categoria) {
                return;
            }

            const categorias = JSON.parse(
                compromisso.dataset.categoriasCompromissos
            );

            const aviso = document.createElement("p");
            aviso.setAttribute("role", "status");
            categoria.insertAdjacentElement("afterend", aviso);

            const bloqueiosOriginais = new Map(
                Array.from(categoria.options, (opcao) => [
                    opcao,
                    opcao.disabled,
                ])
            );

            function atualizar(limparCategoriaLivre = false) {
                for (const opcao of categoria.options) {
                    opcao.disabled = bloqueiosOriginais.get(opcao) ?? false;
                }

                categoria.setCustomValidity("");
                aviso.textContent = "";

                const categoriaId = categorias[compromisso.value];

                if (!categoriaId) {
                    if (limparCategoriaLivre) {
                        categoria.value = "";
                    }
                    return;
                }

                const opcaoCorrespondente = Array.from(
                    categoria.options
                ).find((opcao) => opcao.value === categoriaId);

                if (!opcaoCorrespondente || opcaoCorrespondente.disabled) {
                    categoria.value = "";

                    const mensagem = (
                        "A categoria deste compromisso não está disponível " +
                        "para este lançamento. Ela pode estar inativa. " +
                        "Regularize o vínculo antes de salvar."
                    );

                    categoria.setCustomValidity(mensagem);
                    aviso.textContent = mensagem;
                    return;
                }

                categoria.value = categoriaId;

                for (const opcao of categoria.options) {
                    opcao.disabled = opcao.value !== categoriaId;
                }

                aviso.textContent = (
                    "Categoria definida pelo compromisso selecionado."
                );
            }

            compromisso.addEventListener("change", () => atualizar(true));

            // Reforca o preenchimento caso a selecao da categoria seja alterada.
            categoria.addEventListener("change", () => atualizar());

            atualizar();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", iniciar);
    } else {
        iniciar();
    }
})();