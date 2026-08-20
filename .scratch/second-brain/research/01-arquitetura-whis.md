# Arquitetura do Whis — achados

Ticket: [01-examinar-arquitetura-whis](../issues/01-examinar-arquitetura-whis.md)
Repo examinado: `C:\Users\gabri\development\project-whis` (somente leitura)
Data da análise: 2026-08-13

## TL;DR

O Whis é um agente pessoal de chat (Telegram por padrão; WhatsApp dormente) que roda **Docker-only**, com o Claude Agent SDK como motor e um vault Obsidian (`context/`) como memória durável. O motor é totalmente desacoplado do WhatsApp (abstração `Channel`), já tem um caminho de "mensagem sintética" (scheduler) que serviria de porta de entrada para coletores, e está em produção real numa EC2 com CI/CD. Porém: o runtime inteiro (skills incluídas) roda dentro do container Linux — **não há caminho para uma skill rodar sob demanda no Windows fora do Docker** — e o vault de produção mora na EC2, não na máquina local. Projeto parado desde 2026-05-10 (~3 meses).

---

## 1. Visão geral e monorepo

- Monorepo pnpm workspaces + Turborepo (`pnpm-workspace.yaml`: `apps/*`, `packages/*`; `turbo.json` com `lint`/`typecheck`/`test`/`build`).
- Workspaces:
  - `apps/worker/` — o processo Node único: canais (Telegram/WhatsApp), agent core, scheduler, webhook server (Hono).
  - `packages/storage/` — `@whis/storage`, SQLite (better-sqlite3): sessões, auditoria de mensagens, `scheduled_messages`.
  - `packages/logger/` — factory pino.
  - `agent/` — identidade committed: `SOUL.md`, `mcp.json`, `skills/`.
  - `profile/` — config pessoal (templates committed, reais gitignored): `.env`, `USER.md`, `config.yaml`, `mcp.json`, `skills/`.
  - `context/` — vault Obsidian real (gitignored; `context.example/` é o template).
  - `infra/` — Dockerfile multi-stage, docker-compose, entrypoint, scripts de setup, `deploy.sh`.
- Fork adaptado do `zeno-agent` (github.com/ribeirogab/zeno-agent) — restos disso aparecem no código (comentários mencionando Slack em `apps/worker/src/channels/types.ts`).
- **Runtime é Docker-only por decisão explícita** — `AGENTS.md` linha 15: "Todo runtime é Docker-only — não há `pnpm dev`/`start` pra rodar apps localmente fora do container."

## 2. Motor de raciocínio — como o Claude é invocado

Arquivo central: `apps/worker/src/agent/backends/claude-code.ts`.

- Usa `@anthropic-ai/claude-agent-sdk` — função `query()` por turno de conversa (não é API direta; é o Claude Code SDK, subprocess CLI).
- Autenticação por **OAuth de plano Claude Pro/Max** (`CLAUDE_CODE_OAUTH_TOKEN` em `profile/.env`, gerado via `pnpm run docker:setup-token`), não API key.
- Opções relevantes por chamada:
  - `systemPrompt` montado dinamicamente (ver §3), `cwd` = vault (`WORKSPACE_DIR`, default `/app/context` — `apps/worker/src/config.ts:30`).
  - `permissionMode: 'bypassPermissions'` (a menos que haja hook PreToolUse), `allowedTools: ['Bash', 'Read', 'Glob', 'Grep']` + MCP servers.
  - `settingSources: ['user']` — é assim que as skills em `/home/node/.claude/skills` entram (ver §5).
  - Timeout default de 1h; erros classificados em `timeout` / `auth_expired` / `rate_limited` / `unknown`.
- **Sessões**: o SDK devolve `session_id`; `AgentCore` (`apps/worker/src/agent/core.ts`) persiste por chatId no SQLite (`SessionRepo`) e faz `resume` se a última mensagem foi há menos de `SESSION_IDLE_HOURS` (default 6h). Resume falho → retry stateless.
- System prompt = `agent/SOUL.md` + `profile/USER.md` + skills "always-active" (`profile/config.yaml`, hoje lista vazia) — montado em `apps/worker/src/agent/system-prompt.ts`, hot-reload via `apps/worker/src/profile/watcher.ts` (fs.watch com debounce; mudança em mcp.json exige restart).
- Mensagem do usuário é embrulhada com contexto (`[telegram_context]`/`[whatsapp_context]`, timestamp, anexos com `localPath` para o Claude ler) — `wrapMessageContext` em `core.ts`.
- MCP: `apps/worker/src/agent/mcp.ts` mescla `agent/mcp.json` (built-in: `@cocal/google-calendar-mcp` via npx) com `profile/mcp.json` (usuário; sobrescreve em colisão), com interpolação `${ENV_VAR}` e flag `_disabled`. Além disso há um **MCP server in-process** (sem subprocess) para as tools `schedule_*` — `apps/worker/src/scheduler/tools.ts`, injetado via `inProcessMcpServers` no backend.
- Existe `MockBackend` com fixtures (`WHIS_BACKEND=mock`) para testes sem Claude.

