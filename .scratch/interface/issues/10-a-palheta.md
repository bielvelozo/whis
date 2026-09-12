# 10 — Camada 3: a palheta

Type: task
Status: resolved
Blocked by: 09

**What to build:** uma janela aberta por atalho global — um campo de texto, o comando, e a janela
some. O comando roda em segundo plano, o resultado vira nota no vault, um toast avisa.

Spec: [../spec.md](../spec.md), *A palheta*. Fatos:
[research/05](../research/05-janela-local-e-launcher.md).

- [x] `palheta.py`: registro de comandos (nome, ajuda, função), análise do texto digitado,
      despacho em thread de trabalho, contrato de resultado (nota escrita + aviso). Costura pura,
      testável sem janela.
- [x] Comandos desta entrega: `daily` (gera agora), `anotar <texto>` (Falar), `perguntar <texto>`
      (resposta vira nota em `respostas/`, zona nova do agente), `abrir` (a `daily/atual.md` por
      URI `obsidian://`), `configurar` (abre o painel — camada 4). Nenhum dos seis comandos
      futuros.
- [x] Janela Tk: sem borda, centrada, por cima, some ao despachar ou no Esc; entra por porta
      injetada (o teste monta a palheta sem Tk).
- [x] Atalho global por `win32gui.RegisterHotKey` com `MOD_NOREPEAT`, em thread próprio com
      janela oculta e loop de mensagens próprio (o `_mainloop` do pystray consome as mensagens
      do thread dele). Combinação padrão configurável em `[palheta].atalho`.
- [x] Bandeja: Tk no thread principal, `pystray` por `run_detached`; item de menu
      *Abrir a palheta*; o gesto de gravar continua exatamente igual.
- [x] Personalidade do Whis (sereno, econômico) nas respostas de `perguntar`; a fonte só aparece
      se pedida — o fio de 24h já sustenta.
- [x] Suíte inteira verde.

## Notas para o executor

- Sondas feitas na sessão principal antes desta camada, com resultado no comentário abaixo:
  `RegisterHotKey` sob `pythonw.exe` recebendo `WM_HOTKEY`, e `pystray.run_detached` convivendo
  com `mainloop` do Tk. Se alguma falhou, a forma desta camada muda — leia antes.
- Chamada de outro thread para o Tk só por `after()`; ação de 60 s nunca no handler.
- O comando longo custa dinheiro (pergunta ≈ US$ 0,56, daily ≈ US$ 0,70): sem retry automático.

## Comments

**Sondas feitas na sessão principal, 2026-09-12** (passo 5 do pipeline), nesta máquina, num só
processo sob `pythonw.exe` (sem console), com a tecla simulada por `keybd_event` de outro
processo. Script guardado em [../research/sonda-palheta.py](../research/sonda-palheta.py). Log:

```
  0.00s  processo .venv\Scripts\pythonw.exe
  1.42s  Tk criado no thread principal
  1.72s  pystray.run_detached chamado
  1.72s  hotkey registrado (Ctrl+Alt+Shift+F9) no thread do hotkey
  1.94s  WM_HOTKEY recebido no thread do hotkey
  1.97s  Tk mostrou a janela em resposta ao hotkey
 10.72s  encerrando: janela mostrada=True, icone visivel=True
 10.72s  hotkey desregistrado
 11.03s  mainloop terminou; thread do hotkey vivo=False
saída do pythonw: 0
```

O arranjo da spec **funciona como desenhado**: Tk no thread principal; `pystray` por
`run_detached`; `RegisterHotKey(None, ...)` num thread próprio com `GetMessage` próprio (o
`WM_HOTKEY` chega nesse thread, não no do pystray); a ponte para o Tk é uma `queue.Queue` sondada
por `after(50)`; o encerramento é `PostThreadMessage(WM_QUIT)` no thread do hotkey + `icone.stop()`
+ `destroy()`. Nada disso exigiu console nem elevação. A camada 3 pode seguir a forma prevista.

## Comments

**Camada 3 entregue e fechada** (2026-09-12; executor `palheta`, revisão e gate na sessão principal).

- `palheta.py` (costura pura: `Comando`, `interpretar`, `Resultado`, `Palheta.despachar` com `Lock` não
  bloqueante — despacho recusado com toast enquanto outro roda; exceção vira toast "O comando falhou"),
  `janela_da_palheta.py` (Tk sem borda, `-topmost`, Enter/Esc/perda de foco somem; porta `pedir(f)` por
  fila sondada), `atalho_global.py` (`analisar_atalho` + thread próprio com `GetMessage`, portas do
  Windows injetáveis), bandeja hospedando Tk + `run_detached` + hotkey, com os itens *Abrir a palheta*
  e *Configurar*. Comandos: `daily`, `anotar`, `perguntar` (nota em `respostas/`, zona nova, callout
  recolhido `> [!info]- Fontes`, fio `palheta`), `abrir`, `configurar`, `ajuda`.
- `PROMPT_DA_BUSCA` com a voz do Whis, teto de três frases/400 caracteres e sem bloco de fontes no
  texto (as citações seguem em `citacoes`). Nenhum teste existente editado.
- **Decisão da sessão principal:** o padrão do atalho passou de `ctrl+alt+space` (tomado nesta máquina,
  erro 1409) para **`ctrl+alt+w`** (sondado livre). `[palheta].atalho` no modelo.
- **Prova real na sessão principal**, `pythonw -m whis bandeja --fakes` contra config e vault
  temporários: `Atalho global ctrl+alt+w registrado.`; tecla simulada por `keybd_event` de outro
  processo abriu a janela; `anotar sonda da palheta` digitado de fora chegou à palheta, escreveu
  `- sonda da palheta` em *Falar* e o log registrou `Toast mostrado: Anotado em Falar`. O executor
  provou também `perguntar` (nota em `respostas/2026-09-12-0406-...md`), `daily` e `configurar`.
- Suíte ao fim da camada: 1021 verdes (eram 966).
