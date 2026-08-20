# 04 — Resumo real: adapter Claude

**What to build:** O resumo de verdade: um adapter da porta de resumo que envia a transcrição ao Claude (via conta Pro/Max do usuário, Claude Agent SDK — padrão validado no Whis) e devolve o resumo em português estruturado em decisões, ações/pendências e tópicos, que o pipeline grava na nota de reunião. Demo: uma nota de reunião real, legível e útil, aberta no Obsidian.

**Blocked by:** 01 — Esqueleto do pipeline com portas fake.

**Status:** ready-for-agent

- [ ] Resumo em português cobrindo decisões, ações/pendências e tópicos da reunião
- [ ] Autenticação pela conta Claude do usuário (OAuth), sem API key paga à parte
- [ ] Falha na geração do resumo não perde a transcrição — nota pode ser regenerada
- [ ] Testes da costura continuam verdes com o fake; o adapter real tem verificação própria mínima
