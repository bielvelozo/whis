# 14 — Camada 7: os ajustes da palheta depois da segunda prova

Type: task
Status: resolved
Blocked by: 13

**What to build:** o que a segunda prova do usuário (2026-09-17) pediu — "ficou muito melhor, agora
só tem algumas melhorias". Quatro pontos, nas palavras dele, mais uma pergunta respondida.

- [x] **1. Atalho `ctrl+space`.** `ATALHO_PADRAO` em `atalho_global.py` e o valor no
      `MODELO_DE_CONFIGURACAO` (`[palheta].atalho`) passam a `ctrl+space`; o `config.toml` real
      dele ainda tem `ctrl+alt+w` — a troca lá é dele (painel `settings`) ou pela tarefa
      descartável como usuário, se a rota voltar a atravessar. Sondado livre nesta máquina em
      2026-09-17 (`RegisterHotKey` aceitou `ctrl+space`, `ctrl+shift+space` e `alt+space`).
- [x] **2. Tab autocompleta.** Hoje `<Tab>` move a seleção (`janela_da_palheta.py:145`). Passa a
      completar o campo com o comando da ação selecionada (`daily`, `ask`...) mais um espaço quando
      o comando aceita argumento; Tab de novo com o campo já completo cicla a seleção.
- [x] **3. O rótulo também filtra e casa.** "generate daily" digitado não acha *Generate daily*
      porque `filtrar` casa só o nome do comando (`daily`). O filtro passa a casar prefixo de
      qualquer palavra do rótulo **e** do nome; e o texto digitado igual ao rótulo (sem
      diferenciar maiúsculas) executa a ação como se fosse o comando. O destaque
      (`comando_destacado`) acompanha: destaca o rótulo inteiro quando é ele que casa.
- [x] **4. Fundo translúcido estilo Raycast.** Não é `-alpha` (deixaria o texto transparente
      também): é o efeito acrílico do DWM na janela do Tk —
      `SetWindowCompositionAttribute(hwnd, ACCENT_ENABLE_ACRYLICBLURBEHIND)` por `ctypes` no
      `winfo_id()` da raiz, mantendo os cantos arredondados; se o Windows recusar (API não
      documentada, muda entre builds), cair para `-alpha 0.94` com log, nunca quebrar a janela.
      Provar com captura de tela sob `pythonw`, como na camada 6.
- [x] Suíte inteira verde; `docs/smoke-interface.md` (atalho e Tab) e `CONTEXT.md` (atalho)
      atualizados.

**Pergunta dele respondida:** o Whis sobe sozinho no logon — `Whis.lnk` está na pasta de
Inicialização desde 2026-09-12 (criado por `whis windows` rodando como ele). Nenhum comando a cada
reinício. A daily e o vigia são tarefas do Agendador, independentes da bandeja.

## Notas para o executor

- A bandeja dele está no ar com o código de `605d5e4` (pids mudam); depois do commit ele reinicia
  pelo Menu Iniciar (**Whis**) ou a sessão reinicia pela tarefa descartável com principal
  interativo (`Whis-Reiniciar-Bandeja`, `ORCHESTRATION.md`).
- Nunca simule teclas com a bandeja dele no ar sem um hotkey privado no config de teste
  (`ctrl+alt+shift+f9`): foi assim que a camada 6 disparou um `daily` de verdade por engano.

## Comments

**Camada 7 entregue e fechada** (2026-09-17; direto na sessão principal, sem executor).

- **1. `ctrl+space`.** `ATALHO_PADRAO` e o modelo do `config.toml`. O `config.toml` real dele foi
  trocado pela tarefa descartável rodando como ele (linha substituída, backup
  `config.toml.bak-20260917-110923`, relido com `carregar` → `ctrl+space`), e a bandeja dele foi
  parada e relançada pela tarefa com principal interativo (pids 19700/24924, pai `svchost`).
  Log real dele, lido pela mesma rota: `11:09:49 Atalho global ctrl+space registrado.` Sonda
  `RegisterHotKey` desta sessão depois disso: `ctrl+space` tomado (erro 1409), `ctrl+alt+w` livre.
- **2. Tab.** `completar(acao)` = o comando, mais um espaço quando `Acao.aceita_argumento` (vem de
  `Comando.parametro`: `ask`, `note`, `doubt`). Com o campo já igual ao completado, Tab passa à
  próxima ação visível e completa com ela — assim o Enter sempre bate com a linha destacada.
- **3. Rótulo.** `filtrar` casa o prefixo da primeira palavra no nome do comando (primeiro) e em
  qualquer palavra do rótulo (depois, sem repetir): `generate` e `generate daily` acham *Generate
  daily*; `no` lista *Note* e *Open note*. `comando_pelo_rotulo` faz o texto igual a um rótulo
  despachar o nome do comando; `comando_destacado(texto, acoes)` destaca o rótulo inteiro nesse caso.
- **4. Acrílico.** Módulo novo `acrilico.py`: `SetWindowCompositionAttribute` com
  `ACCENT_ENABLE_ACRYLICBLURBEHIND` (tinta = `FUNDO` a `0xCC`) e cantos por
  `DwmSetWindowAttribute(DWMWCP_ROUND)`, tudo por `ctypes`, devolvendo `bool` e nunca levantando.
  **Achado da sonda** (`research/sonda-acrilico.py`, seis variantes com blocos de cor atrás): neste
  build (26200) o DWM rende o material mas **não amostra as janelas atrás** de um popup — nem a
  `DWMWA_SYSTEMBACKDROP_TYPE` documentada — e o conteúdo GDI do Tk entra com alpha 0. Por isso a
  janela leva o acrílico **e** `-alpha 0.92` por cima (é o alpha que deixa ver o que está atrás; o
  texto a 92% continua legível); o `-transparentcolor` saiu, porque a chave de cor esconde o
  material. Fallback quando o Windows recusa: `-transparentcolor` + `-alpha 0.94` com aviso no log.
- **Prova de tela sob `pythonw`** (janela de verdade, `prova-janela.py` no scratchpad da sessão):
  vazia com as sete ações; `generate daily` destacado inteiro em roxo e só *Generate daily* na
  lista; `no` + Tab → `note ` com *Note* e *Open note*; Tab de novo → `open` com só *Open note*; o
  painel translúcido sobre a tela dele, com o material e os cantos do DWM.
- **Suíte: 1071 verdes / 8 desselecionados** (eram 1063; +4 em `test_palheta.py`, +4 em
  `test_acrilico.py`). `docs/smoke-interface.md` (passos 2 e 5) e `CONTEXT.md` (Palheta) atualizados.
- Rota da tarefa descartável **atravessou de novo** nesta sessão (scripts e logs na raiz do repo);
  a leitura direta do `%APPDATA%` dele por esta sessão continua sendo uma cópia velha (log parado
  em 16/09, config ainda com `ctrl+alt+w`) — nunca afirmar nada por ela. Os três scripts da rota
  ficaram em `research/rota-tarefa-descartavel/`.

