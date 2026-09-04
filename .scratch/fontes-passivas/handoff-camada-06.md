# Handoff: acabamento da entrega de fontes passivas (camada 06)

Documento de continuação. Escrito em 2026-09-03, no fim da sessão que construiu as camadas
01, 02, 03, 04, 05 e 07 da entrega de fontes passivas. Assume **zero contexto**: leia isto
inteiro antes de tocar em qualquer coisa.

Seu trabalho: **fechar a camada 06** — a última. Ela é pequena e está especificada em
`.scratch/fontes-passivas/issues/06-acabamento-e-uso-real.md`.

---

## 1. Onde a entrega está

**Sete das oito camadas estão fechadas e commitadas.** A suíte tem **538 testes verdes**
(7 desselecionados, todos `@pytest.mark.rede`). O código do pacote está em ~9.200 linhas.

| Camada | O que entregou | Estado |
|---|---|---|
| 01 esqueleto do diário | a costura `gerar_diario`, tipos, filtro, janela, zona de propriedade por coletor, todas as chaves de configuração | fechada |
| 02 coletor de git | varredura de repositórios + `git log` por autor | fechada |
| 03 coletor do Linear | GraphQL read-only, issues, comentários, mudanças de estado | fechada |
| 04 resumo do dia | adaptador Claude por OAuth, com custo em log | fechada |
| 05 coletor do Slack | app interna `xoxp`, blocklist antes da leitura | fechada |
| 07 daily | `gerar_daily`, janela da última fala até agora, `notas/daily.md` | fechada |
| **06 acabamento** | log, códigos de saída, smoke | **é o seu trabalho** |

Cada ticket em `.scratch/fontes-passivas/issues/` tem um comentário de entrega com **as provas
que foram executadas** — não adjetivos. Se precisar entender por que algo é como é, o comentário
do ticket é o primeiro lugar a olhar.

### Verifique que está tudo de pé antes de começar

```bash
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m second_brain --help
git log --oneline -10
```

538 passam, 7 desselecionados. **Se a suíte não estiver verde, pare e descubra por quê** — não
construa em cima.

---

## 2. O que ler, nesta ordem

1. `CONTEXT.md` — o glossário. **Daily** e **Diário** são termos distintos aqui, com significados
   fixos. Não os troque.
2. `.scratch/fontes-passivas/spec.md` — a spec da entrega, com 23 user stories.
3. `.scratch/fontes-passivas/contrato-fonte-passiva.md` — o contrato entre camadas. A **seção 9**
   é o adendo da daily e é a parte mais nova.
4. `.scratch/fontes-passivas/issues/06-acabamento-e-uso-real.md` — o seu ticket.
5. `AGENTS.md` e `docs/agents/` — como issues, labels e docs de domínio funcionam neste repo.
6. `.scratch/fontes-passivas/handoff.md` — o handoff que abriu esta entrega. As convenções da
   casa e as armadilhas de Windows estão lá e **continuam valendo**.

---

## 3. As decisões do usuário, e o porquê de cada uma

Herde, não reabra. O que está aqui foi decidido por ele nesta sessão, e a razão importa mais
que a regra.

- **Costura única por entrega.** `gerar_diario(data)` e `gerar_daily(agora)`. Todo teste de
  comportamento passa por uma delas. O que é externo entra por porta injetada.
- **Uma porta só para as fontes** (`PortaFonte.coletar(janela)`), com três implementações. Foi
  o que permitiu construir git, Linear e Slack em paralelo, e é o que faria o navegador entrar
  um dia sem tocar a costura.
- **O filtro de exclusão age na coleta, num ponto só** — dentro da costura, sobre o que toda
  fonte devolveu. Espalhá-lo pelos coletores faria a régua depender de nenhum deles esquecer.
- **Janela do diário: corte às 04:00.** O commit da uma da manhã cai no dia anterior, que é o
  dia que o usuário viveu.
- **Janela da daily: da última daily até agora.** Recorte diferente do dia civil e **não
  derivável dele** — numa segunda-feira cobre o fim de semana inteiro. A âncora é o campo `ate`
  do frontmatter da nota anterior; o vault é a fonte da verdade, sem arquivo de estado escondido.
- **Regenera e sobrescreve.** As duas notas são derivadas; rodar de novo atualiza.
- **Degradação graciosa.** Fonte que falha vira marca visível na nota, não interrupção. Só
  quando **todas** falham nada é escrito — um diário ausente por falha não pode ser confundido
  com um dia tranquilo. Dia vazio não vira nota.
