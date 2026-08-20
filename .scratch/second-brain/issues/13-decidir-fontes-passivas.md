# Decidir as integrações de fontes passivas

Type: grilling
Status: resolved
Blocked by: 12

## Question

Como o second brain lê git, Linear, Slack (e talvez histórico de navegador) e transforma isso em contexto no vault?

Decidir, com os fatos da [pesquisa de fontes passivas](12-pesquisa-fontes-passivas.md) em mãos:

- Quais fontes entram na v1 e quais ficam para depois (o usuário citou git primeiro; navegador é "se for relevante").
- O que se lê de cada uma: no Linear, issues atribuídas/atividade? No Slack, quais canais — DMs entram? No git, quais repositórios?
- Cadência e gesto: leitura retroativa sob demanda ("resume meu dia/semana") ou agendada? Como isso convive com o resumo no vault.
- Privacidade: dados do empregador (Slack/Linear) indo ao Claude para resumo — mesma régua do filtro de exclusão já discutida, ou restrições extras.

## Answer

Decidido pelo usuário em 2026-08-14, com os fatos da [pesquisa de fontes passivas](12-pesquisa-fontes-passivas.md):

- **Fontes da v1: git + Linear + Slack**, construídas nessa ordem (Slack por último — depende de aprovação de admin no workspace; o diário degrada graciosamente sem ele). **Navegador fica fora da v1** — reentra só se os diários se provarem rasos.
- **O que se lê**:
  - **Linear**: **tudo do(s) time(s)** do usuário (issues, comentários, projetos, atividade) — não só a atividade própria. Via API GraphQL com Personal API Key read-only.
  - **Slack**: **tudo que o usuário participa, incluindo DMs, com blocklist** de canais/conversas que ele não quer que o agente leia. Via app interna com user token (xoxp).
  - **Git**: **varredura automática** de uma pasta raiz de desenvolvimento atrás de repos, com lista de exclusão.
- **Cadência: diário agendado** — tarefa agendada do Windows gera `diario/YYYY-MM-DD.md` automaticamente no fim do dia (leitura retroativa; nenhum processo residente — não conflita com o princípio de nada ficar escutando).
- **Privacidade**: régua única — conteúdo vai ao Claude para resumo, com **filtro de exclusão configurável** (padrões/canais/pessoas que nunca saem da máquina); a blocklist do Slack é a primeira camada desse filtro.
