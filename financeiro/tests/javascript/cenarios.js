// AVISO: Estes testes foram elaborados com auxílio de Inteligência Artificial.
// Não houve revisão humana individual de todos os casos.
// Sua aprovação não garante ausência de defeitos; revise-os ao mudar as regras.
// Cenários compartilhados pelo DOM simulado e pelo navegador real.
function verificar(condicao, mensagem) {
    if (!condicao) throw new Error(mensagem);
}
function mudar(campo, valor) {
    campo.value = valor;
    campo.dispatchEvent(new Event('change', {bubbles: true}));
}
const cenarios = {
    abertura({categoria}) { // Preenche categoria ao abrir compromisso existente.
        verificar(categoria.value === '10', 'Categoria inicial deve ser 10');
    },
    selecao({compromisso, categoria}) { // Troca entre categorias distintas.
        mudar(compromisso, '2');
        verificar(categoria.value === '20', 'Troca deve selecionar categoria 20');
        verificar([...categoria.options].filter(o => !o.disabled).length === 1, 'Somente a categoria vinculada fica habilitada');
    },
    remocao({compromisso, categoria}) { // Remove compromisso e libera opções originais.
        mudar(compromisso, '');
        verificar(categoria.value === '', 'Remover compromisso limpa categoria');
        verificar(!categoria.options[1].disabled && !categoria.options[2].disabled, 'Libera opções ativas');
        verificar(categoria.options[3].disabled, 'Preserva bloqueio original da inativa');
    },
    sem_categoria({compromisso, categoria}) { // Compromisso livre permite categoria manual.
        mudar(compromisso, '3');
        mudar(categoria, '20');
        verificar(categoria.value === '20', 'Categoria livre deve ser editável');
        verificar(categoria.checkValidity(), 'Categoria livre deve ser válida');
    },
    indisponivel({compromisso, categoria}) { // ID ausente impede envio por validação nativa.
        mudar(compromisso, '4');
        verificar(categoria.value === '', 'Categoria indisponível não deve ficar selecionada');
        verificar(!categoria.checkValidity(), 'Categoria ausente deve invalidar formulário');
        verificar(categoria.aviso.textContent.includes('não está disponível'), 'Aviso acessível necessário');
    },
    inativa({compromisso, categoria}) { // Opção existente mas desabilitada também impede envio.
        mudar(compromisso, '5');
        verificar(!categoria.checkValidity(), 'Categoria inativa deve invalidar formulário');
        mudar(compromisso, '1');
        verificar(categoria.checkValidity(), 'Seleção válida deve limpar erro anterior');
    },
    adulteracao({categoria}) { // Alterar categoria não pode violar a do compromisso.
        mudar(categoria, '20');
        verificar(categoria.value === '10', 'Categoria deve retornar ao compromisso');
    },
    envio({formulario, categoria}) { // Select fica habilitado e participa dos dados enviados.
        verificar(!categoria.disabled, 'Select inteiro não pode ser disabled');
        if (typeof FormData !== 'undefined') {
            verificar(new FormData(formulario).get('categoria') === '10', 'POST deve incluir categoria');
        } else {
            verificar([...categoria.options].some(o => o.value === categoria.value && !o.disabled), 'Opção selecionada deve participar do POST');
        }
    },
    admin_adicionar_categoria({categoria}) { // Callback real do admin dispara jQuery change, não evento nativo.
        const win = {name: categoria.id + '__1', location: {pathname: '/admin/financeiro/categoria/add/'}, close() {}};
        dismissAddRelatedObjectPopup(win, '77', 'Categoria nova');
        verificar(categoria.value === '10', 'Adicionar categoria no admin não pode substituir a categoria do compromisso');
    },
    admin_adicionar_compromisso({compromisso, categoria}) { // Novo compromisso não está no mapa serializado da página.
        const win = {name: compromisso.id + '__1', location: {pathname: '/admin/financeiro/compromissofinanceiro/add/'}, close() {}};
        dismissAddRelatedObjectPopup(win, '99', 'Novo compromisso com categoria 20');
        // Sem metadados atualizados, deve ao menos bloquear o envio até resolver o vínculo.
        verificar(categoria.value === '20' || !categoria.checkValidity(), 'Novo compromisso desconhecido exige atualizar categoria ou bloquear envio');
    }
};
