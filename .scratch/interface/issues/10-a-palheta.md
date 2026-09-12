# 10 — Camada 3: a palheta

Type: task
Status: ready-for-agent
Blocked by: 09

**What to build:** uma janela aberta por atalho global — um campo de texto, o comando, e a janela
some. O comando roda em segundo plano, o resultado vira nota no vault, um toast avisa.

Spec: [../spec.md](../spec.md), *A palheta*. Fatos:
[research/05](../research/05-janela-local-e-launcher.md).

- [ ] `palheta.py`: registro de comandos (nome, ajuda, função), análise do texto digitado,
      despacho em thread de trabalho, contrato de resultado (nota escrita + aviso). Costura pura,
      testável sem janela.
- [ ] Comandos desta entrega: `daily` (gera agora), `anotar <texto>` (Falar), `perguntar <texto>`
      (resposta vira nota em `respostas/`, zona nova do agente), `abrir` (a `daily/atual.md` por
      URI `obsidian://`), `configurar` (abre o painel — camada 4). Nenhum dos seis comandos
      futuros.
- [ ] Janela Tk: sem borda, centrada, por cima, some ao despachar ou no Esc; entra por porta
      injetada (o teste monta a palheta sem Tk).
- [ ] Atalho global por `win32gui.RegisterHotKey` com `MOD_NOREPEAT`, em thread próprio com
      janela oculta e loop de mensagens próprio (o `_mainloop` do pystray consome as mensagens
      do thread dele). Combinação padrão configurável em `[palheta].atalho`.
- [ ] Bandeja: Tk no thread principal, `pystray` por `run_detached`; item de menu
      *Abrir a palheta*; o gesto de gravar continua exatamente igual.
- [ ] Personalidade do Whis (sereno, econômico) nas respostas de `perguntar`; a fonte só aparece
      se pedida — o fio de 24h já sustenta.
- [ ] Suíte inteira verde.

## Notas para o executor

- Sondas feitas na sessão principal antes desta camada, com resultado no comentário abaixo:
  `RegisterHotKey` sob `pythonw.exe` recebendo `WM_HOTKEY`, e `pystray.run_detached` convivendo
  com `mainloop` do Tk. Se alguma falhou, a forma desta camada muda — leia antes.
- Chamada de outro thread para o Tk só por `after()`; ação de 60 s nunca no handler.
- O comando longo custa dinheiro (pergunta ≈ US$ 0,56, daily ≈ US$ 0,70): sem retry automático.
