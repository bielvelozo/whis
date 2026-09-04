# 04 — As fontes ao vivo

**What to build:** git, Linear e Slack como ferramentas que o agente pode consultar quando o
vault não tiver a resposta. Escolha do usuário em 2026-09-04, Slack incluído.

Contrato: **[contrato-busca.md](../contrato-busca.md)**, seções 2 e 6.

**Blocked by:** 01, 02

**Status:** blocked

- [ ] As três entram como ferramentas novas, pelas fábricas `de_configuracao` dos coletores que
      já existem — **nenhum coletor é reimplementado**
- [ ] A blocklist do Slack, o `so_com_mencao` e o filtro de exclusão **continuam valendo**, de
      graça, por virem junto com os coletores. Há teste mordendo isso
- [ ] Fonte desligada na configuração simplesmente não vira ferramenta
- [ ] Fonte que falha vira resposta útil ao modelo ("o Slack não respondeu: ..."), não exceção
      que derruba a pergunta
- [ ] O prompt manda procurar no vault **antes**: a nota é gratuita, a API não
- [ ] Citação de fonte ao vivo tem origem própria (`linear:FN-1610`, `slack:#canal`), para o
      usuário saber que aquilo não veio do vault
- [ ] Testes com os coletores fakes; nenhum teste novo fala com serviço real fora de `rede`
- [ ] Suíte verde, sem editar teste existente

## Notas para o executor

- **Esta é a camada com mais risco de privacidade da entrega.** O usuário escolheu incluir o
  Slack sabendo disso, e a resposta de projeto é não ter caminho novo: se a consulta ao vivo
  passar pelos coletores, ela herda tudo que já foi ajustado. Um atalho que fale com a Web API
  direto quebraria a blocklist em silêncio.
- Uma pergunta pode virar várias chamadas de API. Registre no log quantas foram.
