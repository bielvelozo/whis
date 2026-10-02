# Research 02b — Sites de freela

Levantado em 2026-10-02.

Parte do [ticket 02](../issues/02-onde-as-vagas-estao.md). Regras que filtram tudo aqui (ticket 06):
freela **por projeto** (preço fechado) e **contínuo pequeno** entram, **por hora** fica fora; o Whis
**só envia sozinho** as de *tentar a sorte* e **só onde mandar proposta é de graça E sem limite**;
onde cobra ou limita, só prepara; o Whis **nunca gasta dinheiro**.

**Como ler as marcas:**

- **[F]** fato com fonte (link na mesma linha ou na seção do site).
- **[I]** inferência do pesquisador, a partir dos fatos.
- **[P]** conhecimento prévio do pesquisador, **não conferido nesta pesquisa** — tratar como hipótese
  e conferir à mão antes da spec.

**Limite desta pesquisa.** O proxy de rede desta sessão bloqueou a leitura direta de quase todos os
sites (upwork.com, workana.com, 99freelas.com.br, freelancer.com, fiverr.com, as centrais de ajuda,
reclameaqui, tabnews, medium) e a cota de buscas da sessão acabou no meio. Os fatos vêm de
resultados de busca (que citam as páginas oficiais) e de código público no GitHub. Os números de
plano e preço **mudam com frequência** — a spec deve tratá-los como configuração, não como
constante, e a primeira corrida deve conferi-los na tela.

## Resumo

- **Nenhum site com volume passa na regra "grátis e sem limite".** Workana (poucas conexões por
  semana), 99Freelas (10 conexões por mês), Upwork (Connects pagos), Freelancer.com (6 lances por
  mês), PeoplePerHour e Guru (créditos/lances limitados) e GetNinjas (paga por contato) — todos
  limitam ou cobram. **[I]** Na prática, pela regra dele, **o Whis não envia nada sozinho em site de
  freela**: tudo vira "preparado" e vai para ele. Isso esvazia a parte de freela da entrega 2 e vale
  levar de volta para ele antes da spec. Únicos candidatos a "grátis e sem limite", **não
  confirmados**: Contra e Crowd (ver seções) — e, mesmo neles, os termos contra automação pesam.
- **Recomendação para a entrega 1 (só ler e preparar):** **Workana** e **99Freelas** (volume em
  português, cliente brasileiro, preço fechado é o padrão, listagem pública lida **sem login**) e
  **Upwork** pelo **servidor MCP oficial** (lançado em 10/08/2026, OAuth na conta dele, feito para
  Claude/Claude Code) — este exige a conta Upwork existir. **Freelancer.com** como quarto, opcional
  (tem API oficial com busca de projetos). **GetNinjas** fica para depois (paga por contato, cliente
  local de orçamento baixo).
- **Descartados:** Toptal e Codeable (triagem pesada, perfil novo não entra; Toptal é por hora),
  Malt (Europa), Fiverr como fonte de *caçada* (é vitrine de gig: o cliente compra, ninguém manda
  proposta — serve como vitrine passiva na entrega 2, não na caçada), PeoplePerHour e Guru (pouco
  volume para web dev brasileiro, ganho marginal **[I]**).
- **Upwork mudou o jogo em 2026:** o RSS morreu em 20/08/2024; a API GraphQL pede **US$ 25 mil de
  ganhos e JSS ≥ 90 %** (fora de alcance para perfil novo); mas o **MCP oficial** dá busca de jobs,
  rascunho e envio de proposta (com confirmação, gastando Connects). É o único caminho de leitura
  automatizada **permitido** no Upwork — qualquer robô no navegador arrisca a conta.
- **Custo por proposta, em reais (câmbio ~R$ 5,4 **[I]**):** Upwork ≈ US$ 0,15 × 4–16 Connects =
  **US$ 0,60–2,40 (R$ 3–13) por proposta**; Workana e 99Freelas não vendem proposta avulsa — vendem
  **plano** (Workana R$ 19,90–99,90/mês; 99Freelas R$ 43,90–89,90/mês); Freelancer.com plano a
  partir de US$ 4,99/mês. Como o Whis nunca gasta, o **teto por corrida é a cota grátis**: ~2–7
  propostas/semana na Workana, 10/mês na 99Freelas, 10 Connects/mês no Upwork (1–2 propostas), 6/mês
  no Freelancer.com. **Cada conexão gasta numa aposta é uma a menos para uma chance boa** — reforça
  a regra dele.
- **Taxa sobre o ganho (perfil novo, plano grátis):** Workana 20 % (cai com o mesmo cliente),
  99Freelas 20 %, Upwork 0–15 % variável, Freelancer.com 10 % (mín. US$ 5), Fiverr 20 % **[P]**.
- **Preço de mercado:** referências brasileiras dão landing page de freelancer **R$ 500–2.500**,
  institucional **R$ 1.500–6.000**, e-commerce em plataforma pronta **R$ 2.000–9.000**; no Upwork o
  orçamento fixo mediano (todas as categorias) é **US$ 100** e o médio **US$ 587**. **Recomendação
  [I]:** o Whis não deve usar tabela fixa — deve **medir a mediana dos orçamentos que ele mesmo lê**
  por site e por tipo de trabalho, e chamar de "abaixo do mercado" o que fica abaixo dela.
