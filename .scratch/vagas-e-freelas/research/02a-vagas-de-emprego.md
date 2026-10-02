# Research 02a — Vagas de emprego

Levantado em 2026-10-02.

Ticket: [02 — Onde as vagas e os freelas estão](../issues/02-onde-as-vagas-estao.md). Esta é a
metade **emprego**; freela está em outro research. O LinkedIn aparece aqui só como fonte de vaga —
o detalhe é do [ticket 08](../issues/08-o-linkedin.md).

**Isto é levantamento, não decisão.** Perfil usado para julgar relevância (tickets 01 e 06): web
developer full-stack; games e software de áudio como *tentar a sorte*; qualquer regime (CLT, PJ,
contrato em USD/EUR); remoto, ou presencial/híbrido só em Ribeirão Preto (~R$ 7 mil) ou São Paulo
(~R$ 8–9 mil); remoto e região de Araraquara com piso de R$ 5 mil/mês. Mora em Matão-SP.

**Como ler as marcas:**

- **[fato]** — afirmado por uma fonte, com link ao lado. Na maioria dos casos a fonte é
  **secundária** (resultado de busca, documentação de terceiros, páginas de scrapers no Apify):
  o contêiner desta pesquisa tem a rede de saída bloqueada para quase todos os sites de vaga
  (`remotive.com`, `himalayas.app`, `gupy.io`, `indeed.com`, `programathor.com.br`,
  `news.ycombinator.com`, `weworkremotely.com`… todos devolveram *egress blocked*). Só o
  **GitHub** foi lido em primeira mão.
- **[medido]** — lido em primeira mão hoje (só GitHub).
- **[inferência]** — leitura minha, sem fonte que a confirme. Precisa de camada 0 no PC dele antes
  de virar spec, como foi feito com o X ([ADR 0003](../../../docs/adr/0003-x-por-navegador.md)).

---

## Resumo

1. **O remoto internacional se lê de graça e sem navegador.** Himalayas, Remotive, RemoteOK, Jobicy,
   Working Nomads e o Hacker News (via Algolia) têm API JSON pública sem chave; o We Work Remotely
   tem RSS por categoria. Nenhum pede login para ler. As condições são de **atribuição e de não
   republicar** em outro quadro de vagas, o que não pesa para um relatório privado dele
   [inferência]. Remotive limita a **4 leituras por dia** e entrega com **24 h de atraso** [fato].
2. **O filtro que mais importa no remoto internacional é "aceita alguém no Brasil?"**, mais do que
   a stack. A maioria das vagas desses sites é só para os EUA ou para a Europa. Só Himalayas
   (`locationRestrictions`, por país), Remotive (`candidate_required_location`, texto livre) e
   Jobicy (`geo=latam`/`brazil`) trazem isso como campo [fato]. Nos outros (WWR, RemoteOK, HN), o
   Claude tem de ler a descrição [inferência].
3. **A faixa salarial é rara, e o piso dele depende dela.** Trazem faixa estruturada quando a
   empresa informa: Himalayas (`minSalary`/`maxSalary`), RemoteOK (`salary_min`/`salary_max` em
   USD), Get on Board (USD, muitas vezes obrigatória) e Jobicy [fato]. O Remotive traz texto livre;
   o RSS do WWR **não traz salário** [fato]. No Brasil, Gupy e LinkedIn quase nunca mostram faixa
   [inferência]. Consequência para a spec: **"sem faixa" não pode descartar a vaga**. Ela vai para
   o relatório como "faixa desconhecida". Vaga em USD acima de ~US$ 1 mil/mês já passa o piso de
   R$ 5 mil [inferência, câmbio ~R$ 5,5].
4. **No Brasil, a fonte-chave é a Gupy, e ela também é a candidatura.** É o ATS da maioria das
   empresas médias e grandes (~20 mil vagas/mês em todas as áreas) [fato]. O portal tem um JSON
   público (`portal.api.gupy.io/api/v1/jobs`), filtrável por termo, cidade, estado e
   `workplaceType` [fato, fonte secundária]. Esse JSON **não é documentado como API pública**: é o
   que o site usa [inferência]. Na candidatura, **uma conta Gupy serve para todas as empresas**. A
   conta pede CPF, e-mail, telefone e data de nascimento [fato]. É de graça e sem limite conhecido
   [inferência]. Cada empresa pode pôr perguntas e testes no meio do processo [fato].
5. **Os repositórios de vaga no GitHub** (`frontendbr/vagas`, `backend-br/vagas`) são pequenos
   (3 a 5 vagas novas por semana cada) [medido], mas têm etiquetas `Remoto`/`CLT`/`PJ`/`USD`/nível
   e são **perfeitamente legíveis pela API do GitHub**, que o Whis já sabe usar. É um bom
   complemento barato, com muita vaga em USD de consultorias de *nearshore*.
