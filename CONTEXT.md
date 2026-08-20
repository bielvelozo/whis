# Second Brain

Agente pessoal local que observa o trabalho do usuário no PC, transcreve reuniões e recupera contexto, com um vault Obsidian como memória durável.

## Language

**Coletor**:
Componente que captura um tipo de sinal (áudio de reunião, fontes passivas de trabalho) e o transforma em notas no vault.
_Avoid_: watcher, observador, collector

**Fonte passiva**:
Dado de trabalho que já existe sem o Second Brain rodando — git local, Linear, Slack, histórico de navegador — lido retroativamente por um coletor.
_Avoid_: monitoramento, tracking

**Vault**:
O vault Obsidian local no PC do usuário — a memória durável do Second Brain, novo e sem legado de outros projetos.
_Avoid_: workspace, base de conhecimento, context/

**Sob demanda**:
Modo de operação de todo coletor: só roda entre um liga e um desliga explícitos do usuário; nunca escuta ou captura contínua.
_Avoid_: always-on, background

**Diário**:
Nota diária em `diario/` que resume o trabalho do dia a partir das fontes passivas.
_Avoid_: daily note, log

**Zona de propriedade**:
Divisão do vault entre pastas que o agente cria e pode regenerar (`reunioes/`, `transcricoes/`, `diario/`) e a zona do usuário (`notas/`), que o agente só toca sob pedido explícito — nunca por iniciativa própria.

**Tracer bullet**:
A primeira fatia construível de ponta a ponta: "aperto um botão durante a reunião → nota transcrita/resumida aparece no vault".
_Avoid_: MVP, PoC

**Whis**:
Agente pessoal anterior do usuário (chat via Telegram, EC2), aposentado; doador de ideias para o Second Brain, nunca dependência.
