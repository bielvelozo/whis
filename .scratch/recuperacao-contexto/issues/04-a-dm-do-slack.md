# 04 — A DM do Slack

**What to build:** `second-brain atender` — o processo que fica escutando a DM do bot no Slack por
Socket Mode, responde ali e mantém o fio de 24 horas. **É a entrega inteira do ponto de vista do
usuário**; as três camadas anteriores existem para esta funcionar.

Contrato: **[contrato-busca.md](../contrato-busca.md)**, seções 3 e 5.

**Blocked by:** 01, 02, 03, **e a aprovação do admin do Slack**

**Status:** resolved

- [x] `atendente.py`: recebe evento de mensagem, chama `responder`, publica a resposta na mesma DM
- [x] **Socket Mode**, com app-level token (`xapp-`) e bot token (`xoxb-`) em chaves novas de
      `[slack]`. Conexão de dentro para fora, sem porta aberta
- [x] O bot **reage à mensagem** assim que a recebe: uma busca demora, e silêncio parece pane
- [x] Só atende **DM com ele mesmo**; mensagem em canal é ignorada
- [x] Ignora as próprias mensagens, senão responde a si mesmo em laço
- [x] O fio de 24h da camada 01, por conversa
- [x] Falha de uma resposta não derruba o processo: vira mensagem de erro em português na DM e o
      atendimento continua
- [x] Reconecta sozinho quando a conexão cai — é um processo que fica no ar o dia inteiro
- [x] `second-brain atender` sobe o processo; **testado sem Slack**, com o cliente injetado e
      eventos de fixture
- [x] Suíte verde (**849**, eram 793), sem editar teste existente

## Notas para o executor

- **Não coloque isto dentro da bandeja.** Ela tem trava de instância e máquina de estados de
  gravação, e o pipeline de reunião está em uso real. Processo separado.
- O passo humano está no `docs/smoke-atendente.md` (camada 05) e **precisa de aprovação nova do
  admin**, porque o roteiro atual promete que a app não pede bot token.
- Escrita em `notas/` só sob pedido explícito na conversa, por `vault.escrever` com
  `zonas=(PASTA_NOTAS,)`.

## Comments

**Camada 04 construída e provada sem Slack** (2026-09-04). O que falta é **humano**: o bot na
app, os dois tokens e a demo pela DM — por isso `ready-for-human`, e não `resolved`.

Entregue: `atendente.py` (a porta `PortaDM`, o laço, o filtro do que é atendido, o fio por
DM, o `anotar`), `dm_slack.py` (Socket Mode pelo `slack_sdk`, dependência nova no
`pyproject.toml`), `DMFake` em `fakes.py`, `[slack].bot_token` e `[slack].app_token` em
`configuracao.py` com conferência de prefixo e no `MODELO_DE_CONFIGURACAO`, `second-brain
atender [--fakes]` em `__main__.py`, e 56 testes novos em quatro arquivos. Suíte em **849
verdes**, 8 desselecionados, nenhum teste existente editado.

**Decisões que o ticket deixou em aberto:**

- **`slack_sdk`** entrou como dependência: o ambiente não tinha cliente de websocket nenhum, e
  escrever um à mão para falar Socket Mode seria o tipo de código que dá errado às 3 da manhã.
  É o SDK oficial, e o cliente de Socket Mode dele não puxa dependência extra.
- **Reconexão é do SDK** (`auto_reconnect_enabled=True`, padrão). Está no checklist como feito
  porque é comportamento do cliente, mas **não há teste nosso** para isso — só a confiança no
  SDK e o teste de que uma falha de resposta não derruba o laço.
- **`anotar <texto>` na DM** é a escrita em `notas/`: um prefixo explícito, sem passar pelo
  modelo, pelo mesmo `vault.anotar_ponto` do `daily --anotar`. Pedido explícito **na
  conversa**, como o contrato manda, sem depender de o modelo decidir se era pedido.
- **`--fakes` no `atender` troca só a busca**: a DM continua sendo o Slack de verdade. É como
  o usuário ensaia a app aprovada sem gastar a assinatura, antes da demo-mestra.
- **Trava própria** (`atendente.lock`), separada da bandeja: dois atendentes responderiam
  cada pergunta duas vezes.