- **Falha do resumo não custa a nota.** Diferente do pipeline de reunião (onde a transcrição já
  guarda o conteúdo), aqui as listas cruas não existem em nenhum outro lugar.
- **Nada é agendado.** Nem o diário, nem a daily. O usuário roda `second-brain daily` na hora,
  um minuto antes de falar. A limpeza do áudio bruto continua agendada — ela é do tracer bullet.
- **O usuário não vai ler o diário.** Ele disse isso com todas as letras. Por isso a **daily
  carrega também as listas cruas** e virou o registro durável do vault — uma chamada ao Claude
  por dia serve para as duas coisas. `second-brain diario` continua existindo para um retrato de
  dia civil sob demanda, mas não é o caminho principal.
- **`notas/daily.md` é do usuário.** O agente lê os itens **desmarcados** e nunca marca nada;
  quem marca é ele, no Obsidian, depois de falar. A única escrita permitida é `--anotar`, que é
  o "pedido explícito" que o glossário prevê. O arquivo é **append-only**.
- **`preciso_de` só tem o que espera outra pessoa.** Review parado, PR sem merge. Nota para si
  mesmo continua em `Pendências` do diário e não entra na daily.

---

## 4. O mapa do código novo

`src/second_brain/`, além do que o tracer bullet já tinha:

| módulo | papel |
|---|---|
| `fontes.py` | `Janela`, `Evento`, `PortaFonte`, `ErroDeFonte`, `janela_do_dia`, `filtrar` — a base que todos compartilham |
| `coleta.py` | a leitura de fontes fatorada, usada pelas duas costuras |
| `diario.py` | **costura**: `gerar_diario(data)` → nota em `diario/` |
| `daily.py` | **costura**: `gerar_daily(agora)` → nota em `daily/`, com a janela da última fala |
| `fonte_git.py` | varredura de repositórios e `git log` por autor |
| `fonte_linear.py` | GraphQL do Linear, read-only |
| `fonte_slack.py` | Web API do Slack, com a blocklist antes da leitura |
| `resumo_dia_claude.py` | o Claude da conta do usuário: resumo do dia **e** roteiro da daily |
| `vault.py` | ganhou a zona `daily/`, `montar_daily`, os pontos do usuário e as zonas por coletor |
| `portas.py` | ganhou `ResumoDoDia`, `Daily` e suas portas |

**Reaproveite sem dó:** `coleta.py` (não duplique leitura de fontes), `registro.py` (o log em
arquivo que a camada 06 precisa) e `automacao.py` (mas **não** para agendar a daily).

### A zona de propriedade é por coletor

`vault.escrever` recebe as zonas permitidas. O pipeline de reunião escreve em `reunioes/` e
`transcricoes/`; o diário só em `diario/`; a daily só em `daily/`. `notas/` é recusada para
todos, exceto pelo `--anotar`. Isso não é detalhe: a primeira versão abria a zona globalmente e
quebraria a invariante do coletor de reunião.

---

## 5. Estado da máquina do usuário

