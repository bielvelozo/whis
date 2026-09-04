# 02 — O agente de verdade

**What to build:** `busca_claude.py` — o adaptador que implementa `PortaBusca` com o Claude da
conta do usuário, expondo as ferramentas da camada 01 ao modelo e traduzindo a resposta em
`Resposta`, com citações e com o fio da conversa.

Contrato: **[contrato-busca.md](../contrato-busca.md)**, seções 1, 2 e 6.

**Blocked by:** 01

**Status:** blocked

- [ ] Implementa `PortaBusca` pela conta do usuário (OAuth), recusando API key paga como
      `resumo_dia_claude` já faz
- [ ] As ferramentas da camada 01 viram tool definitions; o modelo **não** recebe shell nem
      acesso a arquivo
- [ ] O `historico` da conversa entra no turno, para a pergunta de acompanhamento funcionar
- [ ] O prompt manda: procurar no vault antes de tudo, **citar o arquivo** de cada afirmação, e
      responder "não achei" em vez de deduzir
- [ ] `ForaDaFronteira` é traduzido para o modelo como "esse arquivo não existe"
- [ ] Resposta ilegível vira `ErroDeBusca`, com o texto cru no log
- [ ] `custo_usd` a partir do `ResultMessage`, no formato da entrega anterior
- [ ] Teste de tradução sem rede e um `@pytest.mark.rede` opcional, que **gasta a assinatura**
- [ ] Suíte verde, sem editar teste existente

## Notas para o executor

- O irmão mais próximo é `resumo_dia_claude.py`: mesma credencial, mesma recusa de API key paga,
  mesmo jeito de registrar custo.
- **Nunca dê `Bash` nem leitura de arquivo ao modelo.** A pasta privada só é privada porque todo
  acesso passa por `Ferramentas`.
- Uma resposta sem citação nenhuma é suspeita: registre no log, mas não invente citação.