- **`configuracao.py` foi editado** por esta camada, contra a regra da seção 6 do contrato: as
  duas chaves do Slack estavam no ticket e não existiam na camada 01. Registrado na seção 11.

**Provas executadas:**

- **Mutação, 20 linhas**: atende qualquer canal → 2; atende outro bot → 1; responde a si mesmo
  → 1; atende mensagem editada → 1; atende texto vazio → 1; não reage → 2; erro de busca
  derruba → 1; exceção inesperada derruba → 1; fio não é guardado → 3; anotar não escreve → 3;
  anotar não é reconhecido → 4; não achou sem aviso → 1; fontes não vão na resposta → 2; link
  markdown vai cru → 1; trava ignorada → 1; envelope não é confirmado → 3; evento que não é
  mensagem vira mensagem → 2; reação repetida vira erro → 1; prefixo do token não é conferido
  → 3; `atender` não liga o log antes da busca → 1. Nenhuma sobreviveu.
- **O laço sobrevive a tudo que foi injetado**: busca que levanta `ErroDeBusca`, busca que
  levanta `RuntimeError`, DM que falha ao reagir, DM que falha ao publicar — em todos os casos a
  mensagem seguinte é atendida, e a mensagem de erro na DM é em português sem o detalhe
  técnico (que vai ao log).
- **O envelope do Socket Mode é confirmado antes de enfileirar**, também para envelope que não
  é mensagem — o Slack reenvia o que não é confirmado, e um reenvio viraria resposta dupla.
- **O `--help` e o `atender` sem tokens** dizem o que falta e onde está o roteiro.

**Não provado — e é o que fecha a entrega**: nenhuma mensagem real na DM. Depende do passo
humano do `docs/smoke-atendente.md` (camada 05): bot na app com `im:history`, `im:read`,
`chat:write`, `reactions:write`, Socket Mode ligado, `message.im` assinado, app-level token
com `connections:write`, e a aprovação nova do admin. Depois: `second-brain atender --fakes`
prova o Slack sem gastar a assinatura; `second-brain atender` faz a demo-mestra.

### Entrega — provado na maquina do usuario, 2026-09-10

O passo humano foi feito com o usuario na sessao, e a DM funcionou de ponta a ponta.

**O Slack, sem gastar nada** (`atender --fakes`): a mensagem ganhou 👀 em um ou dois segundos
e a resposta de exemplo chegou. Prova junta: `reactions:write`, `chat:write`, Socket Mode de
pe, `message.im` assinado e a Messages Tab liberada. O bot subiu como `U0C0AJXB59V` e so a DM
`D0C1LAWCNHE` foi atendida.

**O Claude de verdade**: a primeira pergunta real custou o equivalente a **US$ 0,5589**, com 18
turnos, **17 chamadas de ferramenta** e 63 s, e voltou com 7 citacoes de 4 notas. As 17 chamadas
fecham o risco que este ticket deixou aberto: `mcp__vault__<ferramenta>` em `allowed_tools` casa
com o que o SDK espera, e nao era so convencao do Claude Code.

**O fio de 24h**: provado pela porta dos fundos. A resposta do ensaio com `--fakes` ficou no
`conversas.json`, e a primeira pergunta real abriu com *"Correcao do que eu disse antes: nao
achei essa decisao em nenhuma nota de reuniao"* — o agente leu o turno anterior, foi conferir e
desmentiu o fake. Funciona; e o fake contaminar o fio virou achado no DEFERRED.

**A fonte ao vivo**: perguntado sobre a ultima hora no Slack, citou com origem `slack:DM com
Whis`, e nao com caminho de nota. Veio do coletor, nao do vault.

**O que o uso real revelou**, tudo no DEFERRED: a resposta e longa demais e o bloco de fontes
incomoda (dito pelo usuario no celular); o agente le a propria DM como fonte ao vivo, inclusive
os proprios erros; imagem e audio na DM sao ignorados em silencio; e o OAuth da conta Claude
vence e derruba tudo que fala com o modelo — aconteceu no meio da demo, as 19:45.

Nota de contexto: o projeto foi rebatizado de Second Brain para **Whis** em 2026-09-09, no meio
deste fechamento. Os comandos citados acima em documentos antigos aparecem como `second-brain`.
