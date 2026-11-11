(() => {
    const formulario = document.getElementById("form-chat");
    const campo = document.getElementById("mensagem");
    const mensagens = document.getElementById("mensagens");
    const historico = document.getElementById("historico-chat");
    const estadoVazio = document.getElementById("estado-chat");
    const aguardando = document.getElementById("chat-aguardando");
    const botaoEnviar = document.getElementById("enviar");
    const ocultarHistorico = document.getElementById("ocultar-historico");
    const tarefaId = document.getElementById("tarefa-id").value;
    const csrf = formulario.querySelector("[name=csrfmiddlewaretoken]").value;

    function rolarParaUltimaMensagem() {
        historico.scrollTop = historico.scrollHeight;
    }

    function enviarJson(url, dados) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrf,
            },
            body: JSON.stringify(dados),
        });
    }

    ocultarHistorico.addEventListener("click", () => {
        mensagens.replaceChildren();
        estadoVazio.classList.remove("d-none");
        ocultarHistorico.disabled = true;
    });

    function mostrarMensagem(remetente, texto) {
        const linha = document.createElement("div");
        const enviada = remetente === "Você";
        linha.className = enviada ? "row g-0 justify-content-end" : "row g-0";

        const coluna = document.createElement("div");
        coluna.className = "col-11 col-lg-9";

        const balao = document.createElement("div");
        balao.className = enviada ? "chat-bubble chat-bubble-me" : "chat-bubble";

        const nome = document.createElement("div");
        nome.className = "chat-bubble-title chat-bubble-author";
        if (remetente === "Erro") {
            nome.classList.add("text-danger");
        }
        nome.textContent = remetente;

        const corpo = document.createElement("div");
        corpo.className = "chat-bubble-body";
        const paragrafo = document.createElement("p");
        paragrafo.className = "chat-financeiro-texto text-break mb-0";
        paragrafo.textContent = texto;

        corpo.appendChild(paragrafo);
        balao.append(nome, corpo);
        coluna.appendChild(balao);
        linha.appendChild(coluna);
        mensagens.appendChild(linha);

        estadoVazio.classList.add("d-none");
        ocultarHistorico.disabled = false;
        return corpo;
    }

    function mostrarExibicao(corpo, exibicao) {
        for (const lista of exibicao?.listas ?? []) {
            const detalhes = document.createElement("details");
            detalhes.className = "card card-sm mt-2";

            const titulo = document.createElement("summary");
            titulo.className = "px-3 py-2 fw-medium text-break";
            titulo.textContent = lista.titulo;

            const itens = document.createElement("ul");
            itens.className = "list-group list-group-flush";
            for (const linha of lista.linhas) {
                const item = document.createElement("li");
                item.className = "list-group-item py-2 text-break";
                item.textContent = linha;
                itens.appendChild(item);
            }
            detalhes.append(titulo, itens);
            corpo.appendChild(detalhes);
        }

        for (const previa of exibicao?.previas ?? []) {
            const bloco = document.createElement("div");
            bloco.className = "card card-sm mt-2";
            const conteudo = document.createElement("div");
            conteudo.className = "card-body";

            const titulo = document.createElement("div");
            titulo.className = "fw-semibold text-break mb-2";
            titulo.textContent = previa.titulo;

            const campos = document.createElement("ul");
            campos.className = "ps-3 mb-2 text-break";
            for (const linha of previa.linhas) {
                const item = document.createElement("li");
                item.textContent = linha;
                campos.appendChild(item);
            }
            conteudo.append(titulo, campos);
            bloco.appendChild(conteudo);
            corpo.appendChild(bloco);

            if (previa.situacao === "confirmada" || previa.situacao === "expirada") {
                const estado = document.createElement("span");
                const confirmada = previa.situacao === "confirmada";
                estado.className = confirmada ? "badge bg-green-lt" : "badge bg-secondary-lt";
                estado.textContent = confirmada ? "Confirmado" : "Prazo de confirmação encerrado";
                conteudo.appendChild(estado);
                continue;
            }

            const confirmar = document.createElement("button");
            confirmar.type = "button";
            confirmar.className = "btn btn-primary btn-sm";
            confirmar.textContent = "Confirmar e gravar";
            conteudo.appendChild(confirmar);

            confirmar.addEventListener("click", async () => {
                confirmar.disabled = true;

                try {
                    const resposta = await enviarJson(formulario.dataset.confirmarUrl, {
                        id_acao: previa.id_acao,
                        tarefa_id: tarefaId,
                    });
                    const resultado = await resposta.json();
                    mostrarMensagem(
                        resultado.confirmada ? "Sistema" : "Erro",
                        resultado.mensagem || resultado.erro || "Não foi possível confirmar.",
                    );
                    if (resultado.confirmada) {
                        confirmar.textContent = "Confirmado";
                    } else if (resposta.status !== 409) {
                        confirmar.disabled = false;
                    }
                } catch {
                    mostrarMensagem("Erro", "Falha ao confirmar a ação.");
                    confirmar.disabled = false;
                } finally {
                    rolarParaUltimaMensagem();
                }
            });
        }
    }

    const anteriores = JSON.parse(document.getElementById("mensagens-iniciais").textContent);
    for (const item of anteriores) {
        const remetente = item.papel === "usuario" ? "Você"
            : item.papel === "sistema" ? "Sistema" : "IA";
        const corpo = mostrarMensagem(remetente, item.texto);
        mostrarExibicao(corpo, item.exibicao);
    }
    rolarParaUltimaMensagem();

    formulario.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        const mensagem = campo.value.trim();
        if (!mensagem || botaoEnviar.disabled) return;

        mostrarMensagem("Você", mensagem);
        campo.value = "";
        botaoEnviar.disabled = true;
        aguardando.classList.remove("d-none");
        rolarParaUltimaMensagem();

        try {
            const resposta = await enviarJson(formulario.action, {
                mensagem,
                tarefa_id: tarefaId,
            });
            const dados = await resposta.json();

            if (!resposta.ok) {
                mostrarMensagem("Erro", dados.erro || "Não foi possível responder.");
                return;
            }

            const corpo = mostrarMensagem("IA", dados.resposta);
            mostrarExibicao(corpo, dados.exibicao);
        } catch {
            mostrarMensagem("Erro", "Falha ao conectar ao chat.");
        } finally {
            aguardando.classList.add("d-none");
            botaoEnviar.disabled = false;
            rolarParaUltimaMensagem();
            campo.focus({ preventScroll: true });
        }
    });
})();