## 3. Vault Obsidian (`context/`) — leitura/escrita e convenções

- **Nenhum código escreve notas.** O vault é escrito exclusivamente pelo próprio Claude via tools de arquivo (Bash/Read/Glob/Grep) com `cwd` apontado para o vault. As convenções são 100% prompt-driven, definidas em `agent/SOUL.md`:
  - Estrutura: `personal/`, `work/`, `daily/` (uma nota por dia, `YYYY-MM-DD.md`), `templates/`.
  - Regra de ouro: memória de sessão gira a cada 6h; o que importa para amanhã vai pro vault.
  - "Modos cognitivos": conteúdo de trabalho → `work/`, pessoal → `personal/`; se ambíguo, perguntar.
  - Proibições: não sair do vault, não mexer em `/app/agent`, `/app/profile`, `/app/data`; conferir duplicação antes de criar nota.
- Formato de nota: template único em `context.example/templates/note.md` — frontmatter YAML (`created`, `tags`) + seções `Contexto` / `Conteúdo` / `Próximos passos` / `Referências`. Placeholders no formato do plugin Templates do Obsidian (`{{date:YYYY-MM-DD}}`, `{{title}}`).
- `context.example/README.md` deixa explícito: "As subpastas são convenção — não são sagradas. Reorganize como quiser; o Whis se adapta lendo o conteúdo."
- **O vault local está vazio** (só `.gitkeep`, README e o template). O vault real vive **na EC2** — montado como bind mount `./context:/app/context` no `infra/docker-compose.yml`, no clone `/opt/whis` da VM (cf. `infra/deploy.sh` e `docs/specs/0005-cicd/setup.md`). Um coletor rodando no Windows local não alcança esse vault diretamente pelo filesystem.

## 4. Canais — acoplamento ao WhatsApp

**O motor funciona sem WhatsApp.** Evidências:

- Interface `Channel` genérica em `apps/worker/src/channels/types.ts` (start/send/react/unreact/stop, `IncomingMessage` normalizado com `platform`, `attachments`, `scheduledTrigger`).
- `apps/worker/src/index.ts` monta uma lista de canais por flags: `TELEGRAM_ENABLED` (default **true**) e `WHATSAPP_ENABLED` (default **false** — "dormente" desde a spec 0002, porque o chip dedicado foi cancelado). Falha no boot só se **nenhum** canal estiver habilitado.
- Evolution API + Postgres só sobem com `docker compose --profile whatsapp` (`infra/docker-compose.yml`, `profiles: [whatsapp]`). No modo default, sobe só o `whis-worker`.
- Telegram usa `grammy` em long-polling (`apps/worker/src/channels/telegram/adapter.ts`) — zero infra pública. WhatsApp usa webhook (Hono, `apps/worker/src/webhook/server.ts`, que também serve o `/health` universal).
- Segurança: single-owner — só `TELEGRAM_OWNER_CHAT_ID` / `WHATSAPP_OWNER_NUMBER` são aceitos.
- Já existe um **terceiro caminho de entrada sem canal humano**: `AgentCore.dispatchSynthetic()` (`core.ts:44`), usado pelo `ScheduledDispatcher` (`apps/worker/src/scheduler/dispatcher.ts`) para fabricar mensagens a partir do banco (tick de 60s + catch-up de 24h no boot). É o precedente arquitetural natural para um coletor injetar eventos no motor.

## 5. Arquitetura de skills

- Skill = diretório com `SKILL.md` (frontmatter `name` + `description`) + arquivos auxiliares, no padrão agentskills.io. Duas camadas: `agent/skills/` (built-in, committed — hoje `google-calendar` e `scheduled-messages`) e `profile/skills/` (usuário, gitignored — hoje **vazio**; sobrescreve em colisão de nome).
- Descoberta: `infra/entrypoint.sh` symlinka ambas as camadas para `/home/node/.claude/skills` no boot do container; o SDK as enxerga via `settingSources: ['user']`. Ativação é **por descrição** (o Claude decide quando usar) — modelo Claude Code padrão.
- Skills "always-active" podem ser injetadas direto no system prompt via `profile/config.yaml` (`always_active_skills`, hoje `[]`).
- Como uma capacidade nova entra, na prática (padrão observado nas specs 0003/0004): pasta da skill + (a) um MCP server externo em `mcp.json` (caso google-calendar) ou (b) tools in-process + tabela SQLite + subsistema no worker (caso scheduled-messages) + regras de confirmação no `SOUL.md`. Ou seja: skill simples é só uma pasta; skill com efeito colateral real exigiu **código no worker**.
- **Restart obrigatório** para skill nova (`README.md`: "Hot-reload de skills é planejado pós-MVP").
- **Skill sob demanda no Windows fora do Docker: não existe hoje.** O subprocess do SDK (e portanto qualquer script que uma skill mande rodar via Bash) executa dentro do container Linux `whis-worker` — em produção, na EC2. Não há mecanismo de execução no host Windows, e o `AGENTS.md` declara runtime Docker-only. Um "observador de atividade do Windows" ou uma transcrição rodando na máquina local teria que ser um processo separado que conversa com o Whis por outra via (webhook, canal, escrita remota no vault) — nada disso existe pronto.

