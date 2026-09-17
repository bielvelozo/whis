# 13 — Camada 6: a palheta depois da prova do usuário

Type: task
Status: resolved
Blocked by: 10, 11

**What to build:** o que a prova na máquina do usuário (2026-09-16) reprovou na palheta, nas
palavras dele, em oito pontos. É a mesma lição da entrega inteira: a interface certa é a que cabe
no dia dele, não a que cabe na arquitetura.

As decisões abaixo vêm do chat da orquestração e **substituem** o que a spec dizia onde conflitam
(registrado no topo da spec e no `ORCHESTRATION.md`).

- [x] **1. Sem explicação na nota.** `MODELO_DA_NOTA_VIVA` perde o callout inteiro: frontmatter
      e os títulos das seções, nada mais. Ele sabe o que cada seção é.
- [x] **2. Nenhuma janela de terminal, nunca.** Todo processo filho nasce sem console:
      `subprocess.CREATE_NO_WINDOW` + `STARTUPINFO` com `SW_HIDE` em `automacao._rodar`,
      `avisos`, `obsidian.lancar` (o `cmd /c start`), e — porque a bandeja e as tarefas rodam sob
      `pythonw.exe` — um interruptor global (`whis.sem_console.instalar()`), chamado por
      `__main__.main()` quando não há console (`sys.stdout is None`), que faz `subprocess.Popen`
      nascer com essas flags por padrão. É o que cobre o `git` da fonte, o PowerShell do toast e o
      CLI do Claude aberto pelo `claude-agent-sdk` (`anyio.open_process` cai no mesmo `Popen`).
      Teste: com o interruptor ligado, um `Popen` espião recebe as flags; sem console de verdade
      não dá para provar na suíte — a sessão principal sonda sob `pythonw`.
- [x] **3. `anotar` vai para uma seção nova, `## Pontos`**, entre *Dúvidas* e *Falar*; *Dúvidas*
      só recebe quando ele pede. A nota viva passa a ter cinco seções: *O que eu fiz*, *O que
      estou fazendo*, *Dúvidas*, *Pontos*, *Falar*. As três últimas são dele; o agente só escreve
      em *Pontos* (`note`) e *Dúvidas* (`doubt`) a pedido, append-only, byte a byte no resto.
      Nota antiga sem `## Pontos`: a seção nasce **antes de `## Falar`** (não no fim).
      `whis daily --anotar` e o `anotar` da DM vão para *Pontos*. `CONTEXT.md` acompanha (a
      sessão principal escreve).
- [x] **4. Sem `ajuda`.** Enter com o campo vazio só esconde a janela.
- [x] **5. Comandos em inglês, e a palavra do comando fica em cor de destaque ao digitar.**
      `daily`, `note <texto>`, `doubt <texto>`, `ask <pergunta>`, `open`, `record`, `settings`.
      O campo vira um `Text` de uma linha com uma tag na primeira palavra quando ela casa com um
      comando (cor de destaque); palavra desconhecida sem cor. Enter despacha (`return "break"`).
- [x] **6. Ações na janela.** Abaixo do campo, uma lista de linhas clicáveis no estilo Raycast, uma
      por comando (ícone em texto, nome, descrição curta em inglês), filtrada pelo que ele digita;
      clicar executa. As três que ele pediu vêm primeiro e existem mesmo com o campo vazio:
      **Open note** (`open`), **Generate daily** (`daily`), **Start recording** / **Stop recording**
      (`record`, alterna o coletor da bandeja — a palheta recebe `gravar()` e `gravando()` da
      bandeja por injeção; o texto da linha segue o estado). Depois: `ask`, `note`, `doubt`,
      `settings`.
- [x] **7. `ask` falhou na máquina dele.** Diagnóstico pelo `bandeja.log` real (trecho no comentário
      abaixo, se a sessão principal conseguir extraí-lo) e conserto. Hipótese principal: sob
      `pythonw.exe` não há console, e o CLI do Claude aberto pelo SDK ou herda `stdin`/`stdout`
      nulos ou abre um console próprio e morre. Prove com `whis bandeja` real sob `pythonw`
      contra um vault temporário e `ask` de verdade (custa uma pergunta), com a resposta no log.