6. **Indeed (e o Glassdoor, que virou Indeed em 2026) e LinkedIn são as maiores, mas são as
   piores de ler.** Os termos do Indeed proíbem bots tanto na leitura quanto na candidatura, a API
   de busca dele morreu em 2023 e o site tem proteção anti-bot [fato]. O LinkedIn tem endpoint
   *guest* sem login, mas leva 429 depois de ~10 páginas [fato] (detalhe no ticket 08). Para a
   entrega 1, nenhum dos dois entra; se entrarem depois, é por navegador logado, com o risco da
   conta dele, como no X [inferência].
7. **Os sites de "rede de talentos"** (GeekHunter, Revelo, Strider, Turing, Toptal, Arc) **não são
   fonte de vaga para a caçada.** Neles o candidato monta perfil, passa por triagem (GeekHunter
   aprova ~5%, Strider pede inglês B1–B2 e 3 anos de experiência) e **a empresa chama** [fato].
   Valem como **perfis a criar uma vez**, na entrega 2, não como algo a varrer.
8. **Candidatura: quase todo o remoto internacional manda para fora**, para o ATS da empresa
   (Greenhouse, Lever, Ashby, Workable). Greenhouse e Lever não pedem conta, mas o Greenhouse usa
   **reCAPTCHA invisível** (às vezes Enterprise) [fato]. Pela regra do ticket 06, CAPTCHA é com ele.
   **Enviar *tentar a sorte* sozinho vai ser frágil nesses formulários** [inferência]. Mandar é de
   graça em todos os sites que entram. Os planos pagos (Remotive Accelerator US$ 79, Himalayas
   Plus US$ 9/mês, Catho R$ 89+) vendem **ver mais vagas ou ferramentas**, não o direito de se
   candidatar [fato].
9. **Generalistas brasileiros (Catho, Vagas.com, InfoJobs, Sólides, BNE) ficam de fora.** Têm muita
   vaga, mas pouca de web dev remoto acima do piso [inferência], termos que proíbem robôs [fato
   para Indeed e Catho; inferência para os outros] e nenhuma leitura estruturada.
10. **Recomendação para a entrega 1** (ler e preparar, sem enviar):
    - **Entram (leitura sem login, R$ 0):** Himalayas, Remotive, We Work Remotely (RSS),
      RemoteOK, Jobicy, Gupy (JSON do portal) e os repositórios `frontendbr/vagas` e
      `backend-br/vagas` (API do GitHub).
    - **Entram se a camada 0 passar:** Programathor (página pública, Playwright), Get on Board
      (API pública, faixa em USD) e o *Who is hiring* do HN (uma vez por mês, pouco volume para
      brasileiro).
    - **Ficam de fora da 1:** LinkedIn (ticket 08), Indeed/Glassdoor, Wellfound (DataDome),
      generalistas brasileiros e redes de talentos.
    - **Antes da spec:** uma camada 0 no PC dele, com uma leitura de cada fonte que entra,
      contando quantas vagas web aceitam Brasil e quantas trazem faixa. Os volumes abaixo são
      estimativa.

---

## Tabela comparativa

Legenda de leitura: **API** = JSON público sem chave · **RSS** · **PW** = página pública lida por
Playwright · **Logado** = só com conta. "Faixa" = mostra salário de forma estruturada.

