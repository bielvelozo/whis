# 14 — Camada 7: os ajustes da palheta depois da segunda prova

Type: task
Status: ready-for-agent
Blocked by: 13

**What to build:** o que a segunda prova do usuário (2026-09-17) pediu — "ficou muito melhor, agora
só tem algumas melhorias". Quatro pontos, nas palavras dele, mais uma pergunta respondida.

- [ ] **1. Atalho `ctrl+space`.** `ATALHO_PADRAO` em `atalho_global.py` e o valor no
      `MODELO_DE_CONFIGURACAO` (`[palheta].atalho`) passam a `ctrl+space`; o `config.toml` real
      dele ainda tem `ctrl+alt+w` — a troca lá é dele (painel `settings`) ou pela tarefa
      descartável como usuário, se a rota voltar a atravessar. Sondado livre nesta máquina em
      2026-09-17 (`RegisterHotKey` aceitou `ctrl+space`, `ctrl+shift+space` e `alt+space`).
- [ ] **2. Tab autocompleta.** Hoje `<Tab>` move a seleção (`janela_da_palheta.py:145`). Passa a
      completar o campo com o comando da ação selecionada (`daily`, `ask`...) mais um espaço quando
      o comando aceita argumento; Tab de novo com o campo já completo cicla a seleção.
- [ ] **3. O rótulo também filtra e casa.** "generate daily" digitado não acha *Generate daily*
      porque `filtrar` casa só o nome do comando (`daily`). O filtro passa a casar prefixo de
      qualquer palavra do rótulo **e** do nome; e o texto digitado igual ao rótulo (sem
      diferenciar maiúsculas) executa a ação como se fosse o comando. O destaque
      (`comando_destacado`) acompanha: destaca o rótulo inteiro quando é ele que casa.
- [ ] **4. Fundo translúcido estilo Raycast.** Não é `-alpha` (deixaria o texto transparente
      também): é o efeito acrílico do DWM na janela do Tk —
      `SetWindowCompositionAttribute(hwnd, ACCENT_ENABLE_ACRYLICBLURBEHIND)` por `ctypes` no
      `winfo_id()` da raiz, mantendo os cantos arredondados; se o Windows recusar (API não
      documentada, muda entre builds), cair para `-alpha 0.94` com log, nunca quebrar a janela.
      Provar com captura de tela sob `pythonw`, como na camada 6.
- [ ] Suíte inteira verde; `docs/smoke-interface.md` (atalho e Tab) e `CONTEXT.md` (atalho)
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