- **Criar conta:** Workana tem **moderação de perfil com cota semanal por categoria** (perfil novo
  pode ser recusado ou ficar meses em análise); Upwork revisa o perfil e pode pedir **documento +
  videochamada**; Fiverr pede verificação de identidade a vendedor novo; o login da 99Freelas tem
  **Cloudflare Turnstile** (CAPTCHA). Pela posição já aceita no ticket 06, CAPTCHA, documento e
  selfie/vídeo são **dele** — a criação de conta será semiautomática.
- **Golpe:** os sinais que mais aparecem são **tirar a conversa da plataforma** (WhatsApp/Telegram),
  **pagar fora do escrow**, **cliente sem pagamento verificado e sem histórico**, **pedir dinheiro ao
  freelancer** (taxa, software, "kit"), **teste grande de graça**, e — o mais perigoso para dev —
  **"baixe e rode este repositório/arquivo"**, que é vetor de malware. Lista completa em
  [Sinais de golpe](#sinais-de-golpe).

## Tabela comparativa

| Site | Custo por proposta | Grátis e sem limite? | Como o Whis lê | O que a conta pede | Termos sobre automação |
|---|---|---|---|---|---|
| **Workana** | Conexão (1 por contato, até pergunta). Grátis: poucas por semana (2–7 conforme fonte/nível), renova toda segunda, não acumula. Planos Plus R$ 19,90 (+5/sem), Profissional R$ 69,90 (+15/sem), Premium R$ 99,90 (+50/sem). Taxa 20 % → 10 % → 5 % com o mesmo cliente. | **Não** (limite semanal) | Listagem pública **sem login**: JSON embutido na página (`budget`, `publishedDate`, `totalBids`, `skills`). Sem API, sem RSS. | E-mail/Google; **moderação de perfil** até 5 dias úteis, **cota semanal de aprovações por categoria** | ToS proíbe scripts de *scraping/data mining* e acesso por "meios automatizados" **[F]** |
| **99Freelas** | Conexão (pergunta ou proposta). Grátis: **10/mês** (renova dia 7). Pro R$ 43,90–49,90 (120/mês, taxa 15 %), Premium R$ 79,90–89,90 (240/mês, taxa 10 %). Grátis paga 20 %. Projeto novo fica **24 h só para assinante**. | **Não** (10/mês) | Listagem pública **sem login** (`/projects?categoria=…`): título, nível, publicado, tempo restante, **propostas**, **interessados**, habilidades. Sem API, sem RSS. | E-mail; login com **Cloudflare Turnstile** | Termos não citados nesta pesquisa; bots de terceiros avisam risco de banimento **[F]** |
| **Upwork** | Connects: **US$ 0,15** cada; **4–16 por proposta** conforme o job; Basic ganha **10/mês**; Freelancer Plus **US$ 19,99/mês** (100/mês). Taxa **0–15 %** variável desde mai/2025. | **Não** (pago) | **MCP oficial** (`mcp.upwork.com/mcp`, OAuth) — jobs, rascunho e envio com confirmação. API GraphQL exige US$ 25 mil + JSS 90 %. RSS **extinto** em 20/08/2024. | E-mail, perfil revisado (pode recusar), verificação de identidade (documento, às vezes videochamada) | Bots/scrapers sem chave de API → aviso, restrição ou bloqueio permanente **[F]** |
| **Freelancer.com** | Lance (bid). Grátis: **6/mês**. Planos US$ 4,99 (50), 9,99 (100), 49 (300), 99 (1.500). Taxa **10 % ou US$ 5** (o maior). | **Não** (6/mês) | **API oficial** (OAuth; busca de projetos e até `place bid`). Site em português: freelancer.com.br. | E-mail; telefone de segurança; **KYC** (documento, comprovante de endereço, foto com código) quando pedido | Não confirmado nesta pesquisa |
| **Fiverr** | Não há proposta: o vendedor publica *gigs* e o cliente compra. Taxa 20 % **[P]**. | n/a (modelo gig) | Não se "caça" — só vitrine | Verificação de identidade de vendedor novo **[F]** | Não confirmado |
| **GetNinjas** | Paga **moedas** para liberar o contato de cada pedido **[P]** | **Não** (pago) **[P]** | Só logado, app **[P]** | Cadastro de profissional **[P]** | Não confirmado |
| **Contra** | Sem comissão para o freelancer; aplicar a oportunidades **parece** grátis **[P]** | **Talvez** — conferir **[P]** | Logado **[P]** | E-mail/Google **[P]** | Não confirmado |
| **Crowd** (crowd.br.com) | Plataforma brasileira com curadoria; candidatura a job **parece** grátis **[P]** | **Talvez** — conferir **[P]** | Logado **[P]** | Cadastro + curadoria **[P]** | Não confirmado |
| **PeoplePerHour** | Créditos de proposta, cota grátis mensal pequena **[P]** | **Não** **[P]** | Listagem pública **[P]** | Perfil aprovado pela equipe **[P]** | Não confirmado |
| **Guru** | Lances (bids) mensais limitados no grátis **[P]** | **Não** **[P]** | Listagem pública **[P]** | E-mail **[P]** | Não confirmado |
| **Toptal / Codeable / Malt** | — | — | — | Triagem pesada (Toptal, Codeable) ou restrição geográfica (Malt) **[P]** | — |

## Tabela de preço de mercado

Nenhuma fonte desta pesquisa dá preço **por site** para os seis tipos de trabalho; o que há são
referências do mercado brasileiro e estatísticas gerais do Upwork. Câmbio de referência ~R$ 5,4/US$
**[I]**.

| Trabalho | Mercado BR (freelancer) | Internacional / Upwork | Fonte e grau |
|---|---|---|---|
| Landing page | **R$ 500–1.500** (faixa básica, template customizado); one page **R$ 900–2.500** | Freelancer: **US$ 800–2.500** | [F] [intentmarketing](https://www.intentmarketing.com.br/blog/post-quanto-custa-landing-page), [htmly](https://htmly.com.br/blog/quanto-custa-landing-page), [projectcostestimator](https://projectcostestimator.com/blog/landing-page-pricing-guide-2026) |
| Site institucional (5–10 páginas) | **R$ 1.500–6.000** | Site de pequena empresa por freelancer: **US$ 2.500–7.000** | [F] mesmas fontes; [projectcostestimator — índice 2026](https://projectcostestimator.com/blog/web-project-cost-index-2026) |
| E-commerce simples (plataforma pronta) | **R$ 2.000–9.000** (montagem) | — | [F] [freelancer.com.br — quanto custa um site](https://freelancer.com.br/blog/quanto-custa-fazer-um-site-em) |
| Sistema web / CRUD | Sem fonte. Estimativa: acima do institucional, **R$ 3.000–15.000** conforme escopo | — | **[I]** |
| Ajuste em WordPress | Sem fonte. Estimativa: **R$ 100–500** por ajuste | Upwork, todas as categorias: **mediana US$ 100**, média US$ 587 (jul/2026) | [F] [snipework — orçamento médio no Upwork](https://snipework.com/answers/average-upwork-project-budget); faixa BR **[I]** |
| Bug fix | Sem fonte. Estimativa: **R$ 100–400** | idem | **[I]** |

**Observações:**

- **Em site de leilão o preço é mais baixo que a tabela.** Relatos de dev brasileiro: na
  Workana e na 99Freelas *"as pessoas tendem a dar lances baixos, criando um efeito dominó que
  desvaloriza o serviço"* — [F] [TabNews](https://www.tabnews.com.br/evandrodias11/5-sites-para-comecar-a-fazer-freela-como-programador).
  **[I]** A faixa de agência/blog acima é **teto**, não referência, para Workana/99Freelas.
- **Formato do orçamento por site:** a Workana mostra **faixa** (ex.: `USD 50 - 100`, também em
  BRL) — [F] estrutura mapeada em 26/09/2026 em [radar-freelas](https://github.com/b4rao-dg/radar-freelas)
  (o exemplo do teste é inventado; o formato é real). A 99Freelas mostra o orçamento na página do
  projeto, muitas vezes "Aberto" **[P]**. O Upwork traz valor fixo ou faixa por hora **[P]**.
- **Recomendação [I]:** a caçada calcula o mercado com os próprios dados — mediana do orçamento
  por (site, tipo de trabalho) nas últimas corridas — e o grava junto do relatório. "Abaixo do
  mercado" (rápido com IA) = abaixo da mediana; "ligeiramente abaixo" (maior) = entre 70 % e 100 %
  dela. Na primeira corrida, sem histórico, usa a tabela acima como semente.

## Workana

**Custo por proposta.**

- [F] Cada **conexão** é qualquer contato novo com cliente — *"se você enviar apenas um 'olá' já
  descontará de suas conexões semanais"*; renovam **toda segunda-feira** e **não acumulam** —
  [comunidade Workana](https://community.workana.com/community//3606137/Como-funciona-e-o-que-%C3%A9-essas-conex%C3%B5es-extras-Quando-%C3%A9-renovado),
  [Conexões](https://community.workana.com/community//3101921/Conex%C3%B5es).
- [F] Plano grátis: as fontes divergem — **2 por semana** ([TabNews](https://www.tabnews.com.br/megbr/febd042e-6311-41d7-b71b-b94410ea208e),
  [idinheiro](https://www.idinheiro.com.br/ganhar-dinheiro/workana/)), **6 ao se cadastrar**, subindo
  com o nível ([blog Workana](https://blog.workana.com/en/freelancing/freelancer-benefit-plans-how-do-i-benefit-from-them/)),
  **7 por semana** no nível Iniciante (comunidade). **[I]** Conte com 2–7 por semana.
- [F] Planos: **Plus R$ 19,90** (+5 conexões/semana), **Profissional R$ 69,90** (+15),
  **Premium R$ 99,90** (+50), com desconto no plano longo; *Starter Pack* dá 3 meses de Plus ou
  Premium a freelancer novo — [Membership plans](https://www.workana.com/en/plans),
  [comunidade: Plus](https://community.workana.com/community//3726902/Qual-diferen%C3%A7a-do-plano-starter-com-o-outro-que-20-por-m%C3%AAs).
- [F] Taxa sobre o ganho: **20 %** no início da relação com cada cliente, **10 %** depois de
  US$ 300 pagos por ele, **5 %** depois de US$ 3.000 — [Mobills](https://www.mobills.com.br/blog/ganhar-dinheiro/workana-vale-a-pena/).
  Outra fonte dá os degraus em US$ 500 e US$ 10.000 — [Contabilidade Zen](https://www.contabilidadezen.com.br/blog/workana-freelancer-brasileiro-impostos-2026/).
  **Conferir na tela.**
- **Grátis e sem limite? Não.**

**Como o Whis lê.**

- [F] A listagem `https://www.workana.com/jobs?category={categoria}&language=pt&page={n}` é
  pública e traz os projetos como **JSON no atributo `:results-initials`** da tag `<search>`, com
  `slug`, `title`, `description`, `budget`, `publishedDate`, `totalBids` (nº de propostas) e
  `skills` — código de [radar-freelas](https://github.com/b4rao-dg/radar-freelas) (`buscador.py`,
  estrutura mapeada em 26/09/2026). As páginas de projeto (`/job/<slug>`) também são públicas.
- [F] Não há API pública nem RSS oficial; o que existe são scrapers de terceiros (Apify) que extraem
  orçamento, habilidades, **país do cliente** e **nº de propostas** — [Apify](https://apify.com/automation-lab/workana-freelance-projects-scraper.md).
- [P] Avaliação e pagamento verificado do cliente aparecem na página do projeto.
- **[I]** Ler sem login não arrisca a conta dele, mas contraria os termos (abaixo). Risco real:
  bloqueio de IP. Volume baixo e intervalo humano mitigam.

**Criar conta.**

- [F] O perfil passa por **moderação** (padrão **até 5 dias úteis**) e a Workana *"define uma
  quantidade limitada de perfis que podem ser aprovados em cada área de atuação"* por semana,
  comparando experiência, **portfólio** e demanda — [FAQ no Reclame Aqui](https://www.reclameaqui.com.br/empresa/workana/faq/por-que-meu-perfil-de-freelancer-est-em-moderao-e-quanto-tempo-leva-para-ser-aprovado_Pnw7XuV3SLB7RyE7/).
- [F] Há reclamações de perfil **recusado sem justificativa** com **reavaliação paga** oferecida, e
  de análise parada há meses — [Reclame Aqui](https://www.reclameaqui.com.br/workana/workana-reprova-perfil-sem-justificativa-e-oferece-servico-pago-para-reavaliacao_ltId9leloknlR0Bp/),
  [outra](https://www.reclameaqui.com.br/workana/perfil-em-analise-ha-mais-de-1-ano-sem-solucao_Lrz96mElTg6zd6MT/).
- **[I]** Para perfil novo de web dev, a aprovação depende de **portfólio** — a amostra do
  ticket 09 serve também aqui. A reavaliação paga é gasto: o Whis não contrata.

**Termos.** [F] Proíbe *"programs or scripts for the purpose of scraping, indexing, surveying, or
otherwise data mining"* e acesso por *"any automated, unethical or unconventional means"*; penalidade
mínima de **suspensão de 15 dias**, e encerramento imediato nas graves — [Terms](https://www.workana.com/pages/view/terms),
[Policies](https://help.workana.com/hc/en-us/articles/360040841214-Workana-Policies). **[I]** Enviar
proposta por robô é a parte mais visível disso; mais um motivo para "preparar, não enviar".

**Golpe.** [F] Conselhos de quem usa: preferir cliente **com ao menos uma avaliação**, olhar quantos
projetos ele publicou e **pagou**, **não sair do chat da Workana** — [TabNews](https://www.tabnews.com.br/AlessandroIvos/16bff419-e5ac-43a9-81e7-9cacca0f38e2).

## 99Freelas

**Custo por proposta.**

- [F] Plano **Básico grátis: 10 conexões/mês**, renovadas **todo dia 7**; uma pergunta ao cliente
  também gasta conexão; o número gasto por proposta aparece antes de enviar e **varia com a
  categoria** — [O que são conexões?](https://99freelas.zendesk.com/hc/pt-br/articles/4410951411223-O-que-s%C3%A3o-conex%C3%B5es),
  [Planos](https://99freelas.zendesk.com/hc/pt-br/articles/1500008543262-Planos-de-freelancers).
- [F] **Pro**: 120 conexões/mês, taxa 15 %; **Premium**: 240/mês, taxa 10 %, 5 propostas
  promovidas/mês. Preço diverge entre fontes: Pro **R$ 43,90–49,90**, Premium **R$ 79,90–89,90**
  por mês — [Planos (Zendesk)](https://99freelas.zendesk.com/hc/pt-br/articles/1500008543262-Planos-de-freelancers),
  [idinheiro](https://www.idinheiro.com.br/ganhar-dinheiro/99freelas/), [blog 99Freelas](https://blog.99freelas.com.br/free-pro-ou-premium-qual-plano-escolher/).
- [F] Básico paga **20 %** de intermediação e recebe em 10 dias úteis.
- [F] **Projeto novo fica 24 horas exclusivo para assinantes**; depois, qualquer um com conexão
  pode propor — [Sou do plano gratuito e não consigo enviar proposta](https://99freelas.zendesk.com/hc/pt-br/articles/360012176014-Sou-profissional-do-plano-gratuito-e-n%C3%A3o-consigo-enviar-proposta-Como-fa%C3%A7o).
  **[I]** Para o plano grátis, o projeto chega com um dia de concorrência na frente — a caçada deve
  priorizar os que estão perto de abrir e com poucas propostas.
- **Grátis e sem limite? Não.**

**Como o Whis lê.**

- [F] Listagem pública `https://www.99freelas.com.br/projects?categoria={categoria}&page={n}`, sem
  login, em HTML: cada `li.result-item` traz título, link, **nível** (Iniciante/…), **publicado**,
  **tempo restante**, **propostas**, **interessados**, descrição e habilidades —
  [radar-freelas](https://github.com/b4rao-dg/radar-freelas) (mapeado em 26/09/2026).
- [F] Um bot de terceiros também lê **orçamento** e **avaliação do cliente** na página do projeto —
  [99freelas-bot](https://github.com/pedroforadori/99freelas-bot).
- [F] Sem API pública nem RSS; há endpoints internos (`/services/...`) usados por scripts de
  terceiros — [99freelas-script](https://github.com/TON1COLO/99freelas-script).

**Criar conta.** [F] Dá para cadastrar e propor logo no plano grátis — [TabNews](https://www.tabnews.com.br/evandrodias11/5-sites-para-comecar-a-fazer-freela-como-programador).
[F] O formulário de login usa **Cloudflare Turnstile**, que barra login automatizado; os bots
existentes importam os cookies do navegador da pessoa — [99freelas-bot](https://github.com/pedroforadori/99freelas-bot).
**[I]** Mesmo modelo do X no jornal (ADR 0003): sessão do navegador logado dele.

**Termos.** [F] Autores de bots registram que *"automação pode violar os termos; risco de ban é do
usuário"* e que perfis com comportamento fora do esperado podem ser rebaixados —
[99freelas-script](https://github.com/TON1COLO/99freelas-script), [99freelas-bot](https://github.com/pedroforadori/99freelas-bot).
Os [termos oficiais](https://www.99freelas.com.br/termos) não puderam ser lidos nesta sessão — conferir.

**Reputação.** [F] Nota 7,7/10 no Reclame Aqui; queixas comuns são reembolso e cobrança —
[idinheiro](https://www.idinheiro.com.br/ganhar-dinheiro/99freelas/).

## Upwork

**Custo por proposta.**

- [F] **US$ 0,15 por Connect** (mínimo 10 por US$ 1,50); **Basic: 10 Connects grátis/mês**;
  proposta custa **4 a 16 Connects** conforme escopo, orçamento e demanda do job —
  [Upwork: Is Upwork free?](https://www.upwork.com/resources/is-upwork-free),
  [aiproposer](https://aiproposer.com/learn/upwork-connects-explained),
  [jobbers](https://www.jobbers.io/what-are-upwork-connects-and-how-much-do-they-cost/).
  **[I]** = US$ 0,60–2,40 (R$ 3–13) por proposta; o grátis dá **1–2 propostas por mês**.
- [F] **Freelancer Plus US$ 19,99/mês** com **100 Connects/mês** (algumas fontes dizem 60) —
  [Upwork: Freelancer Plus](https://www.upwork.com/resources/freelancer-plus-guide),
  [Release notes](https://community.upwork.com/t5/Product-Release-Notes/Freelancer-Plus-rate-change-and-new-perks/ba-p/1526780).
- [F] Taxa de serviço **variável de 0 a 15 %**, mostrada antes de enviar a proposta e fixa pelo
  contrato, desde maio de 2025 — [freelancercalculator](https://freelancercalculator.com/upwork-service-fee-2026-official-guide/),
  [golance](https://golance.com/blogs/upwork-fees-explained-2026).
- [F] Lances extras ("boost") compram posição com mais Connects.
- **Grátis e sem limite? Não.**

**Como o Whis lê.**

- **RSS: morto.** [F] Desligado em **20/08/2024**; as URLs dão 404. O substituto oficial são
  buscas salvas e notificações do app — [Upwork: RSS deprecation](https://support.upwork.com/hc/en-us/articles/52052528243731-RSS-deprecation),
  [gigradar](https://gigradar.io/blog/upwork-rss-feed).
- **API GraphQL: fora de alcance.** [F] Escopos para busca: *Common Entities – Read-Only Access* e
  *Read marketplace Job Postings* — [tryAGI/Upwork](https://github.com/tryAGI/Upwork). Para receber
  chave, a conta precisa de nome, endereço, foto, **meio de pagamento verificado**, **identidade
  verificada**, **≥ US$ 25.000 em ganhos/gastos na vida**, **JSS ≥ 90 %**, conta sem suspensão, e
  um pedido justificando o uso (limite 40 mil chamadas/dia); a chave nasce "Disabled" e espera
  aprovação — [Upwork: Request an API key](https://support.upwork.com/hc/en-us/articles/115015857647-How-to-request-an-API-key-from-Upwork),
  [GigRadar](https://help.gigradar.io/en/articles/12518739-what-are-the-criteria-for-getting-an-upwork-api-key).
  [F] A API não tem mutação para enviar proposta — [tryvibeworker](https://tryvibeworker.com/blog/upwork-api-access-2026).
- **MCP oficial: o caminho.** [F] Em **10/08/2026** o Upwork lançou o **Upwork MCP Server**,
  *"o único conector oficial para agentes de IA"*, hospedado em `https://mcp.upwork.com/mcp`, com
  **OAuth 2.1** (permissões revogáveis em *Connected Apps*). Expõe perfil, **descoberta de jobs**,
  **propostas**, mensagens, ofertas e contratos; sem custo extra, mas **Connects e taxas valem**;
  ações de escrita (inclusive **enviar proposta**) são rascunhadas e **pedem confirmação**, e as
  financeiras (aceitar contrato etc.) **só concluem em upwork.com**. Tem instrução de instalação para
  Claude Code: `claude mcp add --transport http upwork https://mcp.upwork.com/mcp` —
  [GlobeNewswire](https://www.globenewswire.com/news-release/2026/08/10/3342153/0/en/upwork-talent-is-now-everywhere-ai-works.html),
  [Upwork MCP](https://www.upwork.com/ai/mcp), [twixrsolutions](https://www.twixrsolutions.com/blog/upwork-mcp-server-guide),
  [up-bro](https://up-bro.com/blog/upwork-mcp-server).
  **[I]** Encaixa no Whis (Claude pelo Agent SDK, que fala MCP remoto). Falta conferir à mão: quais
  campos a busca devolve (orçamento, nº de propostas, país/gasto/avaliação do cliente), limites de
  uso, e se conta nova sem histórico tem acesso.
- [P] Página de job do Upwork mostra orçamento, tipo (fixo/hora), nível, nº de propostas
  ("Proposals: 20 to 50"), país, gasto total, taxa de contratação e **pagamento verificado** do
  cliente — os melhores campos de qualidade entre todos os sites.

**Criar conta.**

- [F] Identidade: documento oficial com foto e/ou **verificação visual por videochamada** (menos de
  5 min); enquanto pendente, a conta fica em espera e **não envia proposta**; prazo de 7 dias —
  [Upwork Community](https://community.upwork.com/t5/Support-Forum/Identity-Verification/td-p/1538922/page/57),
  [support](https://support.upwork.com/hc/en-us/articles/360001176427).
- [F] O perfil é **revisado** e pode **não ser aprovado** (motivos citados: perfil incompleto, foto
  ruim, categoria saturada) — [websitebuilderinsider](https://www.websitebuilderinsider.com/why-is-my-profile-not-approved-on-upwork/),
  [Upwork Community](https://community.upwork.com/t5/New-to-Upwork/How-can-I-know-that-my-profile-is-approved/td-p/199786/page/67).
  (Números como "98 % recusados" circulam sem fonte primária — ignorar.)
- **[I]** Videochamada é **dele**, sem discussão. Criar conta no Upwork é entrega 2; a entrega 1 só
  usa o Upwork se ele já tiver conta ou a criar à mão.

**Termos.** [F] A User Agreement proíbe *"robots, spiders, scrapers, or other automated means to
access the Site"* sem permissão escrita; o artigo *Use bots and other automation properly* define bot
como qualquer script/extensão/serviço que **age mais rápido ou com mais frequência que um humano**,
manda pedir **chave de API**, e diz que **mesmo com chave** é proibido *"spamming proposals"* e
raspar dados; a punição vai de aviso a **bloqueio permanente** — [Upwork support](https://support.upwork.com/hc/en-us/articles/43342677368467-Use-bots-and-other-automation-properly),
[UpHunt](https://uphunt.io/blog/can-you-get-banned-for-scraping-upwork-2026).
[F] Relatos de aumento de suspensões por automação em 2025 — [gigradar](https://gigradar.io/blog/upwork-auto-bidding-bot).
**[I]** Navegador automatizado no Upwork é o maior risco de conta desta lista; o MCP oficial o
elimina.

**Formato.** Lembrete do ticket 06: **por hora fica fora** — o Upwork registra o tempo com prints de
tela. A caçada filtra só *fixed-price* (e contínuo pequeno com valor mensal).

## Freelancer.com

- **Custo.** [F] Grátis: **6 lances/mês**. Planos: Basic **US$ 4,99** (50 lances), Plus **US$ 9,99**
  (100), Professional **US$ 49** (300), Premier **US$ 99** (1.500); anual até 20 % mais barato.
  Taxa: **10 % ou US$ 5**, o que for maior, cobrada **ao aceitar** o projeto fixo —
  [Fees and charges](https://www.freelancer.com/feesandcharges), [Membership](https://www.freelancer.com/membership/),
  [hireinsouth](https://www.hireinsouth.com/post/freelancer-pricing), [jobbers](https://www.jobbers.io/freelancer-com-vs-jobbers-io-vs-peopleperhour-vs-guru-complete-2026-matrix/).
  [P] Lance destacado/selado é pago à parte. **Grátis e sem limite? Não.**
- **Leitura.** [F] **API oficial** com OAuth2 (cabeçalho `freelancer-oauth-v1`), busca de projetos
  ativos por habilidade e **colocação de lance** (`project_id`, `amount`, `period`, `description`) —
  [developers.freelancer.com](https://developers.freelancer.com), [rollout](https://rollout.com/integration-guides/freelancer/api-essentials).
  [P] Criar o app é self-service; conferir se há aprovação. **[I]** É o único site da lista em que
  ler **e** enviar têm via oficial — mas os 6 lances/mês tiram o envio da autonomia.
- **Conta.** [F] Telefone de segurança e programa **KYC** (documento, comprovante de endereço e foto
  segurando um código) — [KYC](https://www.freelancer.com.ar/support/profile/what-is-the-know-your-customer-program-1793),
  [requisitos](https://www.freelancer.hk/support/Profile/what-is-required-to-become-verified).
- **Termos.** Conta é pessoal e o titular responde por tudo que ela faz — [Terms](https://www.freelancer.com/about/terms).
  Cláusula sobre bots não confirmada.
- **[I] Relevância:** tem versão em português (freelancer.com.br) e cliente brasileiro, mas é o
  mercado mais disputado por lance baixo. Quarto lugar, opcional na entrega 1.

## Fiverr

- **Modelo.** [P] Marketplace de **gig**: o vendedor publica pacotes com preço e o comprador compra;
  não existe "mandar proposta" para projeto de cliente (os *Buyer Requests* deram lugar a *Briefs*
  que o Fiverr distribui a vendedores escolhidos). Taxa **20 %** sobre cada venda.
- **Conta.** [F] Vendedor novo passa por **verificação de identidade** — [Fiverr Help](https://help.fiverr.com/hc/en-us/articles/6348992414097),
  [PT](https://help.fiverr.com/hc/pt/articles/37555379217681-Verifica%C3%A7%C3%A3o-de-identidade-Prote%C3%A7%C3%A3o-e-uso-de-dados).
- **Golpe.** [F] Relato de dev brasileiro: *"Fiverr virou lugar para aplicar golpes"* — [TabNews](https://www.tabnews.com.br/TOMSENA97/fiverr-virou-lugar-para-aplicar-golpes).
- **Serve?** **[I]** Não para a caçada (não há o que caçar). Pode servir na **entrega 2** como
  vitrine passiva: um gig "landing page com entrega rápida" que vende enquanto ele dorme, com o
  Whis só redigindo o gig. Fica fora da entrega 1.

## GetNinjas

- **[P]** Marketplace brasileiro de serviços (de encanador a site): o cliente descreve o pedido e o
  profissional **paga em moedas** para liberar o contato; não há proposta grátis. Público:
  pequeno negócio local, orçamento baixo, muitas vezes por telefone/WhatsApp.
- **Grátis e sem limite? Não [P].** Leitura só logado/app [P].
- **[I]** Fora da entrega 1. Pode valer depois para "site institucional de pequena empresa da
  região", que casa com o perfil dele — mas cada contato custa dinheiro, então nunca sai sozinho.

## Contra

- **[P]** Plataforma americana de freelancer independente, **sem comissão para o freelancer**
  (receita vem de assinatura *Pro* opcional e do cliente); perfil-portfólio e quadro de
  oportunidades. Forte em design, no-code e front-end; cliente majoritariamente dos EUA.
- **Grátis e sem limite? Talvez [P]** — é o candidato mais provável a passar na regra dele. Conferir
  à mão se candidatar tem cota.
- **[I]** Volume para web dev brasileiro é incerto e o inglês é obrigatório. Candidato a teste na
  entrega 2, não na 1.

## Crowd

- [F] Plataforma brasileira que se compara à 99Freelas para "jobs remotos" — [blog Crowd](https://blog.crowd.br.com/99freelas-ou-crowd-para-freelancers/).
- **[P]** Modelo de **curadoria** (a Crowd seleciona e oferece o job a freelancers aprovados),
  candidatura sem custo, forte em agências de marketing (design, social, web).
- **Grátis e sem limite? Talvez [P].** **[I]** Vale abrir conta à mão para ver o volume de web;
  fora da entrega 1.

## PeoplePerHour e Guru

- **[P]** PeoplePerHour (Reino Unido): proposta gasta **créditos**, com cota grátis mensal pequena e
  compra de extras; perfil novo passa por aprovação da equipe. Guru: lances mensais limitados no
  plano grátis, planos pagos dão mais.
- [F] Ambos aparecem nas comparações de 2026 ao lado do Freelancer.com — [jobbers](https://www.jobbers.io/freelancer-com-vs-jobbers-io-vs-peopleperhour-vs-guru-complete-2026-matrix/).
- **[I]** Limitam ou cobram (não passam na regra) e têm pouco cliente que contrate brasileiro em
  português. **Descartados** para a entrega 1.

## Toptal, Codeable, Malt — descartados

- **Toptal** [P]: triagem em várias etapas (idioma, algoritmo, projeto ao vivo), aceita uma fração
  pequena dos candidatos; contrato quase sempre **por hora** ou tempo integral. Perfil novo e por
  hora fora → descartado.
- **Codeable** [P]: só WordPress, com triagem rigorosa de experiência comprovada. Descartado agora;
  pode voltar se ele acumular trabalhos em WordPress.
- **Malt** [P]: mercado europeu (França, Alemanha, Espanha…), voltado a freelancer residente lá.
  Descartado.

## Sinais de golpe

Lista para o Whis "sair fora" (ticket 06, Q9). Vale para todos os sites. Fontes: [Freelancer.com:
10 red flags](https://www.freelancer.in/community/articles/freelancer-scams-10-red-flags-and-warning-signs),
[Sumsub](https://sumsub.com/blog/the-hidden-cost-of-opportunity-how-to-spot-scams-in-the-freelance-marketplace),
[TabNews — Workana](https://www.tabnews.com.br/AlessandroIvos/16bff419-e5ac-43a9-81e7-9cacca0f38e2),
[TabNews — Fiverr](https://www.tabnews.com.br/TOMSENA97/fiverr-virou-lugar-para-aplicar-golpes),
[smartcustomer](https://www.smartcustomer.com/faq/freelancer.com/do-i-need-to-pay-to-get-the-employers-software-and-stuff-to-do-the-job-1).

**Descarte direto (o Whis não envia nem prepara):**

1. **Pede dinheiro ao freelancer** — taxa de cadastro, "kit", software, equipamento, teste pago,
   "taxa de liberação" do pagamento. Cliente de verdade não cobra de quem vai contratar. [F]
2. **Pede para sair da plataforma antes do contrato** — WhatsApp, Telegram, Skype, e-mail pessoal —
   *"onde é difícil provar qualquer coisa depois"*. Sair do chat também quebra o escrow e, em geral,
   os termos do site. [F]
3. **Pagamento fora do escrow** ou por meio sem proteção (Skrill, cripto, cheque, "pago por fora
   com desconto na taxa"), sobretudo com **urgência** ("tem que ser agora"). [F]
4. **"Baixe e rode este repositório/arquivo"** — projeto que chega como `.zip`, link de Drive ou
   repositório para clonar e executar (`npm install`, "rode o teste técnico") é vetor conhecido de
   malware contra desenvolvedores (campanhas de "entrevista/teste técnico" falso). [P] **[I]** Regra
   da spec: o Whis **nunca executa** código ou arquivo vindo do cliente, e marca o projeto como
   suspeito.
5. **Pede documento, dados bancários, código SMS ou login antes de haver contrato** — ou pede para
   ele **criar/verificar conta em nome de outro** (aluguel de conta). [F]/[P]
6. **Texto com ordem ao leitor** ("ignore as instruções", "responda com seu e-mail e CPF") —
   *prompt injection*; o texto da vaga é dado, não ordem (ticket 06). [I]

**Sinais de risco (o Whis rebaixa e anota no relatório):**

7. Cliente **sem pagamento verificado**, conta criada há poucos dias, **zero projetos pagos** ou
   avaliação ruim. [F]
8. **Preço fora da curva** — muito acima da mediana para trabalho trivial (isca) ou "teste grátis"
   que é o projeto inteiro (trabalho de graça). [F]/[I]
9. Descrição vaga, genérica, copiada em vários projetos, ou que não bate com o título. [P]
10. Links encurtados ou para domínio que imita o site (phishing de login). [P]
11. Pede para **refazer de graça** sem escopo fechado, ou para começar antes de depositar a
    garantia ("Aguardando garantia" na Workana). [I]

## A conferir à mão (antes da spec)

- Cota grátis real da Workana para perfil novo (2, 6 ou 7) e se perfil **não aprovado** consegue ler
  e propor.
- Se o plano grátis da 99Freelas mostra o botão de proposta depois das 24 h (um README de terceiro
  diz que não, sem Premium; a ajuda oficial diz que sim).
- Upwork MCP: campos da busca de jobs, limites, e se conta nova sem histórico tem acesso.
- Contra e Crowd: candidatura é **grátis e sem limite**? Se sim, são os únicos lugares em que o Whis
  poderia enviar sozinho.
- Termos da 99Freelas e do Freelancer.com sobre automação.
- Taxa do Fiverr e regra atual dos *Briefs*.
