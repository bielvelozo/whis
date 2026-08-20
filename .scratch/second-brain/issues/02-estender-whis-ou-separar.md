# Estender o Whis ou projeto separado?

Type: grilling
Status: resolved
Blocked by: 01, 10

## Question

O second brain deve ser uma extensão do Whis (coletores novos alimentando o mesmo motor + vault) ou um projeto separado (observador desacoplado do bot de WhatsApp, possivelmente compartilhando o vault)?

Considerar, com os fatos do [exame da arquitetura do Whis](01-examinar-arquitetura-whis.md) em mãos:

- Os coletores precisam rodar no Windows nativo (áudio, janelas); o Whis roda em Docker — como isso convive?
- Compartilhar o vault sem compartilhar o processo é meio-termo viável?
- Custo de manter dois projetos vs. custo de acoplar tudo num só.

## Answer

**Projeto separado, fino e 100% local** — confirmado pelo usuário em 2026-08-14, com uma terceira opção avaliada e descartada no caminho:

- **Estender o Whis**: descartado. O usuário declarou o Whis aposentado (o second brain é o sucessor espiritual), e os fatos do [exame da arquitetura](01-examinar-arquitetura-whis.md) mostram incompatibilidade estrutural: runtime inteiro em Docker numa EC2, vault remoto, nenhum caminho para coletores nativos no Windows.
- **Adotar agente pronto (OpenClaw/Hermes)**: descartado pelos fatos da [avaliação de agentes prontos](10-pesquisa-agentes-prontos.md) — Windows nativo é segunda classe (WSL2 é o caminho oficial), vault Obsidian externo recusado pelo projeto como "not planned", histórico de segurança pesado; e o coração da v1 (captura WASAPI, STT, escrita de nota) seria custom de qualquer forma.
- **A escolha**: coletores Windows custom + Claude via Agent SDK com OAuth da conta Pro/Max do usuário + **vault Obsidian novo, criado localmente no PC**. O Whis entra como doador de ideias (convenções de vault prompt-driven do SOUL.md, arquitetura de skills, uso do Agent SDK), nunca como dependência.
- Consequências no mapa: a [estrutura do vault](07-estrutura-vault-obsidian.md) parte de vault novo local (sem legado); interface de consumo da v1 é Obsidian + CLI local, chat por mensageiro fica na névoa.

Registrado como ADR: `docs/adr/0001-projeto-separado-100-local.md`.
