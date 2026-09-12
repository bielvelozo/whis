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
`daily/atual.md` — a terceira zona de propriedade: uma nota só, que agente e usuário mantêm juntos, dividida por seção. O agente cuida de *O que eu fiz* e *O que estou fazendo*: **acrescenta** o que é novo e **move** um item de *fazendo* para *fiz* quando o sinal é forte (PR mergeada, issue em Done), transportando a linha **literalmente** — nunca reescreve texto que já está lá, nunca apaga um item aberto. *Dúvidas* e *Falar* são só do usuário: o agente lê, nunca escreve — salvo `anotar`, que acrescenta uma linha em *Falar* a pedido explícito. *O que eu fiz* é da janela da daily: ao abrir a janela seguinte, o bloco é arquivado literalmente na nota datada e a seção recomeça.
_Avoid_: painel, dashboard, `daily/hoje.md`, `notas/daily.md`

**Zona de propriedade**:
Divisão do vault em três contratos: as pastas que o agente cria e pode regenerar (`reunioes/`, `transcricoes/`, `diario/`, `daily/`); a zona do usuário (`notas/`), que o agente nunca toca; e a **Nota viva**, onde os dois escrevem, cada um nas suas seções. `notas/daily.md` foi aposentado em 2026-09-12 — nunca foi usado; o que era dele vive nas seções do usuário da nota viva.

**Tracer bullet**:
A primeira fatia construível de ponta a ponta: "aperto um botão durante a reunião → nota transcrita/resumida aparece no vault".
_Avoid_: MVP, PoC

**Whis**:
Este projeto. Nasceu chamado *Second Brain* e foi rebatizado em 2026-09-09, herdando o nome do agente anterior do usuário, que morreu de vez. Os documentos de entregas fechadas em `.scratch/` guardam o nome antigo: são registro do que aconteceu, não foram reescritos.
_Avoid_: Second Brain, second-brain, SB

**Whis da EC2**:
O agente pessoal anterior do usuário — chat por mensageiro, hospedado numa EC2 —, aposentado e desligado. Doador de ideias para o Whis atual, nunca dependência. O qualificador existe para o nome não ficar ambíguo nos documentos antigos.
_Avoid_: Whis (sem qualificador, quando se fala do antigo)
