# 05 — Coletor do Slack

**What to build:** `fonte_slack.py`: a implementação de `PortaFonte` que lê as conversas de
que o usuário participa na janela — canais, DMs e group DMs —, respeitando a blocklist. App
interna com user token `xoxp`. É a última fonte por depender de aprovação de admin no
workspace, e o diário já nasce sem ela.

**Blocked by:** 01

**Status:** resolved

- [x] Lista as conversas do usuário e lê o histórico na janela, incluindo threads
- [x] **Blocklist aplicada antes da busca**: conversa em `[slack].conversas_excluidas` não é sequer consultada — é a primeira camada do filtro de privacidade, e o teste precisa provar que nenhuma requisição foi feita para ela
- [x] Traduz mensagens para `Evento`: `titulo` com quem falou, `detalhe` com o texto, `referencia` = nome do canal ou da conversa, `url` = permalink quando houver, `momento` aware no fuso local
- [x] Nomes de pessoas resolvidos a partir dos ids, para o diário não ficar cheio de `U01234`
- [x] Paginação e rate limit tratados: respeita `Retry-After` em 429 em vez de desistir na primeira
- [x] Token ausente, token inválido, escopo faltando e erro de API viram `ErroDeFonte` com mensagem em português que diga o que fazer
- [x] `de_configuracao(configuracao) -> FonteSlack` e `nome = "slack"`, como no contrato
- [x] Testes de tradução sem rede, a partir de payloads gravados: canal, DM, thread, resposta paginada, 429 com `Retry-After`, e a blocklist
- [x] Um teste `@pytest.mark.rede` que pula limpo sem `[slack].user_token`
- [x] Roteiro de smoke manual em `docs/smoke-slack.md`: criar a app interna, os user scopes mínimos, o que dizer ao admin ao pedir aprovação, e como conferir com `second-brain diario --simular`
- [x] Acrescenta **só** o teste do ramo `slack` de `montar_fontes`

## Notas para o executor

- **Re-cheque a política antes de codar.** A [pesquisa](../../second-brain/research/12-fontes-passivas.md)
  é de agosto de 2026 e o alicerce do plano é a exceção de rate limit para *internal
  customer-built applications*: apps distribuídas fora do Marketplace caíram para 1
  request/min e 15 mensagens/request, as internas mantiveram o Tier 3. Se isso mudou, pare e
  surfaceie ao orquestrador antes de construir.
- Scopes mínimos e justificáveis: `channels:history`/`channels:read`,
  `groups:history`/`groups:read`, `im:history`/`im:read`, `mpim:history`/`mpim:read`,
  `users:read`. `search:read` **não** é necessário para este caso de uso — e é dos que mais
  levantam bandeira na revisão do admin. Não peça.
- Nunca use token de sessão de browser (`xoxc`/`xoxd`): viola os termos.
- O token é segredo: fixture usa `xoxp-EXEMPLO`; nada de token em log nem em mensagem de erro.
- `httpx` já é dependência. Nada novo.

## Comments

**Camada 05 entregue** — `fonte_slack.py`, `tests/test_fonte_slack.py` (61 testes), 8 fixtures de
payload e `docs/smoke-slack.md`. Nenhum arquivo compartilhado tocado. Suite em 465 verdes.

A checagem que podia parar a camada foi feita: **a excecao de rate limit para apps internas
continua valendo**, entao o desenho nao mudou. O aperto de maio de 2025 (1 req/min, 15 objetos)
atinge so apps distribuidas comercialmente fora do Marketplace.

**Fechada pelo orquestrador.** Provas conferidas, nao so reportadas:

- **A politica, na fonte.** Busquei a pagina oficial de rate limits eu mesmo, em vez de aceitar a
  citacao: a frase "Apps already approved for the Slack Marketplace and internal customer-built
  applications should not see rate limit changes" esta la. O alicerce do plano esta de pe.
- **A blocklist, sondada por fora.** Montei um transporte que registra toda requisicao que sai,
  com um canal privado na blocklist: das cinco requisicoes, **nenhuma** carregou o id bloqueado —
  so `auth.test`, a listagem, e o `history` das duas conversas permitidas. A conversa bloqueada
  nao e consultada, que e a promessa; filtrar depois nao teria o mesmo valor.
- **Mutacao na blocklist** (`_bloqueada` sempre falso): 6 testes caem, incluindo os quatro
  dedicados a ela e o da secao do diario.
- **Vazamento de token, sonda propria**: com uma isca em `invalid_auth`, `missing_scope`, HTTP 500
  e HTTP 403, o token nao aparece em nenhuma mensagem, nenhuma excecao crua do `httpx` escapa, e
  o token nao vai em URL nenhuma (fica no header, correto).
- `pytest` 465 verdes, 6 desselecionados; o teste de rede pula limpo sem token.

Decisao do executor que merece registro: **o log conta quantas conversas a blocklist bloqueou,
nunca quais**. O nome de uma conversa que o usuario mandou nunca ler nao pode acabar no
`bandeja.log`. Isso nao estava no contrato e esta certo.

**O que nao foi provado**: nada rodou contra um workspace real — o usuario ainda nao tem a app
interna aprovada. As fixtures vieram dos exemplos da documentacao, nao de um workspace. Os
scopes serem aceitos, o permalink abrir a mensagem certa e o rate limit real ficam para o smoke
(`docs/smoke-slack.md`, passos 6 a 8).
