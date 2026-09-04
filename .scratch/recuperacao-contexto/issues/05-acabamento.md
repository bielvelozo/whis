# 05 — Acabamento e uso real

**What to build:** o que falta para o agente ser confiável no dia a dia: subir com o logon,
deixar rastro, mostrar o custo, e o roteiro que prova tudo na máquina do usuário — incluindo o
pedido ao admin.

**Blocked by:** 01, 02, 03, 04

**Status:** blocked

- [ ] `second-brain windows` passa a poder instalar o atendente no logon, ao lado da bandeja
- [ ] `atender` e `perguntar` escrevem no arquivo de log, como `daily` e `diario` já fazem
- [ ] O custo de cada resposta vai para o log, com o aviso de que a assinatura não cobra por token
- [ ] Códigos de saída de `perguntar` documentados no `--help`, no padrão da entrega anterior:
      `0` respondeu, `3` respondeu sem achar, `1` não conseguiu, `2` erro de uso
- [ ] `docs/smoke-atendente.md`: criar o bot na app que já existe, os scopes, o Socket Mode, o
      app-level token, **o texto do pedido ao admin já pronto para colar**, e o teste de ponta a
      ponta pela DM
- [ ] O roteiro cobre a pasta privada: configurar, perguntar sobre algo que só existe lá, e
      confirmar que o agente diz que não achou
- [ ] Suíte inteira verde, sem editar teste existente

## Notas para o executor

- O `docs/smoke-slack.md` atual diz ao admin que a app **não** pede bot token. Atualize-o, ou o
  usuário chega na conversa com o admin contradizendo o que prometeu antes.
- A prova final é humana: a demo-mestra da seção 7 do contrato, pelo celular. **Gasta a
  assinatura — peça antes.**
