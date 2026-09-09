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
Roteiro falado que o usuário lê na reunião diária do time, em `daily/`. Cobre da última daily até agora — não um dia civil — e carrega as listas cruas embaixo do roteiro, sendo por isso o registro durável do trabalho.
_Avoid_: standup, resumo diário

**Zona de propriedade**:
Divisão do vault entre pastas que o agente cria e pode regenerar (`reunioes/`, `transcricoes/`, `diario/`, `daily/`) e a zona do usuário (`notas/`), que o agente só toca sob pedido explícito — nunca por iniciativa própria. `notas/daily.md` é o caso do pedido explícito: o agente lê os pontos que o usuário escreveu ali e só escreve neles quando mandado (`daily --anotar`).

**Tracer bullet**:
A primeira fatia construível de ponta a ponta: "aperto um botão durante a reunião → nota transcrita/resumida aparece no vault".
_Avoid_: MVP, PoC

**Whis**:
Este projeto. Nasceu chamado *Second Brain* e foi rebatizado em 2026-09-09, herdando o nome do agente anterior do usuário, que morreu de vez. Os documentos de entregas fechadas em `.scratch/` guardam o nome antigo: são registro do que aconteceu, não foram reescritos.
_Avoid_: Second Brain, second-brain, SB

**Whis da EC2**:
O agente pessoal anterior do usuário — chat por mensageiro, hospedado numa EC2 —, aposentado e desligado. Doador de ideias para o Whis atual, nunca dependência. O qualificador existe para o nome não ficar ambíguo nos documentos antigos.
_Avoid_: Whis (sem qualificador, quando se fala do antigo)
