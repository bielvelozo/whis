# Handoff: fontes passivas + diário

Documento de abertura da próxima entrega do Second Brain. Escrito em 2026-09-03,
no fim da sessão que fechou o tracer bullet. Assume **zero contexto**: leia isto
inteiro antes de tocar em qualquer coisa.

Seu trabalho na próxima sessão, nesta ordem: **planejar** (spec + camadas) e
depois **executar**. A parte de planejamento ainda não existe — este handoff é
matéria-prima para ela, não substituto dela.

---

## 1. O que é o projeto

Um agente pessoal local no Windows 11 que observa o trabalho do usuário e mantém
um **vault Obsidian** como memória durável. Nada em servidor: 100% na máquina
dele (ADR `docs/adr/0001-projeto-separado-100-local.md`).

A primeira fatia — **o tracer bullet** — está pronta e em uso real: um ícone na
bandeja grava a reunião, e ao parar o áudio vira nota + transcrição no vault,
transcrito pela Deepgram e resumido pelo Claude.

Leia, nesta ordem, antes de planejar:

1. `CONTEXT.md` — o glossário. **Use estes termos**; eles têm significado fixo
   aqui (Coletor, Fonte passiva, Vault, Sob demanda, Diário, Zona de
   propriedade, Tracer bullet).
2. `AGENTS.md` e `docs/agents/` — como issues, labels e docs de domínio funcionam
   neste repo.
3. `.scratch/second-brain/map.md` — o mapa do wayfinding: **todas** as decisões
   arquiteturais fechadas, uma linha por ticket, com link.
4. `.scratch/tracer-bullet/spec.md` — como uma spec deste repo se parece. A da
   próxima entrega deve ter a mesma forma.
5. `.scratch/tracer-bullet/contrato-pasta-gravacao.md` — exemplo de contrato
   entre camadas, fixado pelo orquestrador antes de abrir camadas em paralelo.

---

## 2. Como este repositório trabalha

Convenções que valem para o código novo. Elas não são preferência estética: cada
uma foi paga com retrabalho evitado.

**Idioma.** Tudo em português: nomes de módulos, funções, variáveis, docstrings,
mensagens de log, texto de nota, mensagens de commit (sem acento nos commits, por
compatibilidade de terminal). Termos técnicos consagrados ficam em inglês.

**Testes: uma costura única, fakes nas portas, zero mock de detalhe interno.** No
tracer bullet a costura é `pipeline.processar(pasta) → arquivos no vault`, e todo
teste exercita comportamento externo por ela. O que é externo (STT, resumo) entra
por **porta injetada** (`src/second_brain/portas.py`), com fakes em
`src/second_brain/fakes.py`. A próxima entrega precisa da sua própria costura
única — decidi-la é parte do planejamento, e o usuário deve confirmá-la.

**O que fica fora da costura vira smoke manual documentado.** Captura WASAPI e
ícone de bandeja não são testáveis automaticamente; viraram roteiros em
`docs/smoke-gravacao.md` e `docs/smoke-ponta-a-ponta.md`, com passos e critérios
de sucesso. Faça o mesmo para o que depender de token de terceiro.

**Comentários só quando explicam o PORQUÊ não óbvio.** Nunca comente o quê — o
nome já diz. Comentário bom aqui: uma restrição de plataforma, um invariante
sutil, o motivo de uma alternativa ter sido descartada.

**Segredos nunca no repo.** Tudo em `%APPDATA%\second-brain\config.toml`, que
está no `.gitignore`. Chave nova = chave nova no TOML, nunca variável de ambiente
obrigatória.

**Portabilidade.** A máquina de destino é o **PC desktop** do usuário; o
desenvolvimento acontece no notebook. Nada de índice de dispositivo, caminho
absoluto ou nome de máquina no código.

**Marcador `rede`.** Testes que falam com serviço real são `@pytest.mark.rede` e
não rodam por padrão (`addopts = -q -m "not rede"`). Rode-os de propósito com
`pytest -m rede`.