- `config.toml` em `%APPDATA%\second-brain\` com **Deepgram, Linear e git preenchidos e
  funcionando**. Slack vazio (falta a app interna aprovada pelo admin).
- `[git].raiz = C:/Users/gabri/development`, profundidade 3, excluindo `node_modules`,
  `vendor`, `.venv`.
- `[diario].inicio_do_dia = "04:00"`. `[privacidade].excluir` **vazio** — o filtro nunca foi
  exercitado com um padrão real.
- Vault em `C:\Users\gabri\second-brain-vault`, com `reunioes/`, `transcricoes/`, `diario/`,
  `daily/`, `notas/`.
- **Um diário real já foi gerado**: `diario/2026-09-03.md`, 377 linhas, 204 eventos (28 commits
  em 25 repositórios + 176 do Linear), duas reuniões linkadas, 47 segundos, **US$ 0,2852** da
  assinatura. O usuário leu e aprovou o conteúdo.
- **Nenhuma daily real foi gerada ainda.**

---

## 6. O que foi provado, e o que não foi

Seja honesto sobre a diferença — a camada 06 existe em boa parte para fechar a segunda coluna.

**Provado com dado real:** o coletor de git contra a raiz real (23–28 commits do dia, ~6s); o
Linear contra a API real com a chave do usuário (172 eventos num dia, 27 no anterior); o diário
inteiro de ponta a ponta com Claude real; a zona de propriedade sondada nos dois sentidos; o
frontmatter validado como YAML por um parser externo.

**Provado só com fixture ou fake:** todo o Slack (o usuário não tem token — as fixtures vieram
dos exemplos da documentação, não de um workspace); a daily inteira (nunca rodou com Claude
real); o filtro de exclusão (nunca rodou com um padrão de verdade).

**Não provado de forma nenhuma:**
- **O texto que o Claude produz para as batidas da daily.** O executor da camada 07 morreu
  (stall do watchdog) justamente enquanto acrescentava o teste de rede do prompt, então ele
  **não existe**. Só a tradução da resposta foi provada, com payloads de fixture.
- Os scopes do Slack serem aceitos, o permalink abrir a mensagem certa, o rate limit real.
- O comportamento em um dia com **muito** Slack (o limite de 400 mil caracteres do adaptador).

---

## 7. Armadilhas já pagas — não redescubra

Além das do handoff anterior (que continuam valendo: barra invertida no TOML, cp1252 no console,
limites da bandeja, `pythonw.exe` sem console):

- **`git log --since` esconde commit do dia.** O flag para a caminhada no primeiro commit mais
  velho que a data: um tip com data de commit velha (rebase, relógio fora de hora, histórico
  importado) apaga em silêncio os commits do dia. Reproduzido nesta sessão — `--since --until`
  devolveu **nada** onde havia dois commits. Por isso `fonte_git` caminha o histórico e recorta
  em Python. **Não "otimize" isso de volta**; há dois testes de regressão guardando.
- **O header do Linear não leva `Bearer`.** Personal API Key vai crua em `Authorization`.
- **O fim da janela é exclusivo.** Um evento exatamente na virada apareceria em dois diários se
  fosse inclusivo. Há teste.
- **Um dia real do Linear traz ~170 eventos**, contra ~28 commits. A movimentação do time é
  contexto, não o trabalho do usuário — o prompt da daily depende dessa distinção.
- **Testes de rede custam dinheiro**: o do Claude gasta a assinatura do usuário, o da Deepgram
  gasta crédito. Rode de propósito, nunca por hábito.

---

## 8. O padrão de trabalho desta casa

Foi ele que pegou todos os achados desta entrega, e vale para você:

1. O **orquestrador** escreve a spec, quebra em camadas e **fixa os contratos entre elas por
   escrito antes** de abrir qualquer uma.
2. Cada camada é entregue por um **executor** e depois **revisada pelo orquestrador, que executa
   as provas ele mesmo** em vez de aceitar o relato. Nesta sessão isso pegou: um furo de
   cobertura na janela (mutação passava nos 290 testes), um relatório da camada 03 que afirmava
   faltar um teste que existia, e o bug do `git log --since`.
3. Achado fora do escopo vai para `.scratch/fontes-passivas/DEFERRED.md` — **33 itens hoje**,
   vale ler antes de começar.
4. Camada fechada recebe comentário de entrega no ticket, **com as provas executadas**.

**Comentários no código só quando explicam o PORQUÊ não óbvio.** Nunca o quê.

---

## 9. Trabalho deferido que vale reconsiderar

`.scratch/fontes-passivas/DEFERRED.md` tem a lista completa. Os que mais interessam à camada 06:

- **Nada distingue "fonte não trouxe nada" de "o filtro removeu tudo"** — ambos aparecem como
  `_(nada registrado)_`. É decisão de privacidade do usuário, não de código.
- **`--simular` mostra só quantos eventos o filtro removeu, não quais** — imprimir o que o
  filtro prometeu esconder é decisão de privacidade.
- **`--simular` da daily imprime só o `titulo`**, que no Slack é o remetente: quem quer conferir
  o filtro não vê o texto que iria ao Claude.
- **Nada re-tenta falhas transitórias** de nenhuma das quatro APIs.
- **Toda DM já aberta custa uma requisição ao Slack**, mesmo as mudas.

---

## 10. Depois da camada 06

A entrega de fontes passivas fecha aí. O que o mapa (`.scratch/second-brain/map.md`) tem em
seguida: **recuperação de contexto** — o agente com `cwd` no vault, busca agêntica pura, chat no
terminal mais comando one-shot. É essa entrega que vai ler as listas cruas das dailies; é por
isso que elas existem.

Antes dela, dois passos humanos pendentes: **criar a app interna do Slack** e obter aprovação do
admin (`docs/smoke-slack.md` tem o texto pronto para o pedido), e **exercitar o filtro de
exclusão** com um padrão real.
