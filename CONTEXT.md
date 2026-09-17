# Whis

Agente pessoal local que observa o trabalho do usuário no PC, transcreve reuniões e recupera contexto, com um vault Obsidian como memória durável.

## Language

**Coletor**:
Componente que captura um tipo de sinal (áudio de reunião, fontes passivas de trabalho) e o transforma em notas no vault.
_Avoid_: watcher, observador, collector

**Fonte passiva**:
Dado de trabalho que já existe sem o Whis rodando — git local, Linear, Slack, histórico de navegador — lido retroativamente por um coletor.
_Avoid_: monitoramento, tracking

**Vault**:
O vault Obsidian local no PC do usuário — a memória durável do Whis, novo e sem legado de outros projetos.
_Avoid_: workspace, base de conhecimento, context/

**Sob demanda**:
Modo de operação de todo coletor: só roda entre um liga e um desliga explícitos do usuário; nunca escuta ou captura contínua.
_Avoid_: always-on, background

**Diário**:
Nota diária em `diario/` que resume o trabalho do dia a partir das fontes passivas.
_Avoid_: daily note, log

**Daily**:
Roteiro falado que o usuário lê na reunião diária do time. Vive na **Nota viva** (`daily/atual.md`); cobre da última daily até agora — não um dia civil. Cada geração deixa ao lado uma nota datada `daily/YYYY-MM-DD.md` com a janela e as listas cruas, que é o registro durável e de conferência.
_Avoid_: standup, resumo diário

**Nota viva**:
`daily/atual.md` — a terceira zona de propriedade: uma nota só, que agente e usuário mantêm juntos, dividida por seção. O agente cuida de *O que eu fiz* e *O que estou fazendo*: **acrescenta** o que é novo e **move** um item de *fazendo* para *fiz* quando o sinal é forte (PR mergeada, issue em Done), transportando a linha **literalmente** — nunca reescreve texto que já está lá, nunca apaga um item aberto. *Fazer*, *Dúvidas*, *Pontos* e *Falar* são só do usuário: o agente lê, nunca escreve por conta própria — os comandos `note` (→ *Pontos*), `doubt` (→ *Dúvidas*) e `do` (→ *Fazer*, com a caixa `- [ ]`) acrescentam uma linha a pedido explícito, e *Falar* ninguém toca além dele. Em *Fazer* quem marca `[x]` é ele, e a linha marcada fica onde está até ele a tirar: virar a janela da daily não mexe nela. A nota não carrega explicação nenhuma: ele sabe o que cada seção é. *O que eu fiz* é da janela da daily: ao abrir a janela seguinte, o bloco é arquivado literalmente na nota datada e a seção recomeça.
_Avoid_: painel, dashboard, `daily/hoje.md`, `notas/daily.md`

**Zona de propriedade**:
Divisão do vault em três contratos: as pastas que o agente cria e pode regenerar (`reunioes/`, `transcricoes/`, `diario/`, `daily/`, `respostas/`); a zona do usuário (`notas/`), que o agente nunca toca; e a **Nota viva**, onde os dois escrevem, cada um nas suas seções. `notas/daily.md` foi aposentado em 2026-09-12 — nunca foi usado; o que era dele vive nas seções do usuário da nota viva.

**Palheta**:
A janela de comandos do Whis, aberta por atalho global de teclado no PC (`ctrl+space`), no estilo Raycast: um campo de texto e uma lista de ações clicáveis, num painel acrílico translúcido; os comandos são em inglês (`daily`, `note`, `doubt`, `do`, `ask`, `open`, `record`, `settings`), o rótulo de uma ação digitado inteiro vale como o comando, Tab completa o comando da ação selecionada, e a janela some ao despachar. Todo comando **dispara e some** — roda em segundo plano, o resultado vira nota no vault e um toast avisa quando fica pronto. Substitui a DM do Slack como o lugar de perguntar e anotar; a bandeja continua sendo o gesto de gravar reunião. Uma resposta de `ask` nasce em `respostas/`, zona do agente.
_Avoid_: launcher, painel com abas, chat

**Vigia**:
Uma tarefa agendada fora do Whis (`Whis-Vigia`, um script PowerShell autossuficiente) que consulta o Agendador e a lista de processos e dispara um toast quando uma peça não subiu — a daily não nasceu, a limpeza falhou, a bandeja não está no ar. Existe porque quem avisa que o Whis caiu não pode ser o Whis.
_Avoid_: watchdog, healthcheck

**Tracer bullet**:
A primeira fatia construível de ponta a ponta: "aperto um botão durante a reunião → nota transcrita/resumida aparece no vault".
_Avoid_: MVP, PoC

**Whis**:
Este projeto. Nasceu chamado *Second Brain* e foi rebatizado em 2026-09-09, herdando o nome do agente anterior do usuário, que morreu de vez. Os documentos de entregas fechadas em `.scratch/` guardam o nome antigo: são registro do que aconteceu, não foram reescritos.
_Avoid_: Second Brain, second-brain, SB

**Whis da EC2**:
O agente pessoal anterior do usuário — chat por mensageiro, hospedado numa EC2 —, aposentado e desligado. Doador de ideias para o Whis atual, nunca dependência. O qualificador existe para o nome não ficar ambíguo nos documentos antigos.
_Avoid_: Whis (sem qualificador, quando se fala do antigo)