### O padrão orquestrador/executor

Esta entrega e a anterior foram construídas assim, e funcionou:

1. O **orquestrador** (você, na próxima sessão) escreve a spec, quebra em
   **camadas** numeradas (`.scratch/<feature>/issues/NN-<slug>.md`), e fixa por
   escrito os **contratos entre camadas** antes de abrir qualquer uma — foi o
   contrato da pasta de gravação que permitiu construir 01 e 02 em paralelo sem
   retrabalho.
2. Cada camada é entregue por um **executor** e depois **revisada pelo
   orquestrador, que executa as provas ele mesmo** em vez de aceitar o relato. Foi
   assim que apareceram: um furo de zona de propriedade na camada 01
   (`reunioes/../notas/` escapava), um relatório mentiroso na 06, e o balão de
   erro sumindo na 05.
3. Achado fora do escopo do ticket vai para `.scratch/<feature>/DEFERRED.md` —
   uma linha: o quê, onde, por que ficou de fora, de qual camada veio.
4. Camada fechada recebe um comentário de entrega no ticket, com **as provas que
   foram executadas**, não com adjetivos.

---

## 3. O que já existe (mapa do código)

`src/second_brain/`, 4.800 linhas, 230 testes verdes:

| módulo | papel |
|---|---|
| `pipeline.py` | **a costura única**: pasta de gravação → nota + transcrição no vault |
| `portas.py` | `PortaSTT` e `PortaResumo` (protocolos) + `Transcricao`, `Resumo`, `Fala` |
| `fakes.py` | as duas portas fake, usadas por quase todo teste |
| `vault.py` | escrita no vault e a **zona de propriedade** (nunca escreve em `notas/`) |
| `gravacao.py` | contrato da pasta de gravação: `gravacao.json`, `estado.json`, `transcricao.json` |
| `gravador.py` | captura WASAPI (mic + loopback em arquivos separados) e a CLI de dispositivos |
| `stt_deepgram.py` | adapter Deepgram Nova-3 `language=multi`, batch, um POST por canal |
| `resumo_claude.py` | adapter Claude via Agent SDK com OAuth da conta do usuário |
| `retencao.py` | avaliar/limpar o áudio bruto vencido; `retidas()` para o reprocesso |
| `coletor.py` | máquina de estados do gesto (gravar → processar), sem UI |
| `bandeja.py` | o ícone pystray — casca fina sobre o coletor |
| `instancia.py` | trava de instância única (bloqueio de faixa do Windows) |
| `janelas.py` | deduz o título da reunião da janela do Meet/Zoom/Teams |
| `automacao.py` | atalho de logon e tarefa agendada da limpeza |
| `registro.py` | log em arquivo, para o que roda sem console |
| `configuracao.py` | o `config.toml` e sua validação |
| `__main__.py` | CLI: `init`, `bandeja`, `windows`, `processar`, `reprocessar`, `limpar` |

**Reaproveite sem dó:** `configuracao.py` (acrescente chaves, não renomeie as
existentes), `vault.py` (a escrita no diário deve passar por ele, para a zona de
propriedade continuar valendo), `registro.py`, `automacao.py` (a tarefa agendada
do diário é o mesmo mecanismo da limpeza) e o padrão porta+fake de `portas.py`.

---

## 4. Estado da máquina do usuário (não refaça este setup)

