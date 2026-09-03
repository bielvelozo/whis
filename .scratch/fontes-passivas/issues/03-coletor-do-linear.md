# 03 — Coletor do Linear

**What to build:** `fonte_linear.py`: a implementação de `PortaFonte` que lê a movimentação
do(s) time(s) do usuário no Linear dentro da janela — issues que andaram, comentários e
mudanças de estado —, não só a atividade própria. API GraphQL com Personal API Key
**read-only**.

**Blocked by:** 01

**Status:** resolved

- [x] Consulta GraphQL a `https://api.linear.app/graphql` com header `Authorization: <API_KEY>` (sem `Bearer`), filtrando por `updatedAt` dentro da janela
- [x] Traduz issues, comentários e mudanças de estado para `Evento`: `titulo` legível (identificador + título + o que mudou), `referencia` = time ou projeto, `url` = link da issue, `pessoas` = quem agiu, `momento` aware no fuso local
- [x] Paginação tratada — um dia movimentado passa de uma página
- [x] Chave ausente, chave inválida, HTTP 4xx/5xx e timeout viram `ErroDeFonte` com mensagem em português que diga o que fazer
- [x] `de_configuracao(configuracao) -> FonteLinear` e `nome = "linear"`, como no contrato
- [x] Testes de tradução sem rede: payload JSON gravado como fixture → `Evento`, cobrindo issue, comentário, mudança de estado, resposta paginada e resposta de erro
- [x] Um teste `@pytest.mark.rede` que só roda de propósito, pulando limpo quando `[linear].api_key` está vazia
- [x] Roteiro de smoke manual em `docs/smoke-linear.md`: como criar a Personal API Key read-only, onde colar, e o que conferir na saída de `second-brain diario --simular`
- [x] Acrescenta **só** o teste do ramo `linear` de `montar_fontes`

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

## Comments

**Camada 03 entregue** — `fonte_linear.py`, `tests/test_fonte_linear.py` (44 testes), quatro
fixtures de payload e `docs/smoke-linear.md`. Nenhum arquivo compartilhado tocado.

Duas correcoes a pesquisa de agosto, conferidas na documentacao oficial: o caminho na UI virou
**Settings → Account → Security & Access**, e os cabecalhos de cota sao
`X-RateLimit-Requests-Remaining` e `X-RateLimit-Complexity-Remaining`. Endpoint, header sem
`Bearer` e limites continuam valendo.

Desvio surfaceado e aceito: **comentarios sao filtrados por `createdAt`, nao `updatedAt`**. O
ticket pedia `updatedAt`, mas o contrato exige que `momento` caia na janela — um comentario de
semana passada editado hoje teria `updatedAt` dentro e `createdAt` fora.

**Fechada pelo orquestrador.** Provas conferidas, nao so reportadas:

- Mutei o header para `Bearer <chave>` — o erro classico com API key do Linear, que so
  apareceria contra a API real: dois testes caem.
- Mutei o recorte de janela dos comentarios: dois testes caem.
- Sondei vazamento de segredo eu mesmo, com chave-isca em 400/401/403/429/500/503: a chave nao
  aparece em nenhuma mensagem e nenhuma excecao crua do `httpx` escapa para a costura.
- `pytest` 405 verdes; o teste de rede pula limpo sem chave.

**Um achado do relatorio estava errado e foi corrigido no DEFERRED.** O executor anotou que
`montar_fontes` nao tem teste do caso "nada configurado". Tem:
`tests/test_comando_diario.py::test_comando_diario_sem_fonte_configurada_falha_com_mensagem`,
pela costura da CLI, que e o estilo da casa. Eles procuraram um teste *nomeado* `montar_fontes`.
Provei que morde (mutar `montar_fontes` para devolver lista vazia derruba o teste) e marquei a
linha como alarme falso, com a evidencia.

Falta a prova contra a API real: o usuario ainda nao tem chave do Linear. Fica no smoke.
