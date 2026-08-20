# Research #12 — Fontes passivas: git local, Linear, Slack, histórico de navegador

Data: 2026-08-14. Contexto: agente local (Claude Agent SDK) em Windows 11, leitura retroativa sob demanda, saída em markdown no vault Obsidian. Meta de custo: ~R$ 0 por fonte.

---

## 1. Git local

### Descoberta de repos
- Não existe registro central de repos no Windows; a abordagem padrão é varrer diretórios de trabalho conhecidos (ex.: `C:\Users\gabri\development`) procurando pastas `.git` com profundidade limitada (PowerShell: `Get-ChildItem -Directory -Recurse -Depth 3 -Force -Filter .git`). Manter a lista em um arquivo de config do agente e revalidar a cada execução é mais robusto que varrer o disco inteiro.
- `git -C <repo> ...` evita `cd` e funciona bem em loop sobre a lista de repos.

### Formatos úteis para resumo diário/semanal
- Base: `git log --author=<padrão> --since="1 day ago" --until=now --all --no-merges --date=iso-local`.
  - `--all` importa: commits em branches não-merged não aparecem sem ele.
  - `--no-merges` limpa ruído de merge commits.
- Formato legível por LLM/máquina: `--pretty=format:'%h|%ad|%s'` (ou `%H%x09%aI%x09%s` com tab). Para volume de mudança: `--shortstat` ou `--numstat` (arquivos/linhas por commit).
- Commits ainda não commitados/pushed: `git status --porcelain` e `git stash list` complementam o retrato do dia.
- Reflog (`git reflog --date=iso`) captura rebases/checkouts do dia mesmo sem commit — útil para "no que mexi", mas é por clone, não sincroniza.

### Pegadinhas
- **E-mail de autor diferente por repo**: `--author` aceita regex — usar um padrão que cubra todos os e-mails/nomes (`--author='gabriel|velozo|gabrielvelozodev'`, case-insensitive via `git -c log.mailmap=true` + arquivo `.mailmap`, ou `--regexp-ignore-case`). Alternativa robusta: comparar `git config user.email` de cada repo e montar o filtro dinamicamente.
- **Shallow clones** (`--depth`): `git log` só enxerga o histórico baixado; para resumo diário isso raramente importa (o topo está presente), mas contagens "na semana" podem ficar truncadas. Detectável via `git rev-parse --is-shallow-repository`.
- **Fuso horário**: `%ad` usa o TZ gravado no commit; `--date=iso-local` normaliza para o relógio local — importante para agrupar "por dia".
- **Worktrees e submódulos**: `git worktree list` e submódulos têm `.git` como *arquivo*, não pasta — a varredura deve aceitar ambos.
- **Repos com CRLF/hooks lentos**: `git log` é read-only e não dispara hooks; sem risco.

### Custo, fragilidade, cadência
- **Custo**: R$ 0 (binário local).
- **Fragilidade**: quase nula — formato do `git log` é estável há décadas; único ponto móvel é a lista de repos e os e-mails de autor.
- **Cadência**: sob demanda, retroativa por `--since/--until`. Nada precisa ficar rodando; um resumo diário lê ~segundos de CPU.

---

## 2. Linear

