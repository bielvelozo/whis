# 05 — Acabamento e uso real

**What to build:** o que falta para a busca ser confiável em uso diário: rastro em log, códigos
de saída, o custo visível e o roteiro de smoke que prova a entrega na máquina do usuário.

**Blocked by:** 01, 02, 03, 04

**Status:** blocked

- [ ] `perguntar` e `chat` escrevem no arquivo de log, como `daily` e `diario` já fazem
- [ ] Códigos de saída documentados no `--help`, no padrão que a entrega anterior fixou:
      `0` respondeu, `3` respondeu sem achar nada, `1` não conseguiu responder, `2` erro de uso
- [ ] O custo de cada pergunta aparece no fim da resposta e no log, com o aviso de que a
      assinatura não cobra por token
- [ ] `docs/smoke-busca.md`: roteiro curto — configurar a pasta privada e conferir que ela some,
      fazer a pergunta da demo-mestra, conferir a citação abrindo o arquivo, e uma pergunta que
      força a consulta ao vivo
- [ ] Testes de comportamento para os códigos de saída e para o rastro, pela costura da CLI
- [ ] Suíte inteira verde, sem editar teste existente

## Notas para o executor

- A prova final é humana, como nas entregas anteriores: uma pergunta de verdade, sobre o vault de
  verdade, cuja resposta o usuário consiga conferir abrindo o arquivo citado. **Gasta a
  assinatura — peça antes de rodar.**
- A demo-mestra está na seção 7 do contrato.
