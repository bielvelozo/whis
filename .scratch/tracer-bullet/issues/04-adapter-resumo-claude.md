# 04 — Resumo real: adapter Claude

**What to build:** O resumo de verdade: um adapter da porta de resumo que envia a transcrição ao Claude (via conta Pro/Max do usuário, Claude Agent SDK — padrão validado no Whis) e devolve o resumo em português estruturado em decisões, ações/pendências e tópicos, que o pipeline grava na nota de reunião. Demo: uma nota de reunião real, legível e útil, aberta no Obsidian.

**Blocked by:** 01 — Esqueleto do pipeline com portas fake.

**Status:** resolved

- [x] Resumo em português cobrindo decisões, ações/pendências e tópicos da reunião
- [x] Autenticação pela conta Claude do usuário (OAuth), sem API key paga à parte
- [x] Falha na geração do resumo não perde a transcrição — nota pode ser regenerada
- [x] Testes da costura continuam verdes com o fake; o adapter real tem verificação própria mínima

## Comments

**Entregue** — `src/second_brain/resumo_claude.py` (`ResumoClaude`), com testes em
`tests/test_resumo_claude.py`, testes de falha de resumo na costura em
`tests/test_pipeline.py` e a chave `[claude] modelo` em
`src/second_brain/configuracao.py`. Suíte: 114 passaram, 3 puladas.

Como ficou:

- Um turno só via **Claude Agent SDK** (`query`), sem ferramenta, sem skill, sem
  `setting_sources` e com `strict_mcp_config` — o resumo depende só da
  transcrição, aqui e na máquina de destino.
- Prompt em português pedindo **JSON** com `titulo`, `participantes`, `decisoes`,
  `acoes`, `topicos`, e mandando preservar os termos em inglês como foram ditos.
  Falha de parse é `ErroDeResumo` com a resposta crua no log.
- **OAuth ou nada**: se `ANTHROPIC_API_KEY` ou `ANTHROPIC_AUTH_TOKEN` estiver no
  ambiente, `verificar_credencial()` recusa a chamada antes de gastar dinheiro do
  usuário, dizendo qual variável remover.
- `modelo=None` por padrão (o modelo da conta escolhido pelo CLI), fixável pela
  configuração — a máquina de destino pode ter outro plano.

**Verificado contra o Claude de verdade** nesta máquina (conta OAuth, sem API
key): transcrição pt-BR com code-switching devolveu 1 decisão, 2 ações e 3
tópicos em português, com `deploy`/`review`/`rollback`/`issue` preservados e os
participantes inferidos da conversa (`Ana`, `Bruno`).

**Não implementado de propósito**: o critério "falha no resumo não perde a
transcrição" hoje é atendido só até onde o pipeline permite — a gravação fica
retida e a nota pode ser regenerada, mas a transcrição em si (que custou API) é
recalculada no reprocesso. Mudar isso é mexer em `pipeline.py`, que não é deste
ticket; a recomendação foi entregue ao orquestrador.

Deferidos registrados no `DEFERRED.md`: resumo em partes para transcrição longa,
`addopts` sem `-m "not rede"`, ausência de retry, e custo/uso do SDK descartado.

**Revisão do orquestrador — adaptador aceito e commitado; a camada não fecha ainda.**

Provas que executei eu mesmo, não apenas recebi: chamada real ao Claude pelo
teste marcado `rede`, com o ambiente sem nenhuma variável `ANTHROPIC_*` — logo a
autenticação só pode ter sido o OAuth da conta do usuário. E o pipeline completo
com o adaptador real de resumo produziu esta nota, que li no disco:

- `participantes: [Bruno, Ana]` — nomes reais inferidos da conversa, no
  frontmatter, em vez de `eu`/`outros`.
- Decisões, ações e tópicos corretos e úteis, em português, com os termos técnicos
  preservados como foram ditos (deploy, rollback plan, review, smoke test,
  staging, blocker, release) — o code-switching que a spec exige.

**Achado de processo corrigido pelo orquestrador:** o marcador `rede` não
desselecionava nada (`addopts` era só `-q`), então um teste marcado falava com o
Claude de verdade dentro da suíte normal. `addopts` passou a `-q -m "not rede"`.
Verificado: `pytest` dá 114 passed, 3 deselected; `pytest -m rede` coleta os 3.

**O que falta para a camada fechar — critério 3.** Hoje `processar()` transcreve,
resume e só então escreve. Uma falha no resumo descarta a `Transcricao` em
memória, e o reprocesso chama a Deepgram de novo: paga crédito e tempo de API por
uma falha que não foi dela. A gravação sobrevive, mas a transcrição não.

Decisão do orquestrador, entre as duas opções que o executor levantou: **guardar a
transcrição como JSON dentro da própria pasta de gravação**, ao lado do
`estado.json`, e o reprocesso lê de lá. Descartada a alternativa de escrever a
transcrição no vault antes do resumo, porque ela cria um wikilink quebrado no
Obsidian enquanto a nota não existe. A opção escolhida não mexe nas zonas de
propriedade e casa com "gravação com falha fica retida indefinidamente".

**Essa mudança foi atribuída à camada 06** (retenção e reprocesso), dona natural
do reprocesso idempotente. O critério 3 deste ticket fecha quando eu revalidar o
ciclo falha-do-resumo → reprocesso sem nova chamada de STT.

**Critério 3 fechado no fechamento da camada 06.** O `transcricao.json` decidido
aqui foi construído lá: o pipeline guarda a transcrição na pasta de gravação
assim que o STT devolve, antes de qualquer tentativa de resumo. Revalidei o ciclo
eu mesmo, com um STT que conta chamadas — resumo quebrado na primeira passada,
resumo saudável na segunda, **1 chamada de STT no total**, transcrição
reaproveitada e status final `transcrito`. A camada está resolvida.
