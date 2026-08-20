# Pesquisar acesso às fontes passivas (git, Linear, Slack, navegador)

Type: research
Status: resolved

## Question

Como um agente local no Windows lê, de forma programática e barata, as quatro fontes passivas de contexto de trabalho do usuário?

Levantar fatos, não decidir:

- **Git local**: agregação de `git log` do autor em múltiplos repositórios (descoberta de repos, formato útil para resumo diário/semanal) — presumivelmente trivial, confirmar pegadinhas.
- **Linear**: API GraphQL com API key pessoal — o que dá para ler (issues atribuídas, atividade, comentários, projetos), rate limits, MCP server oficial ou da comunidade, escopo mínimo.
- **Slack**: opções para ler canais/threads que o usuário participa com token de usuário vs. bot/app (scopes necessários, o que a política de workspace costuma permitir), rate limits, DMs, MCP servers existentes. O usuário consegue criar tokens/apps no workspace do trabalho.
- **Histórico de navegador** (Chrome/Edge): onde ficam os SQLite no Windows, como ler com o navegador aberto (lock do arquivo), o que se extrai (URL, título, timestamps).
- Para cada fonte: custo (todas deveriam ser R$ 0?), fragilidade, e cadência natural de leitura (sob demanda/retroativa — nada precisa ficar "ligado").

O resultado alimenta [Decidir as integrações de fontes passivas](13-decidir-fontes-passivas.md).

## Answer

As quatro fontes fecham em R$ 0 e todas suportam leitura retroativa sob demanda — nenhuma exige processo residente. Detalhes em [../research/12-fontes-passivas.md](../research/12-fontes-passivas.md).

- **Git local**: trivial — varrer pastas `.git` sob os diretórios de dev e rodar `git -C <repo> log --author=<regex> --since --all --no-merges --pretty=format:...`. Pegadinhas: e-mail de autor varia por repo (usar regex/`.mailmap` ou ler `user.email` de cada repo), shallow clones truncam contagens semanais, e `--date=iso-local` para agrupar por dia.
- **Linear**: caminho limpo. Personal API Key pode ser **read-only e restrita a times**, não expira; GraphQL em `api.linear.app/graphql` lê issues atribuídas, comentários, projetos, cycles e histórico de atividade com filtro `updatedAt`. Rate limit folgado (2.500 req/h). Bônus: MCP oficial remoto com endpoint **readonly** (`mcp.linear.app/mcp/readonly`) que aceita a própria API key.
- **Slack**: viável, mas é a fonte com dependência de política corporativa. Melhor rota: app **interna** própria com **user token (xoxp)** e scopes `channels:history, groups:history, im:history, mpim:history` (+`*:read`) — lê tudo que o usuário vê, inclusive DMs. Os novos rate limits punitivos de 2025/26 (1 req/min) atingem só apps *distribuídas* não-Marketplace; **apps internas continuam Tier 3 (~50/min, 1.000 msgs/req)**. Existe MCP oficial (`mcp.slack.com/mcp`, requer aprovação de admin) e o community korotovsky/slack-mcp-server como plano B.
- **Navegador**: SQLite em `%LOCALAPPDATA%\Google\Chrome\User Data\Default\History` (Edge: `...\Microsoft\Edge\...`), tabelas `urls`/`visits`, timestamps WebKit (`visit_time/1e6 - 11644473600`). Com o browser aberto o arquivo trava — **copiar antes de ler**. Bibliotecas prontas: `browser-history`, `browserexport`. Histórico expira em ~90 dias, folga ampla para leitura diária/semanal.
