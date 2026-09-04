# 01 — A costura, a fronteira e o fio

**What to build:** `responder(pergunta, conversa) → Resposta` com as ferramentas de vault atrás
dela, a fronteira da pasta privada, o fio de conversa que expira em 24h, as chaves de
configuração e o fake da porta. É a camada que torna todas as outras testáveis sem rede e sem
Slack.

Contrato: **[contrato-busca.md](../contrato-busca.md)**, seções 1 a 4.

**Blocked by:** nada

**Status:** ready-for-agent

- [ ] `busca.py` com `Citacao`, `Resposta`, `ErroDeBusca` e `PortaBusca`
- [ ] `ferramentas.py` com `buscar_no_vault`, `ler_nota`, `listar` e `ForaDaFronteira`
- [ ] `conversa.py` com `Turno` e `Conversa`, expirando por **24h de silêncio**, com relógio
      injetado e persistência em `conversas.json` ao lado do `config.toml`
- [ ] `pergunta.py` com `responder`, na ordem fixa da seção 3
- [ ] `[privacidade].pastas_privadas` e `[busca].maximo_de_notas`, achatadas, validadas e no
      `MODELO_DE_CONFIGURACAO`
- [ ] `BuscaFake` guardando pergunta, ferramentas e histórico recebidos
- [ ] **A fronteira sondada nos dois sentidos**: arquivo sob a pasta privada não aparece na busca,
      não é lido, não é listado, e `..` não escapa nem para fora do vault
- [ ] A recusa diz "não existe", nunca "é privado" — dizer que há algo escondido já vaza
- [ ] Arquivo de conversas corrompido não derruba nada: vale como conversa vazia
- [ ] Suíte inteira verde (**610 hoje**), sem editar teste existente

## Notas para o executor

- A checagem de fronteira é **uma função só**, usada pelas três ferramentas — mesma lição do
  filtro de exclusão do diário, que age num ponto só. Compare caminhos **resolvidos**, como
  `vault.escrever` já faz.
- A expiração é **por silêncio**: 24h desde o último turno, não meia-noite. Teste com relógio
  injetado; ninguém espera 24 horas para rodar a suíte.
- `conversas.json` não vai para o vault. Rascunho de conversa não é memória durável.