## 6. Docker / deploy

- `infra/Dockerfile`: multi-stage node:24-slim, instala o Claude Code CLI no runtime (`curl claude.ai/install.sh`), roda como user `node`.
- `infra/docker-compose.yml`: serviço `whis-worker` (imagem `ghcr.io/bielvelozo/whis-worker`, healthcheck HTTP `/health`, volumes: `whis_data` (SQLite), `claude_home` (credenciais Claude), `gcal_tokens`, bind mounts read-only de `agent/` e `profile/`, bind mount RW de `context/`); `evolution-api` + `postgres` atrás do profile `whatsapp`.
- `infra/docker-compose.local.yml`: override de dev com bot Telegram separado (`profile/.env.local`) e build local — volumes (vault, DB, tokens) compartilhados com o modo normal.
- CI/CD real e validado (spec 0005, shipped 2026-05-10): `ci.yml` (quality-gate), `deploy.yml` (build GHCR → SSH → `infra/deploy.sh` idempotente com healthcheck + auto-rollback + notificação Telegram), `rollback.yml` manual. Smoke com 11/11 critérios ✅ em `docs/specs/0005-cicd/smoke-results.md` — **incluindo rollback automático comprovado em produção**.

## 7. Estado de maturidade — o que funciona vs. aspiração

Funciona de verdade (evidenciado por smoke-results e código completo com testes):

- **0001 MVP** (shipped 2026-04-25): pipeline canal → Claude → vault ponta-a-ponta, com `smoke-results.md`.
- **0002 Telegram** (shipped 2026-04-25): canal default do dia-a-dia, com `smoke-results.md`.
- **0005 CI/CD** (shipped 2026-05-10): produção na EC2 com deploy automatizado.
- Qualidade: ~50+ testes vitest, biome, knip, quality-gate no CI; **zero TODO/FIXME no código** (grep confirma); nenhum stub encontrado além do `MockBackend` intencional.

Zona cinzenta:

- **0003 google-calendar** e **0004 scheduled-messages**: código completo e commitado (skills, MCP, scheduler, tools, testes; SMOKE.md tem checklist SM1–SM9), mas frontmatter das specs segue `status: draft / shipped: null` e **não há `smoke-results.md`** — implementadas, não formalmente validadas.

Aspiração / não existe:

- Hot-reload de skills; múltiplos usuários; WhatsApp ativo (dormente por falta de chip); cron declarativo no `config.yaml` (o watcher tem callback `onCronsChanged` com corpo vazio — `index.ts:270`: "sem cron no MVP"); `profile/skills/` do usuário nunca foi usado.
- **Momentum**: 88 commits concentrados em duas rajadas (2026-04-24 a 26 e 2026-05-08 a 10); **nenhum commit desde 2026-05-10** — ~3 meses parado na data desta análise.

## 8. Como um coletor novo se plugaria (fatos, sem decidir)

Pontos de acoplamento que existem hoje:

1. **`dispatchSynthetic()`** (`apps/worker/src/agent/core.ts:44`) — turno completo do agente a partir de mensagem fabricada, com sessão e envio pro canal. Precedente pronto; um coletor viraria um subsistema do worker (como o `ScheduledDispatcher`) ou um cliente de um endpoint novo no webhook server.
2. **Webhook server Hono** (`apps/worker/src/webhook/server.ts`) — hoje só rota WhatsApp + `/health`; adicionar rota de ingestão é mudança pequena, mas o worker roda na EC2 (rede/exposição a resolver).
3. **Escrita direta no vault** — qualquer processo com acesso ao filesystem da EC2 (`/opt/whis/context/`) pode dropar notas Markdown que o Whis lê depois; convenções são só as do SOUL.md/template. Do Windows local, exigiria sync (git, syncthing, etc.) que não existe no projeto.
4. **Skill + MCP** — um coletor exposto como MCP server (stdio dentro do container, ou HTTP/SSE remoto — o `McpServerConfig` já suporta `type: 'http' | 'sse'` com `url`, cf. `apps/worker/src/agent/mcp.ts`) daria ao Whis acesso *pull* aos dados do coletor. MCP remoto via URL é o único mecanismo existente pelo qual algo rodando no Windows local se conectaria ao Whis sem tocar no worker.

Restrições estruturais relevantes:

- Tudo que roda "dentro" do Whis roda no container Linux na EC2 — captura de áudio/atividade da máquina Windows é, por construção, externa ao runtime do Whis.
- O motor é single-user, single-turn-por-mensagem, orientado a chat; não há fila de ingestão, batch ou pipeline de processamento de eventos.
- O vault de produção não está na máquina local do Gabriel.
