# 02 — Onde as vagas e os freelas estão, e como se leem

Type: research
Status: open
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