- `config.toml` existe em `%APPDATA%\second-brain\` com a **chave da Deepgram já
  preenchida** e funcionando.
- Vault em `C:\Users\gabri\second-brain-vault` (`reunioes/`, `transcricoes/`,
  `diario/` — vazia —, `notas/`).
- Gravações em `C:\Users\gabri\second-brain-gravacoes`, retidas 7 dias.
- Bandeja instalada na Inicialização do Windows e limpeza diária agendada às
  12:00 (`second-brain windows --limpeza`).
- Log em `%APPDATA%\second-brain\bandeja.log`.
- O Claude responde pela **assinatura Pro/Max** do usuário via OAuth — o adapter
  recusa explicitamente cair para `ANTHROPIC_API_KEY`.

---

## 5. A próxima entrega

**Objetivo:** o vault deixa de depender de reunião. Todo fim de dia nasce
`diario/YYYY-MM-DD.md` resumindo o trabalho, lido retroativamente das fontes
passivas.

### Decisões já tomadas — herde, não reabra

De `.scratch/second-brain/issues/13-decidir-fontes-passivas.md` (fechado pelo
usuário em 2026-08-14):

- **Fontes da v1: git + Linear + Slack**, nesta ordem de construção. Slack por
  último, porque depende de aprovação de admin no workspace — e o diário precisa
  **degradar graciosamente** sem ele.
- **Navegador fica fora da v1.** Reentra só se os diários se provarem rasos.
- **Git:** varredura automática de uma pasta raiz de desenvolvimento atrás de
  repositórios, com lista de exclusão.
- **Linear:** tudo do(s) time(s) do usuário — issues, comentários, projetos,
  atividade —, não só a atividade própria. API GraphQL com Personal API Key
  read-only.
- **Slack:** tudo que o usuário participa, **inclusive DMs**, com **blocklist** de
  canais/conversas. App interna com user token (`xoxp`).
- **Cadência: diário agendado.** Tarefa agendada do Windows no fim do dia. Leitura
  retroativa, nenhum processo residente — o princípio de "nada fica escutando"
  vale para esta entrega também.
- **Privacidade:** régua única. O conteúdo vai ao Claude para resumo, com
  **filtro de exclusão configurável** (padrões/canais/pessoas que nunca saem da
  máquina). A blocklist do Slack é a primeira camada desse filtro.

Os fatos operacionais de cada API (endpoints, limites, formato de token, como o
Slack trata apps internas) estão em
`.scratch/second-brain/research/12-fontes-passivas.md`. **Confira as datas** — a
pesquisa é de agosto de 2026.

### O que ainda não foi decidido, e você precisa fechar com o usuário

1. **A costura única desta entrega.** Provável: `gerar_diario(data) → nota em
   diario/`, com as fontes atrás de portas injetáveis e fakes. Confirme com o
   usuário antes de escrever teste.
2. **Formato do diário** — frontmatter, seções, o que é resumo e o que é lista
   crua, e se ele linka reuniões do mesmo dia (provavelmente sim: é o que
   conecta as duas fontes de contexto).
3. **Onde o filtro de exclusão age** — antes de ir ao Claude é obrigatório; antes
   de gravar no vault é decisão a tomar.
4. **Idempotência e re-execução**: rodar o diário duas vezes no mesmo dia
   sobrescreve? E se o dia já tiver reuniões processadas depois?
5. **Janela de leitura** — "o dia" começa e termina quando? Trabalho depois da
   meia-noite cai em qual diário?
6. **Como as três fontes falham individualmente.** O diário sem Slack tem que
   nascer mesmo assim; provavelmente sem Linear e sem git também.

### Sugestão de camadas (valide, não obedeça)

1. Esqueleto do diário com fontes fake + a costura de teste + escrita no vault
2. Coletor de git (varredura de repos, `git log` por autor e período)
3. Coletor do Linear (GraphQL, chave read-only)
4. Resumo do dia pelo Claude + formato final da nota
5. Coletor do Slack (app interna, blocklist)
6. Agendamento diário + degradação graciosa quando uma fonte falha

Camadas 2 e 3 são paralelizáveis depois da 1 — se abri-las juntas, **fixe antes
o contrato do que cada coletor devolve**, como foi feito com a pasta de gravação.

---

## 6. Armadilhas já pagas nesta sessão

Coisas que custaram tempo e que você não precisa redescobrir:

- **Caminho do Windows no TOML.** Barra invertida quebra o parse com "Invalid hex
  value". Já existe mensagem didática em `configuracao.py`; mantenha o padrão de
  barra normal em qualquer exemplo novo.
- **Texto no console do Windows.** Fora de um console interativo o Python escolhe
  cp1252 e qualquer acento derruba o comando. `forcar_utf8_na_saida()` em
  `__main__.py` trata isso — comando novo deve passar por lá.
- **Limites de UI do Windows.** O tooltip da bandeja cabe 128 caracteres, o balão
  256, o título do balão 64 — estourar levanta `ValueError` e some com a
  mensagem. Ver `bandeja.encurtar()`.
- **`pythonw.exe` não tem console.** Tudo que roda por atalho ou tarefa agendada
  precisa escrever em arquivo de log (`registro.acrescentar_arquivo`), senão o
  diagnóstico se perde.
- **O `pythonw.exe` do venv é um redirecionador**: no Gerenciador de Tarefas
  aparecem dois processos (o stub e o Python base). Não é bandeja duplicada.
- **`keyterm` da Deepgram** recupera termos em inglês que ela omite com
  `language=multi` — e funciona junto com `multi`, o que a documentação não
  deixa claro. Está no `DEFERRED.md` com a tabela de evidência. Em fala humana
  real não foi necessário, mas continua valendo como reforço.
- **Idiomas espúrios**: a Deepgram reportou `ru`, `es`, `hi` numa reunião em
  português. Não atrapalhou; não persiga.
- **Testes de rede** custam dinheiro e cota. O do Claude gasta a assinatura do
  usuário; o da Deepgram gasta crédito. Rode-os de propósito, nunca por hábito.

---

## 7. Trabalho deferido que vale reconsiderar

`.scratch/tracer-bullet/DEFERRED.md` tem a lista completa, com o que já foi
fechado marcado. Os que podem interessar à próxima entrega:

- **Nada re-tenta falhas transitórias** de Deepgram nem de Claude (429, 5xx,
  timeout). Três coletores novos falando com três APIs tornam isso mais provável
  — um retry com backoff compartilhado pode caber nesta entrega.
- **Custo e uso do Claude são descartados** (`ResultMessage.total_cost_usd`).
  Com o diário rodando todo dia, saber quanto consome da assinatura passa a
  importar.
- **Limpeza que falha no meio** deixa a pasta sem `estado.json` e o reprocesso
  paga um STT novo. Raro, mas real.
- **Resumo de transcrição muito longa não é fatiado** (acima de 400 000
  caracteres o adapter recusa). O diário pode bater nesse limite se um dia tiver
  muito Slack.

---

## 8. Verificar que está tudo de pé

```bash
.venv/Scripts/python.exe -m pytest          # 230 passam, 3 desselecionados
.venv/Scripts/python.exe -m second_brain --help
git log --oneline -12
```

Se a suíte não estiver verde antes de você começar, **pare e descubra por quê** —
não construa em cima.

---

## 9. Entregue no dia 2026-09-03 (contexto recente)

Sessão que fechou as seis camadas do tracer bullet. Commits `35a8e65` a
`6c639ff`. O que aconteceu de relevante para você:

- A camada 06 (retenção e reprocesso) foi fechada e commitada.
- A camada 05 (bandeja) foi construída inteira, com o coletor separado da UI.
- Uma **reunião real de 40 minutos** foi gravada e virou nota: 623 falas, 76
  segundos de processamento, o Claude inferiu os participantes pelo conteúdo. O
  usuário confirmou que o resumo é fiel.
- O acabamento entrou depois: instância única, atalho de logon, título automático
  da reunião e limpeza agendada.
- Dois bugs de uso real foram corrigidos: o balão de erro sumindo por causa do
  limite de tooltip, e o download do áudio de exemplo no teste de rede da
  Deepgram (redirect não seguido).

**Estado atual: nenhum critério de aceite em aberto no tracer bullet.**
