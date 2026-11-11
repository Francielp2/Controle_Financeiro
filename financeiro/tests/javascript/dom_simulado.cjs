// AVISO: Estes testes foram elaborados com auxílio de Inteligência Artificial.
// Não houve revisão humana individual de todos os casos.
// Sua aprovação não garante ausência de defeitos; revise-os ao mudar as regras.
// Adaptador mínimo: NÃO é navegador nem validação visual. Callbacks admin só no navegador.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const script = fs.readFileSync(path.resolve(__dirname, '../../../static/financeiro/js/categoria_compromisso.js'), 'utf8');
const cenarios = fs.readFileSync(path.join(__dirname, 'cenarios.js'), 'utf8');
const nomes = ['abertura', 'selecao', 'remocao', 'sem_categoria', 'indisponivel', 'inativa', 'adulteracao', 'envio'];
const resultados = {};
for (const nome of nomes) {
    class Select extends EventTarget {
        constructor(value, options = []) { super(); this.value = value; this.options = options; this.disabled = false; }
        setCustomValidity(message) { this.validationMessage = message; }
        checkValidity() { return !this.validationMessage; }
        insertAdjacentElement(_, aviso) { this.aviso = aviso; }
    }
    const categoria = new Select('20', ['', '10', '20', '30'].map(value => ({value, disabled: value === '30'})));
    const compromisso = new Select('1');
    compromisso.dataset = {categoriasCompromissos: JSON.stringify({'1': '10', '2': '20', '3': '', '4': '999', '5': '30'})};
    const formulario = {querySelector: () => categoria};
    compromisso.closest = () => formulario;
    const document = {readyState: 'complete', querySelectorAll: () => [compromisso], createElement: () => ({setAttribute() {}, textContent: ''})};
    const ctx = vm.createContext({document, Event, categoria, compromisso, formulario});
    try {
        vm.runInContext(script, ctx);
        vm.runInContext(cenarios + `\ncenarios.${nome}({categoria, compromisso, formulario});`, ctx);
        resultados[nome] = null;
    } catch (erro) { resultados[nome] = erro.message; }
}
process.stdout.write(JSON.stringify(resultados));
