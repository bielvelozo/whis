# 03 — STT real: adapter Deepgram

**What to build:** A transcrição de verdade: um adapter da porta de STT que envia os canais gravados para a Deepgram (Nova-3 multilingual, batch) e devolve a transcrição com a distinção "eu vs. os outros" derivada dos canais separados. A API key vem da configuração local (crédito de US$ 200 — custo real zero). Demo: processar uma gravação real com o pipeline do ticket 01 e ler a transcrição verdadeira, com falantes, no vault. Falha de rede/STT não pode produzir nota parcial — a gravação permanece intacta e o erro é sinalizado de forma legível.

**Blocked by:** 01 — Esqueleto do pipeline com portas fake.

**Status:** ready-for-human

- [ ] Pipeline com o adapter real transcreve uma gravação de teste em pt-BR com termos em inglês corretamente
- [x] Transcrição distingue a fala do usuário da dos demais participantes
- [x] API key e opções vêm de configuração local; nenhum segredo no repo
- [x] Falha do STT preserva a gravação, não escreve nota parcial e loga o erro de forma diagnosticável
- [x] Testes da costura continuam verdes com o fake; o adapter real tem verificação própria mínima (ex.: teste marcado/manual contra a API)

## Comments

**Entregue** (camada 03, executor) — `src/second_brain/stt_deepgram.py`, `tests/test_stt_deepgram.py`,
`tests/fixtures/resposta_deepgram_*.json`, mais testes de falha de STT na costura em
`tests/test_pipeline.py`. Suíte: `114 passed, 3 deselected`.

**Como ficou.** Cada canal vai para a Deepgram numa requisição própria: `microfone.wav` → `EU`,
`sistema.wav` → `OUTROS`. As falas dos dois canais são fundidas por tempo, somando o
`offset_inicio_s` que o `gravacao.json` declara para cada canal. Nenhuma diarização é pedida —
a separação de canais já dá a distinção, e o add-on custa US$ 0,0020/min a mais.

**Parâmetros fixados**, conferidos na documentação oficial em 2026-08-20:

| Parâmetro | Valor | Documentação |
|---|---|---|
| endpoint | `POST https://api.deepgram.com/v1/listen` | https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded |
| auth | `Authorization: Token <api_key>` | idem |
| corpo | bytes do WAV, `Content-Type: audio/wav` | https://developers.deepgram.com/docs/pre-recorded-audio |
| `model` | `nova-3` | https://developers.deepgram.com/docs/models-languages-overview |
| `language` | `multi` | https://developers.deepgram.com/docs/multilingual-code-switching |
| `smart_format` | `true` | https://developers.deepgram.com/docs/smart-format |
| `utterances` | `true` | https://developers.deepgram.com/docs/utterances |

A documentação confirma que `nova-3` + `language=multi` cobre **português e inglês** no mesmo
áudio (a pesquisa registrava isso do nova-2, que só fazia es+en).

**Erros.** Rede caída, timeout, 400/401/402/403/413/429/504/5xx, corpo não-JSON e resposta sem
`results` viram `ErroDeSTT` com mensagens distintas — chave inválida diz para conferir
`[deepgram].api_key`, 402 fala de crédito, 413 fala de tamanho, timeout fala de upload lento.
O `err_code`/`err_msg`/`request_id` da Deepgram entram na mensagem, que o pipeline grava em
`estado.json`.

**O que ainda não dá para provar aqui.** Não há chave da Deepgram nesta máquina e o destino é
outro PC. Os dois testes `@pytest.mark.rede` estão escritos para rodar lá:
`test_rede_transcreve_o_audio_de_exemplo_da_deepgram` (áudio de exemplo da própria Deepgram, prova
chave + endpoint + parâmetros) e `test_rede_gravacao_real_em_pt_br_vira_nota_no_vault` (aponte
`SECOND_BRAIN_GRAVACAO_DE_TESTE` para uma pasta de gravação real e rode `pytest -m rede`). Sem
chave, pulam.

**Fiação na CLI** (não feita — território do orquestrador):
`from second_brain.stt_deepgram import de_configuracao; stt = de_configuracao(configuracao)`.

**Deferidos** anotados em `DEFERRED.md`: sem compressão do áudio, WAV inteiro em memória,
`keyterm` não usado, `mip_opt_out` no padrão, sem retry para 429/5xx, guarda dos testes de rede
divergente entre camadas, e ausência de gravação de referência no repositório.

