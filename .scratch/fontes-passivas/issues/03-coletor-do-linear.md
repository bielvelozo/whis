# 03 — Coletor do Linear

**What to build:** `fonte_linear.py`: a implementação de `PortaFonte` que lê a movimentação
do(s) time(s) do usuário no Linear dentro da janela — issues que andaram, comentários e
mudanças de estado —, não só a atividade própria. API GraphQL com Personal API Key
**read-only**.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Consulta GraphQL a `https://api.linear.app/graphql` com header `Authorization: <API_KEY>` (sem `Bearer`), filtrando por `updatedAt` dentro da janela
- [ ] Traduz issues, comentários e mudanças de estado para `Evento`: `titulo` legível (identificador + título + o que mudou), `referencia` = time ou projeto, `url` = link da issue, `pessoas` = quem agiu, `momento` aware no fuso local
- [ ] Paginação tratada — um dia movimentado passa de uma página
- [ ] Chave ausente, chave inválida, HTTP 4xx/5xx e timeout viram `ErroDeFonte` com mensagem em português que diga o que fazer
- [ ] `de_configuracao(configuracao) -> FonteLinear` e `nome = "linear"`, como no contrato
- [ ] Testes de tradução sem rede: payload JSON gravado como fixture → `Evento`, cobrindo issue, comentário, mudança de estado, resposta paginada e resposta de erro
- [ ] Um teste `@pytest.mark.rede` que só roda de propósito, pulando limpo quando `[linear].api_key` está vazia
- [ ] Roteiro de smoke manual em `docs/smoke-linear.md`: como criar a Personal API Key read-only, onde colar, e o que conferir na saída de `second-brain diario --simular`
- [ ] Acrescenta **só** o teste do ramo `linear` de `montar_fontes`

## Notas para o executor

- A [pesquisa](../../second-brain/research/12-fontes-passivas.md) é de agosto de 2026 —
  **confira o que ainda vale** antes de codar: endpoint, formato do header, escopo
  read-only por time e os limites (2.500 requests/h, 3.000.000 pontos/h, máximo 10.000
  por query).
- Usa `httpx`, que já é dependência. Nada novo.
- A chave é segredo: nunca em teste, fixture, log ou mensagem de erro. Fixture usa
  `lin_api_EXEMPLO`.
- `filter: { updatedAt: { gte: ... } }` é o recorte retroativo limpo; a janela tem
  `inicio` e `fim`, use os dois — o `fim` importa quando o usuário gera o diário de uma
  data passada.
