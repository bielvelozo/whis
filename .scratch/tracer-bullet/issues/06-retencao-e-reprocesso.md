# 06 — Retenção e reprocesso

**What to build:** O ciclo de vida do áudio bruto e a rede de segurança: gravações com transcrição bem-sucedida são retidas por 7 dias (configurável) fora do vault e apagadas pela rotina de limpeza; gravações cujo processamento falhou permanecem indefinidamente até um **comando de reprocesso** — idempotente — completá-las. Nenhuma reunião se perde por instabilidade, e áudio sensível não acumula para sempre.

**Blocked by:** 01 — Esqueleto do pipeline com portas fake; 03 — STT real: adapter Deepgram.

**Status:** ready-for-agent

- [ ] Rotina de limpeza apaga apenas gravações com processamento bem-sucedido e mais de 7 dias (período configurável)
- [ ] Gravações com falha nunca são apagadas pela limpeza
- [ ] Comando de reprocesso completa uma gravação retida e é idempotente (não duplica notas)
- [ ] Comportamentos cobertos por testes na costura única (com fakes), incluindo os casos de falha