| Fonte | Mercado | Leitura | Faixa | Aceita BR como campo? | Vagas web/dia que servem (estim.) | Candidatura | Conta pede | Custo p/ candidato | Automação nos termos | Entrega 1 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Himalayas** | Remoto intl | API (60 req/min) | Sim, quando há | Sim (`locationRestrictions`) | 5–20 [inf.] | Redireciona p/ ATS (`applyUrl`) | — | Grátis; Plus US$ 9/mês opcional | Leitura convidada | **Sim** |
| **Remotive** | Remoto intl | API (≤4/dia, 24 h atraso) | Texto livre | Texto (`candidate_required_location`) | 2–8 [inf.] | Redireciona | — | Grátis; Accelerator US$ 79 libera mais vagas | Atribuição; proíbe republicar | **Sim** |
| **We Work Remotely** | Remoto intl | RSS por categoria | Não (no RSS) | Texto (`region`) | 3–10 [inf.] | Redireciona | — | Grátis | Atribuição | **Sim** |
| **RemoteOK** | Remoto intl | API | Sim (USD), quando há | Texto (`location`) | 5–15 [inf.] | Redireciona (`apply_url`) | — | Grátis | Atribuição c/ link *follow* | **Sim** |
| **Jobicy** | Remoto intl | API + RSS | Sim, quando há | Sim (`geo=latam`/`brazil`) | 1–5 [inf.] | Redireciona | — | Grátis | Atribuição; proíbe republicar | **Sim** |
| **Working Nomads** | Remoto intl | API (`exposed_jobs`) | Não confirmado | Texto | 2–8 [inf.] | Redireciona | — | Grátis | Não achei | Talvez (redundante) |
| **HN Who is hiring** | Intl, mensal | API (Algolia/Firebase) | Às vezes, no texto | Texto | ~1/dia em média [inf.] | E-mail ou ATS | — | Grátis | API oficial | Talvez |
| **Get on Board** | LatAm tech | API pública | Sim (USD), frequente | Sim (país, remoto) | 1–5 [inf.] | No site | Conta Get on Board [inf.] | Grátis [inf.] | Não verificado | Talvez |
| **Gupy** | BR (todas as áreas) | JSON do portal (não documentado) | Raro [inf.] | Sim (`workplaceType`, cidade, UF) | 10–40 [inf.] | No site, conta única Gupy | CPF, e-mail, telefone, nascimento | Grátis | Termos preveem suspensão por mau uso; cláusula de bot não confirmada | **Sim (leitura)** |
| **frontendbr / backend-br (GitHub)** | BR, muita vaga USD | API do GitHub | Às vezes (etiqueta/texto) | Etiquetas `Remoto`/cidade | ~1 (somando) [medido] | E-mail, link ou ATS (no texto) | — | Grátis | API oficial | **Sim** |
| **Programathor** | BR, só dev | PW (página pública) [inf.] | Provável [inf.] | Filtro remoto [fato] | 3–10 [inf.] | No site | Conta Programathor | Grátis [fato] | Não verificado | Talvez |
| **Remotar** | BR, só remoto | PW [inf.] | Às vezes [inf.] | É só remoto | 2–8 [inf.] | Redireciona [inf.] | — | Não verificado | Não verificado | Depois |
| **Coodesh** | BR, dev | PW [inf.] | Às vezes [inf.] | Etiqueta remoto | 1–5 [inf.] | No site, com teste técnico | Conta Coodesh | Grátis [inf.] | Não verificado | Depois |
| **Indeed / Glassdoor** | BR + intl | Só navegador; anti-bot | Às vezes | Filtro | Centenas (bruto) | "Candidatura simplificada" ou ATS | E-mail, telefone (SMS) | Grátis | **Proíbe bots** | Não |
| **LinkedIn** | BR + intl | *Guest* sem login (429 ~10 págs) ou logado | Raro no BR | Filtro | Centenas (bruto) | Easy Apply ou ATS | — (ticket 08) | Grátis; Premium opcional | **Proíbe bots** | Não (ticket 08) |
| **Wellfound** | Startups intl | Logado; DataDome | Sim (salário e *equity*) | Filtro | 2–10 [inf.] | No site, um clique | Conta + perfil | Grátis | Anti-bot ativo | Não |
| **Catho / Vagas.com / InfoJobs / Sólides** | BR generalista | PW, anti-bot provável | Às vezes | Filtro | Pouco web acima do piso [inf.] | No site | CPF, telefone etc. | Grátis no básico; Catho R$ 89–360 | Catho e similares proíbem robôs | Não |
| **Trampos** | BR, comunicação + tech | PW [inf.] | Às vezes | Filtro | <2 [inf.] | No site | Conta | Grátis; premium opcional | Não verificado | Não |
| **GeekHunter / Revelo / Strider / Turing / Toptal / Arc** | Redes de talentos | Não é lista para varrer | A empresa propõe | — | — | A empresa chama | Perfil + triagem | Grátis | — | Não (perfil na entrega 2) |

---

## Remoto internacional

### Himalayas

