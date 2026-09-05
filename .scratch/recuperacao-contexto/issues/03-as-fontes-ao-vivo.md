# 03 — As fontes ao vivo

**What to build:** git, Linear e Slack como ferramentas que o agente consulta quando o vault não
tem a resposta. Escolha do usuário em 2026-09-04, Slack incluído.

Contrato: **[contrato-busca.md](../contrato-busca.md)**, seções 2 e 6.

**Blocked by:** 01, 02

**Status:** ready-for-agent

- [ ] As três entram como ferramentas, pelas fábricas `de_configuracao` dos coletores existentes
      — **nenhum coletor é reimplementado**
- [ ] Blocklist do Slack, `so_com_mencao` e filtro de exclusão **continuam valendo**, de graça,
      por virem junto com os coletores. Há teste mordendo isso
- [ ] Fonte desligada na configuração não vira ferramenta
- [ ] Fonte que falha vira resposta útil ao modelo, não exceção que derruba a pergunta
- [ ] O prompt manda procurar no vault **antes**: a nota é gratuita, a API não
- [ ] Citação ao vivo tem origem própria (`linear:FN-1610`, `slack:#canal`), para o usuário saber
      que aquilo não veio do vault
- [ ] Testes com os coletores fakes; nada de serviço real fora de `rede`
- [ ] Suíte verde, sem editar teste existente

## Notas para o executor

- **É a camada com mais risco de privacidade da entrega.** O usuário escolheu incluir o Slack
  sabendo disso, e a resposta de projeto é não ter caminho novo: passando pelos coletores, a
  consulta herda tudo que já foi ajustado. Um atalho que fale com a Web API direto quebraria a
  blocklist em silêncio.
- Uma pergunta pode virar várias chamadas de API. Registre no log quantas foram.
