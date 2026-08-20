# 03 — STT real: adapter Deepgram

**What to build:** A transcrição de verdade: um adapter da porta de STT que envia os canais gravados para a Deepgram (Nova-3 multilingual, batch) e devolve a transcrição com a distinção "eu vs. os outros" derivada dos canais separados. A API key vem da configuração local (crédito de US$ 200 — custo real zero). Demo: processar uma gravação real com o pipeline do ticket 01 e ler a transcrição verdadeira, com falantes, no vault. Falha de rede/STT não pode produzir nota parcial — a gravação permanece intacta e o erro é sinalizado de forma legível.

**Blocked by:** 01 — Esqueleto do pipeline com portas fake.

**Status:** ready-for-agent

- [ ] Pipeline com o adapter real transcreve uma gravação de teste em pt-BR com termos em inglês corretamente
- [ ] Transcrição distingue a fala do usuário da dos demais participantes
- [ ] API key e opções vêm de configuração local; nenhum segredo no repo
- [ ] Falha do STT preserva a gravação, não escreve nota parcial e loga o erro de forma diagnosticável
- [ ] Testes da costura continuam verdes com o fake; o adapter real tem verificação própria mínima (ex.: teste marcado/manual contra a API)
