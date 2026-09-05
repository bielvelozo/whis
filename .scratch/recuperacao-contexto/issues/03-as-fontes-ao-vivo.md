# 03 — As fontes ao vivo

**What to build:** git, Linear e Slack como ferramentas que o agente consulta quando o vault não
tem a resposta. Escolha do usuário em 2026-09-04, Slack incluído.

Contrato: **[contrato-busca.md](../contrato-busca.md)**, seções 2 e 6.

**Blocked by:** 01, 02

**Status:** resolved

- [x] As três entram como ferramentas, pelas fábricas `de_configuracao` dos coletores existentes
      — **nenhum coletor é reimplementado**
- [x] Blocklist do Slack, `so_com_mencao` e filtro de exclusão **continuam valendo**, de graça,
      por virem junto com os coletores. Há teste mordendo isso
- [x] Fonte desligada na configuração não vira ferramenta
- [x] Fonte que falha vira resposta útil ao modelo, não exceção que derruba a pergunta
- [x] O prompt manda procurar no vault **antes**: a nota é gratuita, a API não
- [x] Citação ao vivo tem origem própria (`linear:FN-1610`, `slack:#canal`), para o usuário saber
      que aquilo não veio do vault
- [x] Testes com os coletores fakes; nada de serviço real fora de `rede`
- [x] Suíte verde (**793**, eram 767), sem editar teste existente

## Notas para o executor

- **É a camada com mais risco de privacidade da entrega.** O usuário escolheu incluir o Slack
  sabendo disso, e a resposta de projeto é não ter caminho novo: passando pelos coletores, a
  consulta herda tudo que já foi ajustado. Um atalho que fale com a Web API direto quebraria a
  blocklist em silêncio.
- Uma pergunta pode virar várias chamadas de API. Registre no log quantas foram.

## Comments

**Camada 03 entregue e fechada** (2026-09-04). `fontes_ao_vivo.py` (os coletores como tools de
um segundo servidor MCP, `fontes`), `busca_claude.py` ganhou `montar_opcoes`, o adendo
`PROMPT_DAS_FONTES_AO_VIVO` e o parâmetro `fontes_ao_vivo`, `montar_busca` em `__main__.py`
liga as fontes pelas fábricas, e 26 testes novos em `test_fontes_ao_vivo.py`. Suíte em **793
verdes**, 8 desselecionados, nenhum teste existente editado. O harness HTTP do Slack foi
**importado** de `test_fonte_slack.py`, não copiado.

**Como cada régua continua valendo, e onde o teste morde:**

- **Blocklist e `so_com_mencao`**: vêm de `fonte_slack.de_configuracao`, que é o que
  `montar_fontes` chama — a busca reusa `montar_fontes` inteira. Teste
  `test_a_blocklist_do_slack_vale_de_graca_pelo_coletor_de_verdade`: o coletor real, pela
  fábrica real, com `config.toml` real de teste e HTTP falso; a prova é a **ausência da
  requisição** para `C0TERAPIA`, não a ausência do resultado.
- **Filtro de exclusão**: `fontes.filtrar` num ponto só (`FontesAoVivo.consultar`), com
  `excluir` vindo de `[privacidade].excluir` pela fábrica. Dois testes: o comportamento
  (mensagem de terapia não chega ao texto) e a fábrica (`excluir == ("terapia",)`).
- **Fonte desligada não vira ferramenta**: `montar_busca` com `[git]` e `[slack]` liga só
  `consultar_git` e `consultar_slack`; sem nada, `tools() == []` e o prompt nem menciona as
  fontes (um modelo instruído a usar ferramenta inexistente finge que usou).
- **Fonte que falha**: `ErroDeFonte` vira texto com `is_error` — "não pôde ser lida agora:
  <motivo>. Responda com o que o vault tem." — sem exceção.
- **Origem própria**: `git:loja@a1b2c3d`, `linear:FN-1610`, `slack:#plataforma`, parametrizado,
  com a asserção de que nenhuma termina em `.md`.

**Provas executadas:**

- **Mutação, 16 linhas**: filtro de exclusão não aplicado → 2; termo ignorado → 1; janela
  ignora as horas → 2; horas sem teto → 1; mais antigo primeiro → 1; limite ignorado → 1;
  falha não marcada como erro → 1; falha derruba a pergunta → 1; servidor nasce sem fonte → 2;
  origem do git sem prefixo → 2; chamadas não contadas → 1; fontes não entram nas opções → 1;
  nomes não permitidos → 1; prompt das fontes não entra → 1; fábrica esquece o filtro → 1;
  fábrica ignora as fontes → 2. Nenhuma sobreviveu.
- **A fábrica com a configuração real da máquina, só construção**: liga `git`, `linear` e
  `slack`; o coletor do Slack nasce com a blocklist `slackbot, uslack, notifier, sentry,
  zeno-agent` e `so_com_mencao = dev-codereview` — os mesmos da daily, sem ninguém lembrar
  deles. Nenhuma API foi chamada.

**Não provado**: nenhuma consulta ao vivo com o Claude de verdade — mesma pendência da camada
02, o mesmo teste de rede a rodar quando o usuário autorizar. Uma pergunta como *"o que
aconteceu no Slack na última hora?"* pelo `perguntar` exercita esta camada de ponta a ponta e
gasta a assinatura.

**Achados fora do escopo** no DEFERRED, marcados "Recuperação de contexto, camada 03".