**Revisão do orquestrador — adaptador aceito e commitado; um critério só fecha na
máquina de destino, e uma decisão foi para o usuário.**

Conferido por mim: 114 testes verdes com 3 desselecionados; nenhuma credencial
real em `src/`, `tests/` ou nas fixtures; os parâmetros enviados são exatamente
`model=nova-3`, `language=multi`, `smart_format=true`, `utterances=true`, e a
fusão mapeia `microfone.wav → EU` e `sistema.wav → OUTROS`, que é a separação por
canais que a spec exige.

Aceita a análise do executor sobre `multichannel=true`: mixar os dois canais num
estéreo exigiria resample no adaptador, o que contradiz o contrato (cada canal na
taxa nativa, sem resample) e não reduz o custo por minuto. Fica como está.

Dois achados que corrigem a pesquisa `03-captura-audio-stt.md`: o `language=multi`
do nova-3 cobre português+inglês (a pesquisa registrava só es+en, que era o
nova-2), e `diarize` está deprecado — como não pedimos diarização nenhuma, o
custo cai de US$ 0,0112 para US$ 0,0092 por minuto (≈ R$ 60/mês em vez de R$ 73,
e de qualquer forma dentro do crédito).

**Decisão levada ao usuário:** na modalidade pay-as-you-go, onde o crédito de
US$ 200 vive, a Deepgram opta o cliente **por padrão** no Model Improvement
Program — o áudio enviado pode ser retido e usado para treinar os modelos deles.
O adaptador hoje não manda `mip_opt_out`. Isso tensiona a user story 13 (áudio
retido 7 dias e apagado, por privacidade) e é decisão do dono das reuniões, não
do agente. Fonte: https://developers.deepgram.com/docs/the-deepgram-model-improvement-partnership-program

**O que só fecha na máquina de destino, com a chave:** que a chave autentica, que
a Deepgram aceita estes parâmetros e que a transcrição pt/en sai correta. Os dois
testes marcados `rede` existem para isso e pulam sem chave.

**Status ajustado para `ready-for-human` no fechamento da camada 06.** Todo o
código do adaptador está aceito e commitado; o único critério aberto — transcrever
pt-BR com termos em inglês corretamente — depende da chave da Deepgram na máquina
de destino, exatamente como o smoke da camada 02 depende de um Meet real. Não há
trabalho de agente pendente aqui.

**Primeira execução com a chave real (orquestrador, 2026-09-02).** A chave do
usuário entrou na configuração e os dois testes `rede` passam: o áudio de exemplo
da Deepgram é transcrito e o Claude resume pela conta OAuth. Consertei um bug do
próprio teste no caminho — `httpx.get("https://dpgr.am/spacewalk.wav")` sem
`follow_redirects=True` baixava 0 byte, e a Deepgram respondia HTTP 400 ("corrupt
or unsupported data") em vez de transcrever.

Também rodei a costura completa com adaptadores reais contra um diálogo pt-BR
**sintetizado** pelo TTS do Windows (voz pt-BR Maria), dois canais separados, com
termos em inglês de propósito. Deepgram e Claude responderam 200; a fusão por
tempo, os rótulos `eu`/`outros` e o resumo saíram corretos (o Claude inferiu
`participantes: [Gabriel, Ana]` da conversa).

**Achado com evidência, sobre o critério 1.** A transcrição **perdeu** boa parte
dos termos em inglês. Conferi a resposta crua da Deepgram: a perda é dela, não do
adapter — o `transcript` já vem sem as palavras, com `languages: ['pt']` e
confiança 0,99.

| pedido | sem `keyterm` | com `keyterm` |
|---|---|---|
| "esperar o code review" | "esperar o." | "esperar o code review" |
| "subo o release em staging depois do review" | "subo o depois do," | "subo o release and stage depois do review" |
| "decide o rollback amanhã" | "decide o rolar amanhã" | "decide o rollback amanhã" |

Duas chamadas ao mesmo WAV, só mudando `keyterm=code review&keyterm=rollback&...`
— e `keyterm` **funciona junto com `language=multi`** (não dá 400), o que a
documentação não deixava claro. Isso promove o item do `DEFERRED.md` sobre
`keyterm` de "seria bom" a provável pré-requisito do critério 1.

**Ressalva honesta:** o áudio é TTS pt-BR pronunciando inglês com fonética
portuguesa — o pior caso possível para code-switching. Fala humana real, com
pronúncia inglesa nos termos ingleses, pode se comportar melhor sem `keyterm`. O
critério 1 continua aberto e só o smoke com Meet real decide.