- [x] **8. Estilo Raycast.** Painel escuro (`#1c1c1e`), cantos arredondados (canvas com
      `-transparentcolor` no `overrideredirect`), borda fina em cor de destaque (`#7c6cf2`),
      campo grande (Segoe UI 18) com placeholder ("Type a command…"), lista de ações com a linha
      selecionada destacada, setas ↑/↓ para escolher e Enter para executar a selecionada quando o
      campo está vazio, largura ~680, altura conforme as linhas. Sem Windows 95.
- [x] `docs/smoke-interface.md` passo 5 e a tabela de comandos atualizados; suíte inteira verde.

## Notas para o executor

- A sonda do executor anterior (`keybd_event` de outro processo) continua sendo o jeito de provar a
  janela sob `pythonw`; a sessão principal repete a prova antes do commit.
- Os nomes das seções continuam em português (é a nota dele); só os comandos mudam de idioma.
- Não invente comando novo além dos sete; os seis futuros continuam fora.

## Comments

**Camada 6 entregue e fechada** (2026-09-16; executor `palheta`, revisão e gate na sessão principal).

- Os oito pontos: modelo sem callout; `sem_console.py` (`CREATE_NO_WINDOW` + `SW_HIDE` em todo
  processo filho, com interruptor global sob `pythonw` que cobre o `git`, o PowerShell e o CLI do
  Claude via `anyio`); cinco seções com *Pontos* (`note`) e *Dúvidas* (`doubt`) a pedido, seção que
  falta nasce na ordem; sem `ajuda`; comandos `daily note doubt ask open record settings`, campo
  `Text` com a primeira palavra destacada; lista de ações clicáveis com *Open note*, *Generate daily*,
  *Start/Stop recording* primeiro e `record` alternando o coletor; visual Raycast (painel escuro
  arredondado por `-transparentcolor`, borda roxa, placeholder, ↑/↓, Enter na selecionada).
- **`ask` tinha duas causas de código e uma de credencial.** (a) Sob `pythonw` o stderr herdado
  pelo CLI do Claude é um pipe morto e o processo sai com 1 — os três adaptadores passam
  `stderr=` ao SDK agora; (b) cada processo filho abria console (item 2); (c) **a credencial do
  `claude` nesta máquina está vencida** (`OAuth session expired`, `~/.claude/.credentials.json`
  com tokens vazios) — o usuário precisa rodar `claude login`. Com (a) e (b) consertados, o caminho
  inteiro sob `pythonw` foi provado até o CLI responder o erro de credencial e o toast sair.
- **Gate na sessão principal:** suíte **1063 verdes** (eram 1048); captura de tela da janela nova sob
  `pythonw` com o hotkey privado `ctrl+alt+shift+f9` (vazia e filtrando "no" com destaque roxo);
  log com `Atalho global ... registrado.`; 0 janelas de console contadas pelo executor durante
  `daily --fakes`, `note`, `open`, toast e `ask`.
- **Incidente:** as teclas simuladas do executor caíram na bandeja real do usuário (código antigo,
  `ctrl+alt+w`) às 23:15–23:16 e rodaram `daily` de verdade contra a configuração dele (além de
  `open`); `note`/`vagas` viraram "Não entendi". Registrado para ele conferir
  `daily/2026-09-16.md` e `daily/atual.md`. O executor trocou para um hotkey privado ao perceber.
- Testes existentes editados (decisão revertida pelo usuário): em `test_nota_viva.py` (modelo com
  cinco seções sem explicação; `anotar` em *Pontos*), `test_daily.py` (lista de seções),
  `test_comando_daily.py` (`--anotar` → *Pontos*), `test_atendente.py` (`anotar` → *Pontos*),
  `test_palheta.py` (comandos em inglês, sem `ajuda`).
