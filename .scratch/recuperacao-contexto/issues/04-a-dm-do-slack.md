# 04 — A DM do Slack

**What to build:** `second-brain atender` — o processo que fica escutando a DM do bot no Slack por
Socket Mode, responde ali e mantém o fio de 24 horas. **É a entrega inteira do ponto de vista do
usuário**; as três camadas anteriores existem para esta funcionar.

Contrato: **[contrato-busca.md](../contrato-busca.md)**, seções 3 e 5.

**Blocked by:** 01, 02, 03, **e a aprovação do admin do Slack**

**Status:** blocked

- [ ] `atendente.py`: recebe evento de mensagem, chama `responder`, publica a resposta na mesma DM
- [ ] **Socket Mode**, com app-level token (`xapp-`) e bot token (`xoxb-`) em chaves novas de
      `[slack]`. Conexão de dentro para fora, sem porta aberta
- [ ] O bot **reage à mensagem** assim que a recebe: uma busca demora, e silêncio parece pane
- [ ] Só atende **DM com ele mesmo**; mensagem em canal é ignorada
- [ ] Ignora as próprias mensagens, senão responde a si mesmo em laço
- [ ] O fio de 24h da camada 01, por conversa
- [ ] Falha de uma resposta não derruba o processo: vira mensagem de erro em português na DM e o
      atendimento continua
- [ ] Reconecta sozinho quando a conexão cai — é um processo que fica no ar o dia inteiro
- [ ] `second-brain atender` sobe o processo; **testado sem Slack**, com o cliente injetado e
      eventos de fixture
- [ ] Suíte verde, sem editar teste existente

## Notas para o executor

- **Não coloque isto dentro da bandeja.** Ela tem trava de instância e máquina de estados de
  gravação, e o pipeline de reunião está em uso real. Processo separado.
- O passo humano está no `docs/smoke-atendente.md` (camada 05) e **precisa de aprovação nova do
  admin**, porque o roteiro atual promete que a app não pede bot token.
- Escrita em `notas/` só sob pedido explícito na conversa, por `vault.escrever` com
  `zonas=(PASTA_NOTAS,)`.
