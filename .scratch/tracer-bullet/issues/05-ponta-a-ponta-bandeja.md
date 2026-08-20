# 05 — Ponta a ponta na bandeja

**What to build:** O tracer bullet completo, no gesto decidido: um ícone na bandeja do Windows com liga/desliga da gravação e indicação visual de estado (gravando/parado). Parar a gravação dispara o pipeline automaticamente (gravador do 02 → pipeline do 01 com adapters reais do 03 e 04) e a nota aparece no vault sem nenhum passo manual. É a demo-mestra da spec: *aperto um botão durante a reunião → nota transcrita/resumida aparece no vault*.

**Blocked by:** 02 — Gravador WASAPI sob demanda; 03 — STT real: adapter Deepgram; 04 — Resumo real: adapter Claude.

**Status:** ready-for-agent

- [ ] Ícone na bandeja inicia e para a gravação com um clique e mostra o estado atual sem ambiguidade
- [ ] Parar a gravação dispara o processamento completo sem interação extra
- [ ] Smoke manual da spec executado: reunião real no Meet → nota com resumo + transcrição linkada no Obsidian
- [ ] Erros do pipeline aparecem de forma visível/diagnosticável (a bandeja não engole falhas)
- [ ] A bandeja é casca fina: nenhuma lógica de pipeline vive nela
