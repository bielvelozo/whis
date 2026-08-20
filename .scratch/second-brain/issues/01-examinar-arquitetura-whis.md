# Examinar a arquitetura do Whis

Type: research
Status: resolved

## Question

O que o Whis (`C:\Users\gabri\development\project-whis`) já resolve que o second brain precisaria, e como um coletor novo (transcrição de reunião, observador de atividade) se plugaria nele?

Levantar fatos, não decidir:

- Arquitetura geral: motor de raciocínio, como o Claude é invocado, deploy (Docker Compose, monorepo pnpm + turbo).
- Como o vault Obsidian (`context/`) é lido e escrito hoje — formato das notas, convenções, quem escreve.
- A arquitetura de skills: como uma capacidade nova entra; uma skill consegue rodar sob demanda no Windows (fora do Docker)?
- Estado de maturidade: o que funciona de verdade hoje vs. o que é aspiração.
- Acoplamento ao WhatsApp: o motor funciona sem essa interface?

O resultado alimenta [Estender o Whis ou projeto separado?](02-estender-whis-ou-separar.md).

## Answer

- O Whis é um agente de chat single-user (Telegram default; WhatsApp **dormente**, `WHATSAPP_ENABLED=false`) rodando **Docker-only** — em produção numa EC2 com CI/CD completo e testado (GHCR + SSH deploy + auto-rollback, spec 0005 shipped).
- Motor: `@anthropic-ai/claude-agent-sdk` (`query()` por turno, OAuth de plano Pro/Max, `bypassPermissions`), system prompt = `agent/SOUL.md` + `profile/USER.md`, sessões SQLite com resume (janela de 6h). Totalmente desacoplado do WhatsApp via interface `Channel` — funciona só com Telegram, e Evolution+Postgres nem sobem sem `--profile whatsapp`.
- Vault Obsidian (`context/`) é o `cwd` do Claude; **nenhum código escreve notas** — convenções (`personal/`, `work/`, `daily/YYYY-MM-DD.md`, template com frontmatter) são 100% prompt-driven no SOUL.md. O vault real vive na EC2 (`/opt/whis/context/`), não na máquina local — o checkout local está vazio.
- Skills = pastas com `SKILL.md`, symlinkadas pro `~/.claude/skills` do container no entrypoint; ativação por descrição; restart obrigatório. Skills com efeito real (google-calendar, scheduled-messages) exigiram MCP server ou código no worker. **Não existe caminho pra skill rodar sob demanda no Windows fora do Docker** — todo runtime executa no container Linux na EC2.
- Ganchos existentes pra coletor: `dispatchSynthetic()` no AgentCore (usado pelo scheduler — precedente de mensagem fabricada), webhook server Hono extensível, e suporte a MCP remoto (`type: http/sse` + `url`) — único mecanismo pronto pra algo no Windows local falar com o Whis.
- Maturidade: MVP, Telegram e CI/CD formalmente shipped com smoke-results; google-calendar e scheduled-messages implementados mas com specs em draft sem smoke. Código limpo (~50 testes, zero TODOs), porém **nenhum commit desde 2026-05-10** (~3 meses parado).
- Implicação factual pra decisão: um coletor de transcrição/atividade na máquina Windows é, por construção, externo ao runtime do Whis — a integração seria por MCP remoto, endpoint novo no worker ou sync de arquivos até o vault na EC2 (nada disso existe hoje).

Detalhes e evidências: [../research/01-arquitetura-whis.md](../research/01-arquitetura-whis.md)
