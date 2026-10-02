# 02 — Onde as vagas e os freelas estão, e como se leem

Type: research
Status: resolved
Blocked by: 01

## Question

Nos sites de TI mais famosos de vaga e freela (ticket 01: ele não conhece todos, a lista é desta
pesquisa), quais fontes existem e **como o Whis lê cada uma**, a
R$ 0 ou perto disso, rodando no PC dele (ADR 0001)?

Para cada fonte: API oficial (e custo), RSS, página pública lida sem login, ou só navegador
logado; o que cada leitura traz (título, empresa, faixa, remoto, data, link); volume por dia;
risco para a conta dele e termos de uso. E, porque o Whis vai **criar conta e aplicar** por ele
(ticket 01): o que cada site pede para abrir conta (e-mail, telefone, documento, CAPTCHA), quanto
custa mandar uma proposta, e se a candidatura sai pelo próprio site ou manda para fora. Candidatas conhecidas, a conferir e completar:

- Emprego no Brasil: LinkedIn, Gupy, Programathor, GeekHunter, Indeed — o presencial só conta em
  Ribeirão Preto e São Paulo, com piso maior (ticket 06).
- Remoto internacional: LinkedIn, We Work Remotely, Remotive, RemoteOK, Himalayas, Wellfound,
  Hacker News *Who is hiring*.
- Freela: Workana, 99Freelas, Upwork (o RSS de busca acabou em 2024 — conferir o que sobrou).
- O X, que o jornal já lê ([ADR 0003](../../../docs/adr/0003-x-por-navegador.md)): vale uma busca
  por `hiring`?

**Pedido dele (ticket 06)**: o levantamento de **quanto custa cada proposta em cada site de freela**
— o teto de gasto por corrida sai daqui. E **o preço de mercado** do que ele faz em cada site, para o
Whis saber o que é "abaixo" e "ligeiramente abaixo".

Para cada site, também: **mandar proposta é de graça e sem limite?** Só nesses o Whis envia sozinho
as de tentar a sorte (ticket 06, rodada 3).

O **e-mail dedicado é Gmail** (ticket 06): como o Whis lê a caixa para confirmar conta nova e ver
resposta de cliente. Candidatas: IMAP com senha de app (pede verificação em duas etapas) ou a API do
Gmail — que tem a armadilha já vista na interface: app OAuth em *Testing* dá refresh token que
vence em 7 dias ([research 02 da interface](../../interface/research/02-windows-agendador-e-aviso.md)).

Achados em `../research/02-fontes-de-vagas.md`.

## Answer

Três pesquisas: [02a — vagas de emprego](../research/02a-vagas-de-emprego.md), [02b — sites de
freela](../research/02b-sites-de-freela.md), [02c — o Gmail](../research/02c-gmail.md).

- **Remoto internacional se lê de graça e sem navegador**: Himalayas, Remotive, RemoteOK, Jobicy e HN
  (Algolia) têm JSON público; o We Work Remotely, RSS. O filtro que mais pesa é "aceita Brasil?",
  mais que a stack; faixa salarial é rara, então vaga sem faixa não pode ser descartada por isso.
- **No Brasil a Gupy é a fonte** (JSON do portal, não documentado) e também a candidatura (conta
  única com CPF). `frontendbr/vagas` e `backend-br/vagas` pela API do GitHub.
- **Indeed, Wellfound e Catho ficam fora** (termos e anti-bot); GeekHunter, Revelo, Turing, Toptal
  são redes de talentos — perfil a criar, não fonte a varrer.
- **Freela: nenhum site com volume é grátis e sem limite.** Workana (poucas conexões por semana),
  99Freelas (10 por mês, e 24 h de exclusividade para assinante), Upwork (Connects pagos, US$
  0,60–2,40 por proposta), Freelancer.com (6 lances por mês). **Pela regra dele, freela nunca sai
  sozinho.**
- **Workana e 99Freelas leem por HTTP simples**: a Workana guarda os projetos em JSON no atributo
  `:results-initials`; a 99Freelas é HTML com `li.result-item`. O Upwork tem MCP oficial desde
  10/08/2026, mas pede conta.
- **Preço de mercado no Brasil**: landing page R$ 500–2.500, site institucional R$ 1.500–6.000,
  e-commerce R$ 2.000–9.000; Upwork preço fixo, mediana US$ 100.
- **Gmail**: IMAP com senha de app, só leitura, pela biblioteca padrão — e a entrega 1 nem precisa.

Os volumes por dia são estimativa: a camada 0 é `whis hunt --simular` na máquina dele.