### API GraphQL com Personal API Key
- Endpoint único: `https://api.linear.app/graphql`, header `Authorization: <API_KEY>` (sem prefixo `Bearer` para API key). Chave criada em *Settings → Security & access* ([docs GraphQL](https://linear.app/developers/graphql)).
- **Escopo mínimo**: ao criar a chave dá para restringir permissões (**Read**, Write, Admin, Create issues, Create comments) e limitar a **times específicos** — ou seja, existe chave read-only por time, exatamente o necessário aqui ([Linear Docs — API and Webhooks](https://linear.app/docs/api-and-webhooks)).
- **Expiração**: a chave não expira automaticamente; expiração é opcional na criação. Vale até revogar.
- **O que dá para ler** (schema GraphQL completo, o mesmo usado pelo app): `viewer.assignedIssues`, issues com filtros (`updatedAt`, estado, assignee), `comments`, `projects`, `cycles`, `issue.history` (trilha de atividade: mudanças de estado, assignee etc.), documentos, times, workflow states. Queries com `filter: { updatedAt: { gte: "..." } }` dão leitura retroativa limpa.
- **Rate limits** ([docs](https://linear.app/developers/rate-limiting)): API key = **2.500 requests/h por usuário** e **3.000.000 pontos de complexidade/h** (máx. 10.000 pontos/query). Headers `X-RateLimit-*` informam o restante. Para um resumo diário (dezenas de requests) é irrelevante.

### MCP server oficial (mcp.linear.app)
- Remoto e hospedado pelo Linear ([docs MCP](https://linear.app/docs/mcp), [changelog](https://linear.app/changelog/2025-05-01-mcp)):
  - `https://mcp.linear.app/mcp` (read-write) e **`https://mcp.linear.app/mcp/readonly`** (só ferramentas de leitura).
  - Autenticação: OAuth 2.1 com dynamic client registration (fluxo interativo no browser), ou bearer token / **API key do Linear** direto — combina com Agent SDK sem servidor próprio.
  - Ferramentas: buscar/ler issues (filtros por status, prioridade, assignee, labels), projetos, comentários, cycles.
- Comunidade: existem servers self-hosted (ex. [cline/linear-mcp](https://github.com/cline/linear-mcp), [tacticlaunch/mcp-linear](https://mcpservers.org/servers/tacticlaunch/mcp-linear)), mas o oficial + endpoint readonly torna-os desnecessários.

### Custo, fragilidade, cadência
- **Custo**: R$ 0 — API GraphQL e MCP server são gratuitos em qualquer plano.
- **Fragilidade**: baixa. API key estática (não expira, revogável); risco maior é vazamento da chave (mitigar com chave read-only + times restritos). GraphQL versionless: o schema evolui sem quebra abrupta, deprecações anunciadas. O endpoint SSE legado do MCP foi aposentado — usar `/mcp` (streamable HTTP).
- **Cadência**: retroativa perfeita via filtro `updatedAt >= ontem`. Diária ou semanal, sob demanda.

---

## 3. Slack

### Caminhos de leitura programática
Duas rotas principais para app própria (interna) no workspace do trabalho:

1. **User token (xoxp)** — o app pede *user scopes* e o token age como o usuário:
   - Lê **tudo que o usuário vê**: canais públicos (mesmo sem ser membro), privados/DMs/MPDMs em que é membro.
   - Scopes de leitura: `channels:history` + `channels:read` (públicos), `groups:history` + `groups:read` (privados), `im:history` + `im:read` (DMs), `mpim:history` + `mpim:read` (group DMs), `users:read` (resolver nomes), e `search:read` se quiser `search.messages` (busca — só existe com user token).
2. **Bot token (xoxb)** — mesmos scopes de history, mas o bot **só lê canais em que foi convidado** e não vê DMs do usuário. Para este caso de uso (retrato do dia do usuário), user token é o caminho certo ([conversations.history](https://docs.slack.dev/reference/methods/conversations.history/)).

Métodos-chave: `users.conversations` (lista conversas do usuário), `conversations.history` (mensagens, paginação por `oldest`/`latest` em epoch — leitura retroativa natural), `conversations.replies` (threads).

### Rate limits — e a mudança de 2025/2026
- Tiers da Web API: T1 ~1/min, T2 ~20/min, T3 ~50/min, T4 ~100/min ([rate limits](https://docs.slack.dev/apis/web-api/rate-limits/)). `conversations.history` e `.replies` são **Tier 3 (~50/min, até 1.000 msgs/request)**.
- **Mudança para apps não-Marketplace** ([changelog + FAQ](https://api.slack.com/changelog/2025-05-terms-rate-limit-update-and-faq)): apps **distribuídos comercialmente** fora do Marketplace caíram para **1 request/min e 15 mensagens/request** em `conversations.history`/`.replies` (novos apps desde 29/mai/2025; instalações existentes desde 03/mar/2026).
- **Exceção crucial**: *"internal customer-built applications"* — app criado no próprio workspace, não distribuído — **não é afetado** e mantém Tier 3. O plano aqui (app própria interna) fica no regime antigo. Risco residual: a Slack apertar isso no futuro; e um resumo diário cabe até no regime de 1/min (lento, mas viável).

### Política de workspace corporativo
- Admins costumam controlar via **App Management**: exigir aprovação para instalar apps (inclusive as internas criadas por membros), restringir quem cria apps, e allowlist de scopes. `search:read` e scopes de DM (`im:history`) são os que mais levantam bandeira em revisão de admin, por darem visão de conteúdo privado — pedir o mínimo e justificar.
- Se a criação de app for bloqueada, alternativas: pedir aprovação de app interna read-only, ou export pessoal (limitado). Não contar com tokens de sessão de browser (xoxc/xoxd) — violam ToS.

### MCP servers
- **Oficial da Slack** (fev/2026): remoto em `https://mcp.slack.com/mcp`, OAuth 2.0 com user token, **atrás de aprovação de admin**; ferramentas de busca, leitura de histórico de canais/threads, DMs, canvases ([Slack MCP server overview](https://docs.slack.dev/ai/slack-mcp-server/)). Só apps Marketplace ou internas podem usá-lo; clientes parceiros (Claude.ai/Claude Code, Cursor…) já integrados.
- **Comunidade**: [korotovsky/slack-mcp-server](https://github.com/korotovsky/slack-mcp-server) — self-hosted, aceita user/bot token, DMs e group DMs, cache de canais, busca. Bom plano B se o MCP oficial esbarrar na política do admin, usando o xoxp da app interna própria.

### Custo, fragilidade, cadência
- **Custo**: R$ 0 — Web API e MCP oficial não têm cobrança por uso.
- **Fragilidade**: média. User token xoxp não expira por padrão (a menos que o workspace ative *token rotation*), mas **é invalidado** se o usuário mudar a senha, se o admin revogar o app, ou por políticas de sessão corporativas. A mudança de rate limit de 2025 mostra que a Slack está ativamente restringindo apps não-Marketplace — a exceção para apps internas é o alicerce do plano e merece re-checagem anual.
- **Cadência**: retroativa por `oldest=<timestamp de ontem>` em cada conversa de `users.conversations`. Diária, sob demanda; ~1 request por canal ativo + threads.

---

## 4. Histórico de navegador (Chrome e Edge)

### Onde ficam os SQLite no Windows
- Chrome: `C:\Users\<user>\AppData\Local\Google\Chrome\User Data\Default\History`
- Edge: `C:\Users\<user>\AppData\Local\Microsoft\Edge\User Data\Default\History`
- Perfis extras ficam em `Profile 1`, `Profile 2`… ao lado de `Default` — enumerar `User Data\*\History`.

### Esquema (Chromium — igual nos dois)
- Tabela `urls`: `id, url, title, visit_count, typed_count, last_visit_time` ([Wikiversity — Chromium browsing history database](https://en.wikiversity.org/wiki/Chromium_browsing_history_database)).
- Tabela `visits`: `id, url (FK→urls.id), visit_time, from_visit, transition, segment_id` — uma linha por visita, ideal para reconstruir o dia.
- **Timestamps WebKit**: microssegundos desde 01/01/1601 UTC. Conversão SQL: `datetime(visit_time/1000000 - 11644473600, 'unixepoch')` ([Epoch Converter — WebKit](https://www.epochconverter.com/webkit)).
- Retenção: o Chrome expira histórico com ~90 dias — a leitura retroativa diária/semanal está bem dentro da janela.

### Ler com o navegador aberto (lock)
- Com o browser rodando o arquivo fica com lock exclusivo; conectar direto dá `database is locked`.
- **Prática padrão: copiar o arquivo** (`History` — e, por segurança, `History-wal`/`History-journal` se existirem) para o temp e abrir a cópia. `Copy-Item` funciona mesmo com o browser aberto.
- Alternativa: abrir em modo imutável — `sqlite3.connect('file:...History?mode=ro&immutable=1', uri=True)` — com fallback para cópia se falhar ([abordagem discutida aqui](https://www.pythontutorials.net/blog/is-it-possible-to-open-a-locked-sqlite-database-in-read-only-mode/)). A cópia é a rota mais previsível.

### Bibliotecas prontas
- [`browser-history`](https://pypi.org/project/browser-history/) (Python, multiplataforma): abstrai caminhos e lock de Chrome/Edge/Firefox/etc., retorna (timestamp, URL, título).
- [`browserexport`](https://pypi.org/project/browserexport/) (Python): faz snapshot/merge dos SQLite de vários browsers — bom para arquivar histórico além dos 90 dias.
- Para o agente, um script SQL de ~20 linhas sobre a cópia é suficiente; biblioteca é opcional.

### Custo, fragilidade, cadência
- **Custo**: R$ 0 (arquivo local).
- **Fragilidade**: baixa-média. O esquema `urls`/`visits` é estável há muitos anos, mas é **formato interno não documentado oficialmente** — pode mudar em major versions (versionamento na tabela `meta`). Caminhos mudam se o usuário criar perfis novos. Sem tokens, sem rede.
- **Cadência**: retroativa por `visit_time >= ontem`. Diária, sob demanda; leitura de milissegundos. Atenção ao filtro de ruído (redirects têm `transition` próprio; dá para filtrar visitas de subframe pela máscara de `transition`).

---

## Síntese comparativa

| Fonte | Custo | Auth | Fragilidade | Cadência natural |
|---|---|---|---|---|
| Git local | R$ 0 | nenhuma | mínima (mailmap/e-mails) | diária, `--since` |
| Linear | R$ 0 | API key read-only, sem expirar | baixa (GraphQL estável; MCP oficial readonly) | diária, `updatedAt >= X` |
| Slack | R$ 0 | user token xoxp de app interna (ou MCP oficial c/ aprovação de admin) | média (política corporativa + histórico de aperto em rate limits) | diária, `oldest=<ts>` |
| Navegador | R$ 0 | nenhuma (arquivo local; copiar antes de ler) | baixa-média (esquema não documentado, estável na prática) | diária, `visit_time >= X` |

Todas as quatro fontes fecham em R$ 0 e suportam leitura retroativa pura — nenhuma exige processo residente. O único ponto de dependência externa/política é o Slack corporativo (aprovação de admin para app interna ou para o MCP oficial).

## Fontes

- Linear: [GraphQL API](https://linear.app/developers/graphql) · [Rate limiting](https://linear.app/developers/rate-limiting) · [API and Webhooks (scopes de API key)](https://linear.app/docs/api-and-webhooks) · [MCP server](https://linear.app/docs/mcp) · [Changelog MCP](https://linear.app/changelog/2025-05-01-mcp)
- Slack: [conversations.history](https://docs.slack.dev/reference/methods/conversations.history/) · [Rate limits](https://docs.slack.dev/apis/web-api/rate-limits/) · [Mudança de rate limits não-Marketplace (FAQ)](https://api.slack.com/changelog/2025-05-terms-rate-limit-update-and-faq) · [Slack MCP server oficial](https://docs.slack.dev/ai/slack-mcp-server/) · [korotovsky/slack-mcp-server](https://github.com/korotovsky/slack-mcp-server)
- Navegador: [Chromium browsing history database (Wikiversity)](https://en.wikiversity.org/wiki/Chromium_browsing_history_database) · [WebKit timestamp converter](https://www.epochconverter.com/webkit) · [SQLite read-only/immutable](https://www.pythontutorials.net/blog/is-it-possible-to-open-a-locked-sqlite-database-in-read-only-mode/) · [browser-history (PyPI)](https://pypi.org/project/browser-history/) · [browserexport (PyPI)](https://pypi.org/project/browserexport/)
