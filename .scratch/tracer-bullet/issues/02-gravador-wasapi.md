# 02 — Gravador WASAPI sob demanda

**What to build:** A captura de áudio da reunião: um script/CLI que, ao iniciar, grava simultaneamente o microfone e o loopback WASAPI (a voz dos outros no fone) em **canais/arquivos separados** dentro de uma pasta de gravação datada, e para sob comando. É a matéria-prima do pipeline: a pasta produzida aqui é exatamente o que o ticket 01 consome. Validação por smoke manual (fora da costura de teste, conforme a spec): gravar ~1 minuto de um Meet real e conferir os dois arquivos audíveis.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Iniciar/parar gravação por comando, sem interação extra durante a reunião
- [ ] Microfone e áudio do sistema gravados em canais/arquivos separados, sincronizados o suficiente para transcrição
- [ ] Gravações salvas em pasta datada, fora do vault, no local configurado
- [ ] Funciona no Windows 11 nativo (sem WSL/Docker), com fone conectado
- [ ] Roteiro de smoke manual curto documentado no repo e executado com sucesso num Meet real
