# 05 — Coletor do Slack

**What to build:** `fonte_slack.py`: a implementação de `PortaFonte` que lê as conversas de
que o usuário participa na janela — canais, DMs e group DMs —, respeitando a blocklist. App
interna com user token `xoxp`. É a última fonte por depender de aprovação de admin no
workspace, e o diário já nasce sem ela.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Lista as conversas do usuário e lê o histórico na janela, incluindo threads
- [ ] **Blocklist aplicada antes da busca**: conversa em `[slack].conversas_excluidas` não é sequer consultada — é a primeira camada do filtro de privacidade, e o teste precisa provar que nenhuma requisição foi feita para ela
- [ ] Traduz mensagens para `Evento`: `titulo` com quem falou, `detalhe` com o texto, `referencia` = nome do canal ou da conversa, `url` = permalink quando houver, `momento` aware no fuso local
- [ ] Nomes de pessoas resolvidos a partir dos ids, para o diário não ficar cheio de `U01234`
- [ ] Paginação e rate limit tratados: respeita `Retry-After` em 429 em vez de desistir na primeira
- [ ] Token ausente, token inválido, escopo faltando e erro de API viram `ErroDeFonte` com mensagem em português que diga o que fazer
- [ ] `de_configuracao(configuracao) -> FonteSlack` e `nome = "slack"`, como no contrato
- [ ] Testes de tradução sem rede, a partir de payloads gravados: canal, DM, thread, resposta paginada, 429 com `Retry-After`, e a blocklist
- [ ] Um teste `@pytest.mark.rede` que pula limpo sem `[slack].user_token`
- [ ] Roteiro de smoke manual em `docs/smoke-slack.md`: criar a app interna, os user scopes mínimos, o que dizer ao admin ao pedir aprovação, e como conferir com `second-brain diario --simular`
- [ ] Acrescenta **só** o teste do ramo `slack` de `montar_fontes`

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