- **Leitura** [fato]: API JSON pública, sem chave nem conta. `GET https://himalayas.app/jobs/api`
  (offset/limit, máx. 20 por página) e `.../jobs/api/search` com filtros por palavra, país,
  *worldwide*, senioridade, tipo de contrato, fuso, ordenação. Limite de 60 req/min. Afirma 100 mil+
  vagas ativas. Fontes: [himalayas.app/api](https://himalayas.app/api),
  [data dictionary](https://himalayas.app/docs/data-dictionary).
- **Campos** [fato]: título, resumo, empresa, `employmentType`, `locationRestrictions` (lista de
  países com código ISO), `timezoneRestriction`, `category`, `minSalary`/`maxSalary`/`salaryPeriod`,
  `publishedAt`, link de candidatura. **É a fonte mais bem estruturada para a pergunta "aceita
  Brasil?"**.
- **Volume** [inferência]: o total é grande, mas a fatia web que aceita Brasil (ou *worldwide*/LatAm)
  deve ficar em 5–20 por dia.
- **Candidatura** [fato/inferência]: o link leva ao ATS da empresa. Para se candidatar não é preciso
  assinatura ([Himalayas Plus](https://himalayas.app/docs/himalayas-plus): US$ 9/mês por
  currículo/carta com IA e alertas, opcional).
- **Termos**: a API é oferecida para uso público [fato]. Não achei proibição de uso pessoal
  [inferência].

### Remotive

- **Leitura** [fato]: `GET https://remotive.com/api/remote-jobs` com `category`
  (`software-dev`), `search`, `company_name`, `limit`. Campos: `id`, `url`, `title`, `company_name`,
  `category`, `job_type`, `publication_date`, `candidate_required_location`, `salary` (texto
  livre), `description`. Fonte: [README oficial](https://github.com/remotive-com/remote-jobs-api).
- **Limites e termos** [fato]: no máximo **4 chamadas por dia**; mais de 2 por minuto é
  bloqueado; as vagas chegam com **24 h de atraso** de propósito. É obrigatório citar o Remotive e
  linkar a URL original. É proibido enviar as vagas para outros quadros e usá-las para captar
  cadastros. Nada disso atrapalha uma leitura por corrida para um relatório privado [inferência].
- **Volume** [fato/inferência]: ~2 mil vagas ativas grátis em todas as áreas
  ([suporte](https://support.remotive.com/en/article/how-much-does-remotive-cost-10louvq/)). O
  [Accelerator](https://remotive.com/community) (US$ 79, pagamento único) libera dezenas de
  milhares a mais. **O Whis não paga** (ticket 06). Web que aceita Brasil: 2–8 por dia
  [inferência].
- **Candidatura**: redireciona ao ATS da empresa [inferência pelo campo `url`].

### We Work Remotely

- **Leitura** [fato]: RSS público por categoria, incluindo **Full-Stack**, **Front-End**,
  **Back-End** e *All Programming* (ex.:
  `https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss`). A única condição
  é atribuir o link ao WWR ([página dos feeds](https://weworkremotely.com/remote-job-rss-feed)).
- **Campos** [fato]: empresa e título, categoria, tipo, `region` (ex.: "Anywhere in the World"),
  skills, data e descrição. **O RSS não traz salário**
  ([fonte secundária](https://apify.com/bovi/weworkremotely-scraper)).
- **Volume** [fato]: 1.000+ vagas novas por mês em todas as categorias
  ([FAQ](https://Weworkremotely.Com/job-seeker-faq)). Programação deve ser 1/3 disso, umas 10 por
  dia, das quais talvez metade aceita fora dos EUA [inferência].
- **Candidatura e custo** [fato]: ver e se candidatar é grátis e não precisa de cadastro
  ([suporte](https://support.weworkremotely.com/do-i-have-to-pay-to-use-we-work-remotely)). O botão
  leva à página da empresa ou ao ATS.
- **Qualidade** [inferência]: a empresa paga caro para anunciar, então há menos lixo e menos
  agregação.

### RemoteOK

- **Leitura** [fato]: `GET https://remoteok.com/api`, JSON sem chave. **O primeiro item é um aviso
  legal**, não uma vaga. Campos: título, empresa, `tags`, `location` (vazio quando é *worldwide*),
  `salary_min`/`salary_max` (USD; 0 = não informado), `apply_url`, `epoch`. Fontes:
  [jobspipe](https://jobspipe.dev/blog/remoteok-api), [Apify](https://apify.com/retrainmap/remoteok-jobs).
- **Termos** [fato]: linkar de volta (sem `nofollow`) e citar o Remote OK, sob pena de corte do
  acesso. Não usar o logo.
- **Volume** [inferência]: muita vaga agregada e repetida de outros sites. Na fatia web que aceita
  Brasil, depois de tirar duplicatas, sobram 5–15 por dia.

### Jobicy

- **Leitura** [fato]: `GET https://jobicy.com/api/v2/remote-jobs` com `count` (1–100), `geo`
  (inclui `latam` e país), `industry` (`engineering`…) e `tag`. Também há RSS. Não precisa de
  token. Exige atribuição e proíbe redistribuir para agregadores
  ([fonte secundária](https://mindcloud.co/docs/universal/rest/jobicy/latest/actions/list-brazil-remote-jobs)).
- **Campos** [fato]: empresa, cargo, local, tipo, descrição e salário quando há.
- **Por que entra** [inferência]: é a única, além do Himalayas, com **filtro LatAm/Brasil no
  servidor**. O volume é pequeno, mas quase tudo serve.

### Working Nomads

- **Leitura** [fato]: JSON anônimo em `https://www.workingnomads.com/api/exposed_jobs/`, com URL,
  título, empresa, categoria, local, data, tags e descrição. Sem paginação histórica
  ([fonte secundária](https://apify.com/automation-lab/working-nomads-jobs-scraper)).
- **Avaliação** [inferência]: é um agregador e repete muito do que já vem de WWR e RemoteOK. Só
  entra se a camada 0 mostrar que traz vaga nova.

### Hacker News — *Ask HN: Who is hiring?*

- **Leitura** [fato]: as APIs oficiais (Firebase e Algolia, `hn.algolia.com`) são públicas, sem
  chave. O fio sai no primeiro dia útil de cada mês, postado pela conta `whoishiring`.
- **Volume** [fato]: o fio caiu de quase mil comentários (2021) para ~320 vagas por mês em 2024
  ([análise 2011–2024](https://exxa.notion.site/Hacker-News-analysis-Ask-HN-Who-is-hiring-1099f6be204280b7b909c08634441563)).
  Um agregador contou 33 papéis no fio de setembro de 2026, 48% remotos
  ([ctaio.dev](https://ctaio.dev/en/tech-jobs/who-is-hiring/september-2026/)); o número parece baixo
  e pode ser filtro dele [inferência].
- **Campos**: texto livre com empresa, local, REMOTE/ONSITE e às vezes salário. O Claude teria de
  extrair os campos.
- **Avaliação** [inferência]: muita vaga é só EUA ou presencial. Na média, ~1 vaga útil por dia.
  Barato de ler uma vez por mês.

### Get on Board (getonbrd.com)

- **Leitura** [fato, fonte secundária]: API REST pública de vagas tech na América Latina, Brasil
  incluído. Traz título, senioridade, tags, empresa e país, remoto/híbrido/presencial, **faixa em
  USD (muitas vagas são obrigadas a publicar)**, número de candidaturas e link
  ([Apify](https://apify.com/scrapers_lat/getonbrd-scraper.md)).
- **Avaliação** [inferência]: o foco é Chile, Argentina e México, mas há muita vaga remota aberta a
  toda a LatAm em USD. É a melhor fonte para o piso, porque quase sempre tem faixa. A doc da API
  (`getonbrd.com/api-doc`) não pôde ser lida daqui.

### Wellfound (ex-AngelList Talent)

- **Leitura** [fato]: o site usa **DataDome** contra bots desde 2025
  ([caso DataDome](https://datadome.co/customers-stories/33-less-bot-traffic-lower-costs-how-wellfound-gains-time-tranquility-with-datadome/)).
  Mostra salário, *equity* e política de remoto na vaga, e tem candidatura em um clique com perfil
  ([wellfound.com/candidates/remote](https://wellfound.com/candidates/remote)). Há ~776 vagas para
  a América Latina ([listagem](https://wellfound.com/location/latin-america-8?page=2)).
- **Avaliação** [inferência]: ler exige navegador logado e brigar com o anti-bot. Fica fora da
  entrega 1. Na entrega 2 pode valer criar o perfil.

### Arc, Turing, Toptal, Strider, Revelo (redes de talentos)

- **Modelo** [fato]: perfil + triagem, depois a empresa ou a plataforma propõe. Turing anuncia
  aceitar ~1%, Arc ~2%, Toptal o "top 3%"
  ([comparativo](https://www.index.dev/blog/toptal-turing-arcdev-bairesdev-indexdev-comparison)).
  O Strider pede inglês B1–B2 e 3+ anos de experiência ([onstrider.com](https://onstrider.com/)).
  O Revelo atende empresas dos EUA com talento LatAm e publica faixas de referência
  (full-stack LatAm US$ ~48–72 mil/ano,
  [revelo.com/salaries](https://www.revelo.com/salaries/full-stack-developer-salary)). Turing virou
  trabalho de avaliação de IA em 2026 [fato, mesma fonte do comparativo].
- **Avaliação** [inferência]: não há lista de vagas para varrer. Servem como **perfis criados uma
  vez**, na entrega 2. A faixa do Revelo serve de régua de mercado para o relatório. Toptal é
  freela por hora e fica fora pela regra do ticket 06.

### Remote.com, Jobgether e outros agregadores

- **Jobgether** [fato]: grátis para candidato. O premium (com *auto-apply*) custa menos de US$ 1
  por dia. Anuncia ~21 mil vagas remotas abertas ao Brasil
  ([FAQ](https://jobgether.com/faq/answer/is-jobgether-free-to-use),
  [listagem](https://jobgether.com/remote-jobs/brazil/4)). Não achei API [inferência]. É agregador
  e repete o que já se lê nas fontes acima.
- **hiring.cafe** [fato]: agrega 2,9 milhões de vagas tiradas direto de Greenhouse, Lever, Workday
  etc. Não tem API pública e os termos não convidam scraping
  ([jobspipe](https://jobspipe.dev/blog/hiring-cafe-api)). Fica fora.
- **Remote.com (jobs)**: a busca não trouxe nada útil. Descartado.

---

## Brasil

### Gupy

- **O que é** [fato]: o ATS dominante no Brasil, com ~20 mil vagas por mês de ~1.500 empresas
  (Ambev, Cielo, Vivo…) em todas as áreas
  ([tecnoblog](https://tecnoblog.net/comunidade/t/processo-seletivo-longo-e-feedbacks-rasos-o-que-acontece-com-a-gupy/58563)).
  Cada empresa tem sua página `empresa.gupy.io`. O portal `portal.gupy.io` junta todas.
- **Leitura** [fato, fonte secundária]: o portal consome um JSON público
  (`portal.api.gupy.io/api/v1/jobs`), sem login, até 100 vagas por página, com filtro por termo,
  cidade, estado e `workplaceType` (remoto/híbrido/presencial). Traz `publishedDate` e o link da
  vaga ([Apify](https://apify.com/dadosbr/gupy-vagas.md),
  [Apify](https://apify.com/automation-lab/gupy-jobs-scraper.md)). **Não é a "Gupy Public API"
  oficial**: essa é para empresas, com token
  ([Digibee](https://docs.digibee.com/documentation/connectors-and-triggers/connectors/industry-solutions/gupy)).
  Pode mudar sem aviso [inferência].
- **O filtro de cidade casa com a regra dele** [inferência]: o JSON permite buscar `Ribeirão Preto`,
  `São Paulo` e `Araraquara` com `workplaceType` híbrido/presencial, mais remoto em qualquer lugar.
- **Faixa** [inferência]: a maioria das vagas na Gupy não mostra salário e pede pretensão. Não
  confirmei se o JSON tem campo de salário.
- **Volume** [inferência]: vagas de dev web remotas ou nas três cidades, 10–40 por dia. Muita é
  júnior ou abaixo do piso; a triagem fica com o Claude.
- **Candidatura** [fato]: na própria Gupy, com **uma conta para todas as empresas**. A conta abre
  por e-mail, Google, CPF, LinkedIn ou link mágico. Coleta nome, nascimento, país, **CPF** e
  **celular**. O currículo é preenchido uma vez. A IA da Gupy cruza currículo e vaga. A empresa pode
  pôr questionário próprio ou testes prontos
  ([blog Gupy](https://www.gupy.io/blog-do-emprego/curriculo-gupy),
  [aviso de privacidade](https://www.gupy.io/hubfs/LGPD/RS%20Candidatos/9%20versao/Aviso%20Recrutamento%20%26%20Sele%C3%A7%C3%A3o%20-%20Candidatos%20-%209%20vers%C3%A3o%202025.pdf)).
  Existe candidatura pelo WhatsApp [fato, mesma fonte do tecnoblog].
- **Custo e limite** [inferência]: grátis. Não achei limite de candidaturas por dia.
- **Termos** [fato]: a Gupy pode remover conteúdo e suspender ou cancelar o cadastro por uso
  indevido ([termos do candidato](https://www.gupy.io/termos-de-uso-recrutamento-e-selecao-candidatos)).
  Não consegui ler a cláusula sobre robôs. Há bots open source que aplicam na Gupy com Playwright
  [fato, menção genérica em resultado de busca], sem relato de banimento achado.
- **Automação da candidatura** [inferência]: viável por navegador logado (o login é um só). O
  risco está nas perguntas abertas e nos testes por empresa, que mudam de vaga para vaga. Para a
  entrega 2, *tentar a sorte* na Gupy parece o caso mais promissor do Brasil.

### Repositórios de vaga no GitHub (`frontendbr/vagas`, `backend-br/vagas`)

- **Leitura** [medido, 2026-10-02]: issues públicas, legíveis pela API do GitHub (o Whis já usa).
  - `frontendbr/vagas`: 32 abertas; 15 novas entre 26/08 e 30/09. Etiquetas: `Remoto`, `Híbrido`,
    `CLT`, `PJ`, `Pleno`, `Sênior`, `São Paulo`. Títulos com USD e empresas como Coodesh, Strider e
    Jcal ([issues](https://github.com/frontendbr/vagas/issues)).
  - `backend-br/vagas`: 41 abertas; 15 novas entre 10/09 e 01/10. Etiquetas `Remoto`, `PJ`, `CLT`,
    `Contrato` e uma com `Salary: $15K–$18K/month`
    ([issues](https://github.com/backend-br/vagas/issues)).
- **Volume** [medido]: ~3 a 5 por semana em cada repositório. Pouco, mas muito no perfil dele
  (full-stack, React/Next, Python, muitas em USD).
- **Candidatura** [inferência]: o texto da issue manda para e-mail, formulário ou ATS. Varia.
- **Termos**: API oficial, sem risco de conta. A conta GitHub dele **é pública** e o empregador
  pode vê-la, então o Whis **só lê**: nunca comenta nem reage [inferência, regra de discrição].

### Programathor

- **O que é** [fato]: um quadro só de vagas para programador, de graça para o dev, com ~200 mil
  profissionais cadastrados e ~700 empresas. Mantém ~220 vagas online
  ([Baguete](https://www.baguete.com.br/noticias/portal-de-selecao-foca-programadores),
  [Betterteam](https://www.betterteam.com/br/programathor)). Tem filtro de remoto
  ([Betterteam](https://www.betterteam.com/br/programathor)).
- **Leitura** [inferência]: a lista é pública sem login e dá para ler com Playwright ou com
  requisição simples. Não há API nem RSS conhecidos. Lembro que os cartões mostram faixa salarial e
  nível, mas não confirmei.
- **Candidatura** [fato/inferência]: no próprio site, com perfil Programathor (algoritmo de
  *matching*, chat, testes voluntários). Os dados pedidos na conta não foram verificados.
- **Avaliação** [inferência]: o volume é pequeno, mas o nicho é exato. Se a faixa aparecer mesmo, é
  a melhor fonte brasileira para o piso.

### Remotar

- **O que é** [fato]: um quadro de vagas 100% remotas para brasileiros, com curadoria e parceria de
  listas com o TecMundo ([TecMundo](https://www.tecmundo.com.br/mercado/403325-home-office-64-vagas-para-trabalho-remoto-internacional-1403.htm)).
- **Avaliação** [inferência]: tem bastante vaga internacional "em dólar para brasileiro", que é a
  filtro "aceita Brasil?" já feito pela curadoria. Leitura e candidatura não verificadas. Vai para a camada 0.

### Coodesh

- **O que é** [fato]: plataforma brasileira de vagas tech com validação técnica (testes,
  entrevista técnica, avaliação comportamental), 32 mil+ devs cadastrados
  ([B2B Stack](https://www.b2bstack.com.br/product/coodesh)). Publica vagas também nos repositórios
  do GitHub [medido: issues #8565 e #8564 do `frontendbr`].
- **Avaliação** [inferência]: a candidatura passa por teste técnico, então não serve para mandar
  *tentar a sorte* em massa. A leitura pode vir pelo GitHub.

### GeekHunter

- **Modelo** [fato]: invertido, a empresa manda pedido de entrevista com salário definido. Aprova
  ~5% dos candidatos depois de testes. Pertence à Howdy.com desde agosto de 2023
  ([InvestNews](https://investnews.com.br/negocios/howdy-com-compra-brasileira-geekhunter-dos-gemeos-tomas-e-celso-ferrari),
  [Startupi](https://startupi.com.br/?p=238369)).
- **Avaliação** [inferência]: não há o que varrer. Vale criar o perfil uma vez (entrega 2), porque
  a proposta já vem com salário.

### Indeed (e Glassdoor)

- **Leitura** [fato]: a Publisher API foi desligada em 2023 e não há substituto para quem consome
  dados ([jobspipe](https://jobspipe.dev/blog/indeed-publisher-api)). O `robots.txt` bloqueia
  `/jobs?q=`, e há bloqueio de bots por reputação de rede e aprendizado de máquina
  ([webscraping.ai](https://webscraping.ai/faq/indeed-scraping/can-i-automate-the-process-of-indeed-scraping)).
- **Termos** [fato]: proíbe scraping e **proíbe usar bots ou ferramentas automatizadas para se
  candidatar**, sob pena de bloqueio ou encerramento da conta
  ([diretrizes do candidato](https://pt.indeed.com/help/job-seekers/articles/360028540531-diretrizes-do-indeed-para-candidatos),
  [ConductAtlas](https://conductatlas.com/platform/indeed/indeed-terms-of-service/provision/CA-P-028619/prohibition-on-scraping-automated-access-and-bot-activity/)).
- **Conta** [fato]: verificação de telefone por SMS, ligação ou WhatsApp
  ([ajuda](https://support.indeed.com/hc/en-us/articles/34540805299085)).
- **Glassdoor** [fato]: incorporado juridicamente ao Indeed em 1º de julho de 2026. Opera sob os
  termos do Indeed e passou a exigir login Indeed desde o fim de 2025
  ([Reworked](https://reworked.co/employee-experience/glassdoor-folds-into-indeed/)). Para vaga, é
  o Indeed.
- **Avaliação** [inferência]: é a maior fonte depois do LinkedIn, mas é hostil a automação dos dois
  lados. Fica fora da entrega 1. Uma eventual leitura logada, nos moldes do X, seria decisão dele
  com risco declarado.

### LinkedIn (só o papel de fonte; detalhe no ticket 08)

- [fato]: é de longe o maior quadro de vaga tech no Brasil
  ([wmtips](https://www.wmtips.com/technologies/job-boards/country/br/)). Tem endpoints *guest*
  sem login (`/jobs-guest/jobs/api/seeMoreJobPostings/search`) que devolvem HTML de 25 em 25, mas
  dão **429 depois de ~10 páginas por IP** ([jobspipe](https://jobspipe.dev/blog/linkedin-job-scraper-python.md)).
  O User Agreement, seção 8.2, proíbe scraping e automação, com restrição ou encerramento de conta
  ([ajuda LinkedIn](https://www.linkedin.com/help/linkedin/answer/a1341387)).
- [inferência]: muitas vagas do LinkedIn também estão na Gupy ou num ATS público (Greenhouse,
  Lever). Ler essas fontes cobre parte do LinkedIn sem tocar nele.

### Catho, Vagas.com, InfoJobs, Sólides, BNE (generalistas)

- **Catho** [fato]: candidatar é grátis no plano básico. Planos pagos de R$ 89 a R$ 360
  ([stylingcv](https://stylingcv.com/blog/como-usar-catho-guia-completo-2026/)). A própria Catho
  foi condenada por usar robôs na base da Curriculum
  ([Baguete](https://www.baguete.com.br/noticias/catho-x-curriculum-catho-e-condenada)). Lançou um
  envio automático de currículo por IA
  ([TecMundo](https://www.tecmundo.com.br/mercado/249014-catho-lanca-ferramenta-ia-envia-curriculos-automaticamente.htm)).
- **Vagas.com** [fato]: não cobra do candidato
  ([termos](https://www.vagas.com.br/candidatos/termos-de-uso)). Cláusula de robô não verificada.
- **Sólides Vagas** [fato]: 45 mil+ vagas, cadastro grátis
  ([Itatiaia](https://www.itatiaia.com.br/ciencia-e-tecnologia/solides-lanca-solucao-para-incentivar-empregabilidade/)).
- **Avaliação** [inferência]: muito volume, mas pouca vaga de web dev remota acima de R$ 5 mil, e o
  que há costuma estar também na Gupy ou no LinkedIn. Ficam fora.

### Trampos

- [fato]: vagas de comunicação, marketing e tecnologia. Grátis, com premium opcional. Já anunciou
  ~160 vagas de TI ([Olhar Digital](https://olhardigital.com.br/2020/11/19/pro/plataforma-disponibiliza-160-vagas-de-ti-com-salarios-de-ate-r-12-mil/),
  dado de 2020).
- [inferência]: pouco volume de dev hoje. Fica fora.

---

## A candidatura fora do site: os ATS

Quase todo o remoto internacional (Himalayas, Remotive, WWR, RemoteOK, Jobicy, HN) **manda para o
ATS da empresa**. O que importa para a entrega 2:

- **Greenhouse** [fato]: o formulário é público, sem conta. Usa **reCAPTCHA invisível**, que
  analisa mouse e digitação ([suporte Greenhouse](https://support.greenhouse.io/hc/en-us/articles/115005448066)).
  Já apareceu **reCAPTCHA Enterprise** em tentativas automatizadas
  ([vanja.io](https://vanja.io/zapply-hacking-greenhouse-and-lever/)). As vagas também se leem pela
  API pública `boards-api.greenhouse.io/v1/boards/{empresa}/jobs`, sem autenticação
  ([dev.to](https://dev.to/zsevic/integration-with-greenhouse-public-jobs-api-1lj3)).
- **Lever** [fato]: o formulário é público, sem conta. API pública
  `api.lever.co/v0/postings/{empresa}?mode=json`
  ([dev.to](https://dev.to/zsevic/integration-with-lever-public-jobs-api-2mnn)).
- **Ashby, Workable** [inferência]: formulário público, sem conta, CAPTCHA variável. **Workday**
  pede uma conta por empresa e é o pior caso.
- **Consequência** [inferência]: na entrega 1, o relatório entrega o link do ATS e o texto pronto.
  Na entrega 2, *tentar a sorte* por navegador vai bater em CAPTCHA em parte dos formulários, e a
  regra do ticket 06 manda parar e anotar. **A taxa de envio sozinho no remoto internacional deve
  ser baixa**; a Gupy promete mais.
- **Precedente** [fato]: um dev brasileiro relatou um agente de IA que tocou a busca por vaga
  remota por 4 dias, com 360 vagas lidas e **9 candidaturas** enviadas
  ([TabNews](https://www.tabnews.com.br/vinicius91carvalho/deixei-um-agente-de-ia-tocar-minha-busca-por-vaga-remota-por-4-dias-360-vagas-9-candidaturas-e-a-conta-do-llm)).
  O conteúdo não pôde ser lido daqui. Vale ele abrir: é a medida mais próxima do que a caçada vai
  achar.

---

## O que falta medir (camada 0, no PC dele)

1. Uma leitura de cada fonte da entrega 1, contando: total, web/full-stack, que aceita Brasil e que
   tem faixa. Substitui as estimativas da tabela.
2. O JSON da Gupy: ver se tem campo de salário, se os filtros de cidade funcionam para Ribeirão
   Preto, São Paulo e Araraquara, e se responde sem cabeçalho de navegador.
3. Programathor e Remotar: ver se a lista é pública e se a faixa aparece no cartão.
4. Get on Board: ler a `api-doc` e ver se o Brasil aparece de fato.
5. Duplicatas entre RemoteOK, Working Nomads, Himalayas e WWR: quanto cada uma acrescenta.
6. Games e áudio: buscar `game`, `unity`, `audio`, `DSP`, `JUCE` em Himalayas e Remotive e ver se há
   algo que aceite Brasil, para calibrar o *tentar a sorte*.
