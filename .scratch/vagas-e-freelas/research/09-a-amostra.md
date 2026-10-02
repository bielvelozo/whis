# Research 09 — A amostra para o cliente

Levantado em 2026-10-02.

Pergunta: ticket [09](../issues/09-a-amostra-para-o-cliente.md). Contexto: ticket
[06](../issues/06-os-limites-da-autonomia.md) — no freela com **chance boa** o Whis não envia nada;
entrega *"tudo mastigado"* (proposta, link para aplicar e, no freela web, uma amostra com link
público que ele só copia).

Convenção: **[F]** = fato com fonte (link ao lado); **[I]** = inferência do agente. As páginas de
docs da Vercel, GitHub, Cloudflare, Netlify, Workana e 99Freelas estavam bloqueadas pelo proxy desta
sessão; os fatos delas vieram de buscas que citam essas páginas (o link é o da página oficial
citada). A doc de artifacts do Claude Code foi lida na íntegra. Vale reconferir os números do plano
grátis na hora da spec: mudam (a Netlify mudou em 2025 e teve bug em 2026).

## Resumo

- **Hospedagem recomendada: Cloudflare Pages por *direct upload*** (`npx wrangler pages deploy
  <pasta> --project-name=<nome>`, com `CLOUDFLARE_API_TOKEN`). Grátis, banda ilimitada, uso
  comercial permitido, 500 deploys/mês, URL `<nome-neutro>.pages.dev` sem o nome dele, sobe em
  segundos e sai do ar com `wrangler pages project delete <nome> --yes`. O Node já existe na máquina
  (o Whis roda o CLI do Claude pelo npm). Ressalva: a Cloudflare põe o investimento novo em Workers;
  Pages segue suportado, mas em manutenção — o plano B é Workers com *static assets* (mesma conta,
  mesmo token).
- **Plano B só-Python: Netlify por zip na API** (um `POST` com o zip e um token). Uso comercial
  permitido no Free, URL `<nome>.netlify.app`. Mas o Free virou 300 créditos/mês, **15 créditos por
  deploy de produção** (~20 amostras/mês) e, quando acaba, **todos os sites da conta pausam**; houve
  bug de créditos travados de jul. a set. de 2026.
- **GitHub Pages serve, mas expõe**: no Free o repositório tem de ser público (o código da amostra
  fica aberto) e a URL é `usuario.github.io/...`, que leva ao perfil dele — isso vira *rota de
  contato*, o que a Workana pune. Só com uma **organização de nome neutro** (`org.github.io`). Pode
  levar até ~10 min para ir ao ar.
- **Vercel Hobby: evitar.** A regra define uso comercial como qualquer deploy *"for the purpose of
  financial gain of anyone involved… including a paid employee or consultant writing the code"*. Uma
  demo feita para ganhar um contrato pago fica, no mínimo, na zona cinzenta.
- **Artifact do claude.ai não serve para o cliente.** Dá para tornar público (link aberto sem conta,
  em Pro/Max), mas **o botão Share é manual, no navegador** (a ferramenta Artifact não compartilha),
  a URL é `claude.ai/...` e o visitante sem login vê o rótulo *"Content is user-generated and
  unverified."*. Serve como **prévia privada para ele** avaliar a amostra no celular antes de mandar.
- **Plataformas — crítico:** **Upwork** permite link externo de portfólio/amostra (não pode dado de
  contato antes do contrato). **99Freelas** permite link externo *"só com o intuito de apresentar o
  portfólio"*, sem contato. **Workana é o risco**: a ajuda oficial lista *enviar links externos*
  (até Behance) como motivo de suspensão de propostas (~15 dias); respostas da própria Workana dizem
  que página feita por você e **sem dado de contato** pode. Na Workana o padrão do Whis deve ser
  **anexo** (print/PDF da amostra), com o link só como opção marcada como risco.
- **A amostra nunca leva nome, e-mail, WhatsApp, logo do cliente nem link para perfil.** Isso
  protege das duas coisas: a regra anti-contato das plataformas e a exposição dele. Leva um aviso
  discreto *"Conceito de demonstração para a proposta — não é o site final"* e `noindex`.
- **Tamanho: um conceito, não o trabalho.** Uma página (hero + 2–3 seções do pedido), estática,
  sem formulário funcionando, imagens genéricas, textos do próprio pedido. Feita em uma corrida
  curta. Fica no ar por um prazo (ex.: 30 dias) e o Whis a derruba e registra.
- **Sem amostra quando não é web visual** (bug fix, manutenção, integração, backend, automação,
  app): no lugar, um **plano de execução** de 3–5 passos e, se o cliente deu URL/repo público, um
  **diagnóstico** curto (o que está errado e como resolve).
- **O pacote** de cada chance boa: oportunidade (link, cliente, orçamento, prazo, concorrência),
  por que casa, alertas, preço e prazo sugeridos com a conta, **proposta de 100–200 palavras** que
  abre citando o pedido, a amostra (link + print + regra da plataforma + validade) e o botão para
  aplicar. Formato na seção 5.

## 1. Onde hospedar a amostra

Requisito do Whis [I]: publicar sem intervenção a partir do PC (token no config, sem navegador),
URL que não exponha o nome dele, grátis sem cartão, uso comercial permitido, tirar do ar por
comando, `noindex`. A conta e o token são criados por ele **uma vez** (CAPTCHA e verificação são
dele, ticket 06). O ADR 0001 continua de pé: o Whis não tem servidor; quem hospeda é um serviço de
terceiros, como o artifact do jornal já é [I] — dizer isso na spec.

### Tabela

| | Cloudflare Pages | Netlify | GitHub Pages | Vercel Hobby | Surge.sh | Artifact claude.ai |
|---|---|---|---|---|---|---|
| Custo | grátis [F] | grátis, 300 créditos/mês [F] | grátis (repo público) [F] | grátis [F] | grátis [F] | já pago (assinatura) |
| Uso comercial no free | sim [F] | sim [F] | não para "negócio online/e-commerce"; demo é ok [F/I] | **não** [F] | não explícito [F] | n/a |
| URL | `nome.pages.dev` [F] | `nome.netlify.app` [I] | `usuario.github.io/repo` ou `org.github.io/repo` [F] | `projeto.vercel.app` [I] | `nome.surge.sh` [F] | `claude.ai/code/artifact/<uuid>` [F] |
| Expõe o nome dele | não, se o nome for neutro | não | **sim**, salvo org neutra | não | não | não, mas mostra a marca Claude |
| Publicar sem intervenção | `wrangler pages deploy` + token [F] | `POST` zip na API + token [F] | API/`gh` + token [F] | `vercel deploy --token` [F] | `surge` + `--token` [F] | ferramenta Artifact [F]; tornar público é manual [F] |
| Tirar do ar | `wrangler pages project delete` [F] | apagar o site (API/CLI) [I] | `DELETE .../pages` ou apagar o repo [I] | `vercel remove` [I] | `surge teardown dominio` [F] | despublicar/apagar [F] |
| No ar em | segundos [I] | segundos [I] | até ~10 min [F] | segundos [I] | segundos [I] | segundos |
| `noindex` | preview já tem; produção via `_headers` [F] | deploy preview tem; produção não [F] | só `<meta>` no HTML [I] | preview tem; produção não [F] | só `<meta>` [I] | n/a |

### Cloudflare Pages (recomendado)

- **Limites do Free [F]**: 500 builds/mês, 20.000 arquivos por site, 25 MiB por arquivo
  ([limites](https://developers.cloudflare.com/pages/platform/limits/)). Banda ilimitada e sites
  ilimitados, uso comercial permitido
  ([freetier.co](https://freetier.co/directory/products/cloudflare-pages),
  [Gigazine](https://www.gigazine.net/gsc_news/en/20250116-why-cloudflare-pages-free)) — fonte
  secundária; [I] a regra geral da Cloudflare não restringe uso comercial no Free.
- **Publicar [F]**: *direct upload* sem git — `wrangler pages project create`, depois
  `wrangler pages deploy <pasta>`; token com permissão *Cloudflare Pages — Edit* em
  `CLOUDFLARE_API_TOKEN`; `wrangler pages project list --json` para listar
  ([direct upload](https://developers.cloudflare.com/pages/get-started/direct-upload/),
  [wrangler-action](https://github.com/marketplace/actions/deploy-cloudflare-pages-github-action)).
- **Tirar do ar [F]**: `npx wrangler pages project delete <nome> --yes`
  ([direct upload](https://developers.cloudflare.com/pages/get-started/direct-upload/)).
- **URL [F/I]**: `<projeto>.pages.dev` [F]. O nome é global; se já existir, a Cloudflare acrescenta
  sufixo [I, a confirmar]. Nome neutro sugerido: `<tema>-<4 letras aleatórias>`, ex.
  `clinica-sorriso-k7q2.pages.dev` [I] — nunca o nome dele nem "whis".
- **Indexação [F]**: preview já sai com `X-Robots-Tag: noindex`; para a produção, um `_headers` com
  `https://:project.pages.dev/*  X-Robots-Tag: noindex`
  ([preview deployments](https://developers.cloudflare.com/pages/configuration/preview-deployments/)).
- **Risco [F]**: Pages não está sendo descontinuado, mas *"all new investment goes to Workers"*
  ([morphllm](https://www.morphllm.com/comparisons/cloudflare-pages-vs-workers), fonte
  secundária). Plano B na mesma conta: **Workers com static assets** — requisições a arquivos
  estáticos são grátis e ilimitadas
  ([billing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations)); URL
  `<nome>.<subdominio-da-conta>.workers.dev` [I], com o subdomínio da conta escolhido neutro.
- **Bônus [F]**: *Cloudflare Drop* (jul. 2026) publica sem conta, mas o site vive só 60 min se não
  for reivindicado — não serve para amostra
  ([changelog](https://developers.cloudflare.com/changelog/post/2026-07-08-cloudflare-drag-and-drop/)).
- **Encaixe no Whis [I]**: o CLI do Claude já vem do npm (`src/whis/claude_cli.py`), então Node e
  `npx` existem na máquina; o Python chama `npx wrangler ...` por subprocess, como chama o `claude`.

### Netlify (plano B só-Python)

- **Uso comercial [F]**: permitido no Free/Starter; só não pode revender hospedagem a terceiro
  ([answers.netlify.com](https://answers.netlify.com/t/can-we-use-netlify-free-plan-for-commercial-purposes/41545)).
- **Custo [F]**: desde 05/09/2025, planos por crédito; Free = 300 créditos/mês; **deploy de
  produção = 15 créditos**, banda = 10 créditos/GB
  ([changelog](https://www.netlify.com/changelog/netlify-pricing-update-introducing-credit-based-plans/),
  [withorb](https://withorb.com/blog/netlify-pricing)). [I] ~20 amostras/mês se nada mais gastar.
- **Quando acaba [F]**: todos os sites da conta pausam com "Site not available" até o ciclo virar
  ([netli.fyi](https://netli.fyi/blog/netlify-free-plan-limits-2026)). **Bug de 2026 [F]**: de julho
  a setembro, contas Free ficaram com deploy de produção bloqueado ("operational credits") mesmo com
  saldo ([fórum](https://answers.netlify.com/t/free-plan-production-deploys-still-blocked-since-jul-24-monthly-300-credits-never-granted/165874)).
- **Publicar [F]**: `POST /api/v1/sites/{site_id}/deploys` com `Content-Type: application/zip` e o
  zip no corpo, token pessoal no `Authorization`; até 25.000 arquivos por zip
  ([guia oficial](https://developers.netlify.com/guides/deploy-zip-file-to-production-website/)).
  [I] Puro `httpx`/`requests`, sem Node.
- **Netlify Drop [F]**: anônimo vive 1 h, e desde 2024 fica protegido por senha até ser
  reivindicado ([blog](https://www.netlify.com/blog/thirteen-years-of-netlify-drop)) — não serve.
- **Indexação [F]**: deploy preview tem `noindex` automático; branch deploy e produção não
  ([fórum](https://answers.netlify.com/t/override-x-robots-tag-noindex-header-in-deploy-preview/38980)).
  [I] Pôr `X-Robots-Tag` num `_headers` ou `<meta name="robots">`.

### GitHub Pages

- **Limites [F]**: site publicado até 1 GB, banda *soft* de 100 GB/mês, 10 builds/h (não se aplica
  com Actions); proibido usar como hospedagem grátis de negócio online, e-commerce ou SaaS
  ([limites](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)).
  [I] Uma demo estática de proposta não é e-commerce; passa.
- **Repo público [F]**: no GitHub Free, Pages só sai de repositório público; Pages privado exige
  Enterprise Cloud ([planos](https://docs.github.com/en/get-started/learning-about-github/githubs-plans)).
  Logo o código da amostra fica aberto.
- **URL e exposição [F/I]**: `usuario.github.io/repo` [F] mostra o usuário, que leva ao perfil (com
  e-mail/links) — na Workana isso pode contar como rota de contato [I]. **Uma conta grátis por
  pessoa** ([ToS, via codenote](https://codenote.net/en/posts/github-tos-one-free-account-per-person/)),
  então não dá para criar uma segunda conta pessoal "neutra"; dá para criar uma **organização grátis
  de nome neutro** (`org.github.io`) [F: Pages roda em org Free com repo público, mesma página de
  planos].
- **Publicar [F]**: `POST /repos/{owner}/{repo}/pages` com `source.branch` (e `build_type`)
  ([REST Pages](https://docs.github.com/en/rest/pages/pages)); [I] com `gh repo create` +
  `git push` + essa chamada. Um repo por amostra (apaga inteiro) ou um repo com pastas (uma URL
  base, apaga a pasta) — [I] repo por amostra é mais limpo para tirar do ar.
- **Tempo [F]**: pode levar até 10 min para publicar
  ([criando um site](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)).
- **Indexação [I]**: Pages não deixa configurar cabeçalhos; só `<meta name="robots" content="noindex">`.

### Vercel Hobby (evitar)

- **Comercial [F]**: Hobby é *"non-commercial personal use only"*; uso comercial é *"any Deployment
  that is used for the purpose of financial gain of anyone involved in any part of the production
  of the project, including a paid employee or consultant writing the code"*; exemplos incluem
  *"advertising the sale of a product or service"* e *"receiving payment to create, update, or host
  the site"* ([fair use](https://vercel.com/docs/limits/fair-use-guidelines)).
- **Demos [F]**: na comunidade, a Vercel diz que site de demonstração onde ninguém ganha dinheiro é
  ok, e que clone de site real com logo verdadeiro já foi denunciado como phishing
  ([comunidade](https://community.vercel.com/t/question-on-fair-use-and-hobby-plan-suitability-for-demo-commercial-websites-in-portfolio/1769)).
- **Leitura [I]**: a amostra existe para ganhar um contrato pago e tende a virar a base do trabalho
  pago; pela letra da regra, isso é ganho financeiro do "consultant writing the code". Zona cinzenta
  que não vale o risco quando Cloudflare e Netlify permitem.
- **Resto, para registro [F]**: 100 deploys/dia, 100 GB de banda
  ([deploywise](https://deploywise.dev/blog/vercel-free-tier-limits-2026)); deploy sem git por CLI
  com `--token` e `--prebuilt` ([guia](https://vercel.com/kb/guide/using-vercel-cli-for-custom-workflows));
  preview com `noindex` automático, produção não
  ([guia](https://vercel.com/kb/guide/are-vercel-preview-deployment-indexed-by-search-engines));
  no Hobby, produção é sempre pública
  ([deployment protection](https://vercel.com/docs/deployment-protection)).

### Surge.sh

- **[F]** Grátis com projetos e deploys ilimitados, subdomínio `*.surge.sh` com SSL, domínio próprio
  ([planos](https://surge.sh/docs/platform/plans)); token para CI com `surge token` / `--token`;
  tirar do ar com `surge teardown nome.surge.sh`
  ([teardown](https://surge.sh/help/tearing-down-a-project)). Uso comercial: os termos não dizem
  explicitamente [F, via busca].
- **[I]** Funciona, mas é um serviço pequeno, sem cabeçalhos no Free (só `<meta>` para `noindex`) e
  sem a robustez de uma Cloudflare. Reserva.

### Outros

- **Firebase Hosting, canais de prévia [F]**: `firebase hosting:channel:deploy <canal> --expires 7d`;
  expira por padrão em 7 dias, máximo 30; ao expirar, o canal é apagado em até 24 h
  ([manage releases](https://firebase.google.com/docs/hosting/manage-releases)). **A expiração
  automática é exatamente o ciclo de vida de uma amostra** [I]. Contra: projeto Google Cloud,
  Firebase CLI, URL com o id do projeto (`<projeto>--<canal>-<hash>.web.app`) [I]; não confirmei o
  plano Spark para canais. Alternativa a avaliar se a limpeza manual for um problema.
- **Domínio próprio neutro [F/I]**: `.com.br` custa R$ 40/ano no Registro.br
  ([fonte](https://tudosobrehospedagemdesites.com.br/registro-de-dominio/)) [F, secundária]. [I]
  Opcional e decisão dele (o Whis nunca gasta dinheiro sozinho, ticket 06): um domínio como
  `demo-<algo>.com.br` apontado para a Cloudflare dá cara mais profissional que `pages.dev`, mas não
  é necessário.

## 2. Artifact do claude.ai como amostra

- **Dá para tornar público [F]**: em Pro/Max, o artifact do Claude Code pode ser compartilhado por
  um link *"that anyone on the internet can open, with no claude.ai sign-in required"*; em
  Team/Enterprise depende do admin
  ([doc de artifacts](https://code.claude.com/docs/en/artifacts)). Artifacts de chat publicados
  também abrem sem conta
  ([suporte](https://support.claude.com/en/articles/9547008)).
- **Mas o passo é manual [F]**: *"A new artifact is visible only to you. To share it, open the
  artifact in your browser and use the Share control in the page header."* A ferramenta Artifact
  (que o Whis usa no jornal) publica privado e não tem ação de compartilhar. [I] Ele teria de abrir
  e clicar — quebra o "só copia".
- **Marca e rótulo [F]**: URL `claude.ai/code/artifact/<uuid>`; quem abre sem login *"sees the
  label `Content is user-generated and unverified.`"* no cabeçalho do visualizador
  ([doc](https://code.claude.com/docs/en/artifacts)). [I] Para um cliente, isso lê como "feito por
  IA" e "não verificado" — o oposto do que uma proposta quer.
- **Limitações [F]**: uma página só, sem rotas; CSP bloqueia imagens externas (tudo embutido); só
  fontes do Google Fonts e scripts de 5 CDNs; até 16 MiB. Depois de público, o Claude Code pede
  aprovação para alterar. No Agent SDK a ferramenta vem desligada por padrão (o Whis já a liga com
  `CLAUDE_CODE_ARTIFACT=1` no jornal).
- **Uso certo [I]**: **prévia privada para ele** — o Whis publica a amostra também como artifact
  privado (ou só manda o link `pages.dev`, que já abre no celular). Não é a casa da amostra para o
  cliente.

## 3. O que cabe numa amostra

### O que a prática diz

- **Pedir amostra grátis é proibido ao cliente na Upwork [F]**: comunidade e moderadores repetem
  que cliente não pode pedir trabalho novo sem pagar; teste deve ser contrato pago
  ([comunidade](https://community.upwork.com/t5/Freelancers/Client-requesting-samples-before-hiring/m-p/865773)).
  [I] Oferecer, por iniciativa própria, um conceito curto não fere isso — é diferente de cumprir um
  pedido de trabalho grátis. Se o *cliente* pedir "faça antes uma página de teste", é sinal de
  alerta (e possível golpe), não de chance boa.
- **Contra o *spec work* [F]**: a AIGA desaconselha trabalho especulativo por qualidade, PI e
  justiça econômica ([AIGA](https://www.aiga.org/resources/aiga-position-on-spec-work)).
  [I] O argumento perde força quando o custo cai a minutos de IA, mas a regra útil fica: o cliente
  não tem direito ao que não pagou, e a amostra não deve ser utilizável como entrega.
- **A favor da demo [F]**: relatos de freelancers dizem que uma demo pequena feita para aquele
  cliente, junto de uma proposta de uma página, persuade mais do que texto; antes era cara demais
  para fazer em todo lead ([dev.to](https://dev.to/solo_operator/i-stopped-writing-proposals-and-started-shipping-demos-5hfj)).
  Guias de proposta citam mockup/print/Loom de 60–90 s como "prova" que aumenta resposta
  ([gigradar](https://gigradar.io/blog/upwork-cover-letter-template)) — fonte de mercado, sem
  método publicado.
- **Clone de marca real [F]**: demo com logo verdadeiro já foi denunciada como phishing
  ([Vercel](https://community.vercel.com/t/question-on-fair-use-and-hobby-plan-suitability-for-demo-commercial-websites-in-portfolio/1769)).

### Regras propostas para a spec [I]

- **Uma página, um conceito**: hero com a proposta de valor do cliente (tirada do pedido), 2–3
  seções que respondem ao que ele pediu (serviços, depoimentos de exemplo, chamada para ação),
  rodapé. Responsiva. HTML/CSS estático (ou Tailwind por CDN), sem build.
- **Não utilizável como entrega**: formulário e botões sem backend; textos do pedido + placeholders
  marcados; imagens genéricas (gradientes, ilustrações SVG, placeholders), **sem o logo do
  cliente** (nome em texto); sem SEO, sem integrações, sem painel.
- **Aviso discreto** fixo: *"Conceito de demonstração preparado para esta proposta — não é o site
  final."* Funciona como a "marca d'água" e evita o problema de phishing.
- **Nada dele na página**: sem nome, e-mail, WhatsApp, GitHub, LinkedIn, "feito por", nem "Whis".
  Também nada de comentário no HTML com isso. É o que faz o link passar pelas regras anti-contato
  (seção 4) e não expõe o usuário.
- **`noindex`** em cabeçalho e `<meta>`.
- **Orçamento de esforço**: uma corrida curta por amostra (ordem de minutos e de uma chamada de
  modelo), e só para as chances boas — não para as de tentar a sorte. O número exato sai do ticket
  07 (cota).
- **Validade**: no ar por um prazo (sugestão: 30 dias, ou até a proposta ser recusada); o Whis
  registra cada amostra (URL, projeto, data) e derruba as vencidas na corrida seguinte.
- **Se o pedido traz o site atual do cliente**: um "antes/depois" da dobra principal costuma
  convencer mais que uma página do zero [I].

### Quando a amostra não faz sentido e o que entra no lugar [I]

| Tipo de freela | Amostra? | No lugar |
|---|---|---|
| Landing page, site institucional, página de produto, redesign | **sim** | — |
| Loja (Shopify/WooCommerce), sistema com telas | parcial: uma tela estática | + plano de execução |
| Bug fix, manutenção, ajuste em WordPress | não | **diagnóstico** (se há URL/repo público: o que provavelmente é e como resolve) + plano em 3–5 passos |
| Integração, API, backend, automação, scraping | não | **plano de execução** (passos, riscos, o que precisa do cliente) |
| App mobile, game, áudio | não (no máximo um print/mock) | plano + portfólio/repos dele que se aproximam |
| Conteúdo, design puro | fora do perfil web; decidir na spec | portfólio |

Portfólio só com o que ele **já fez** (fato, ticket 06); o plano é onde cabe o "consegue fazer
mais um pouco".

## 4. Link externo na proposta, por plataforma

| Plataforma | Link externo na proposta | Contato antes do contrato | Pena | Fonte |
|---|---|---|---|---|
| **Upwork** | **permitido** (portfólio/amostra) | proibido (e-mail, telefone, etc.) | perda de badges até banimento permanente | [F] [comunidade](https://community.upwork.com/t5/Freelancers/Can-I-add-behance-profile-link/m-p/906242), [suporte](https://support.upwork.com/hc/en-us/articles/17995705476627--What-to-do-if-someone-contacts-you-outside-Upwork) |
| **99Freelas** | **permitido só para portfólio** | proibido pedir ou compartilhar | moderação/suspensão | [F] [termos](https://www.99freelas.com.br/termos) (via busca) |
| **Workana** | **ambíguo — tratar como proibido** | proibido até o depósito de garantia | suspensão de propostas (~15 dias) ou conta encerrada | [F] [motivos de suspensão](https://help.workana.com/hc/en-us/articles/360041499134-Reasons-for-suspension-of-bids-and-accounts-closure), [dados de contato](https://help.workana.com/hc/en-us/articles/360041977773-Why-not-to-send-your-contact-details-at-Workana) |

- **Upwork [F]**: a Upwork não proíbe link externo para portfólio ou exemplos; se o link tiver
  contato, o freelancer deve lembrar o cliente de falar só pela Upwork até o contrato. Contato antes
  do contrato viola os Termos.
- **99Freelas [F]**: os termos dizem que não se pode solicitar ou compartilhar dados de contato em
  proposta, pergunta ou chat; *"o link externo só pode ser utilizado com o intuito de apresentar o
  portfólio"*, sem rede social, e-mail ou telefone. [I] Uma amostra feita para o pedido, sem
  contato, é apresentação de portfólio.
- **Workana [F]**: a ajuda oficial lista entre os motivos de suspensão *enviar links externos ao
  cliente — nem Behance é permitido* — e diz que o portfólio deve estar no perfil (importável do
  Behance). Ao mesmo tempo, respostas na central/comunidade dizem que **pode** link externo **sem
  dado de contato** (ex.: *páginas web criadas por você*, apps na loja) e que anexos (currículo, PDF,
  vídeo) são livres se não tiverem contato
  ([comunidade](https://community.workana.com/community//3752346/Que-tipo-de-links-posso-enviar-na-workana),
  [anexos](https://community.workana.com/community//3317250/Nos-anexos-da-proposta-eu-posso-anexar-qualquer-arquivo-ou-somente-os-trabalhos-feitos-na-workana)).
  Há relatos de suspensão por mandar link de portfólio
  ([comunidade](https://community.workana.com/community//3396512/Minha-conta-foi-suspensa-por-enviar-dados-nunca-enviei-e-nem-pedi-apenas-links-para-meu-porf%C3%B3lio-O-que-fa%C3%A7o)).
  - **[I] Regra do Whis para a Workana**: a amostra vai como **anexo** (print em PNG/PDF da página,
    opcionalmente um vídeo curto de rolagem); o link fica no pacote como "opcional — risco de
    suspensão", e **nunca** um link que leve a perfil (por isso `github.io` com usuário é ruim aqui).
    Vale ele perguntar ao suporte da Workana antes da primeira vez.
- **[I] Regra geral**: o pacote marca, por oportunidade, *"link permitido / só anexo / risco"* a
  partir de uma tabela por site mantida no ticket 02. Como ele envia a mão as de chance boa, a
  decisão final é dele.

## 5. O pacote de uma oportunidade com chance boa

### O que as boas propostas têm

- **Upwork, oficial [F]**: personalizar para o pedido e os objetivos do cliente; o primeiro
  parágrafo deve se sustentar sozinho; trazer experiência relevante ou uma amostra; carta curta —
  *três parágrafos curtos*; fechar com um próximo passo claro
  ([Upwork](https://www.upwork.com/resources/how-to-create-a-proposal-that-wins-jobs)).
- **Mercado [F, fontes de ferramentas de proposta, sem método publicado]**: só as 2 primeiras linhas
  aparecem na prévia do cliente; a primeira frase deve citar algo específico do pedido; 100–150
  palavras; uma prova ligada ao resultado que o cliente quer; um próximo passo de baixo atrito
  ([gigradar](https://gigradar.io/blog/upwork-cover-letter-template),
  [aiproposer](https://aiproposer.com/guides/upwork-proposals/upwork-proposal-length)).
- **Sites brasileiros [I]**: Workana e 99Freelas pedem valor, prazo e texto na proposta; o texto
  deve ser em português, sem contato, e se sustentar sem o link (porque, na Workana, o link pode
  nem ir).

### Formato proposto (campos)

```
OPORTUNIDADE
  titulo, site, link_do_pedido, link_para_aplicar
  publicado_ha, propostas_ja_enviadas (concorrência, se o site mostra)
  cliente: nome/país, avaliações, histórico de gasto/contratações, pagamento verificado
  formato: projeto | contínuo          (por hora fica fora, ticket 06)
  orcamento_do_cliente, prazo_do_cliente
  custo_para_enviar (connects/créditos; do ticket 02)

POR QUE CASA          2–3 linhas, cada uma ligada a um fato do vault (o que ele já fez)
O QUE ESTICA          o que ele nunca fez mas faz com IA (permitido na proposta como "consigo")
ALERTAS               golpe?, pede contato fora?, escopo vago, prazo curto demais, pede amostra grátis

PRECO E PRAZO SUGERIDOS
  preço (faixa de mercado → sugestão abaixo/ligeiramente abaixo, ticket 06) e a conta: horas
  estimadas com IA × valor-hora implícito
  prazo, cabendo em trabalho + faculdade

PROPOSTA (pronta para colar, no idioma do pedido)
  linha 1–2: cita o problema do cliente nas palavras dele + o resultado ("Vi que você precisa de X
             para Y; fiz um conceito de como ficaria: <link | em anexo>")
  linha 3–5: como vai fazer, 3 passos, e o que entrega
  linha 6:   uma prova (projeto real dele parecido) — nunca inventada
  linha 7:   preço e prazo
  linha 8:   uma pergunta que puxa resposta ("Prefere tom X ou Y?") 
  limite:    100–200 palavras; sem contato; sem link para perfil
  variante_sem_link (para Workana/anexo)

PERGUNTAS AO CLIENTE  1–2, se o site tem campo de perguntas

AMOSTRA (se web visual; senão PLANO DE EXECUÇÃO / DIAGNÓSTICO)
  url_publica, print (PNG, também é o anexo), o que ela mostra em 1 linha
  regra_do_site: link ok | só anexo | risco
  no_ar_ate (data), id para derrubar

REGISTRO              status (pronto → enviado por ele → resposta), data; vai para o log de ações (ticket 06)
```

- **[I]** No relatório (ticket 04), o que ele vê primeiro é: título, valor, por que casa (1 linha),
  e dois botões — *copiar proposta* e *abrir para aplicar* — com a amostra logo abaixo. O resto
  abre sob demanda.
- **[I]** A proposta afirma só fatos sobre o passado dele; o "consigo fazer" fica no tempo futuro
  e no plano (regra da Q12).

## Fontes principais

- Vercel fair use: https://vercel.com/docs/limits/fair-use-guidelines
- Vercel comunidade (demos): https://community.vercel.com/t/question-on-fair-use-and-hobby-plan-suitability-for-demo-commercial-websites-in-portfolio/1769
- GitHub Pages limites: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
- GitHub REST Pages: https://docs.github.com/en/rest/pages/pages
- Cloudflare Pages limites: https://developers.cloudflare.com/pages/platform/limits/
- Cloudflare direct upload: https://developers.cloudflare.com/pages/get-started/direct-upload/
- Cloudflare preview/noindex: https://developers.cloudflare.com/pages/configuration/preview-deployments/
- Cloudflare Drop: https://developers.cloudflare.com/changelog/post/2026-07-08-cloudflare-drag-and-drop/
- Netlify créditos: https://www.netlify.com/changelog/netlify-pricing-update-introducing-credit-based-plans/
- Netlify zip API: https://developers.netlify.com/guides/deploy-zip-file-to-production-website/
- Netlify uso comercial: https://answers.netlify.com/t/can-we-use-netlify-free-plan-for-commercial-purposes/41545
- Surge: https://surge.sh/docs/platform/plans, https://surge.sh/help/tearing-down-a-project
- Firebase preview channels: https://firebase.google.com/docs/hosting/manage-releases
- Claude Code artifacts: https://code.claude.com/docs/en/artifacts
- Claude suporte (publicar artifacts): https://support.claude.com/en/articles/9547008
- Upwork proposta: https://www.upwork.com/resources/how-to-create-a-proposal-that-wins-jobs
- Upwork contato fora: https://support.upwork.com/hc/en-us/articles/17995705476627--What-to-do-if-someone-contacts-you-outside-Upwork
- Workana suspensão: https://help.workana.com/hc/en-us/articles/360041499134-Reasons-for-suspension-of-bids-and-accounts-closure
- Workana contato: https://help.workana.com/hc/en-us/articles/360041977773-Why-not-to-send-your-contact-details-at-Workana
- 99Freelas termos: https://www.99freelas.com.br/termos
- AIGA spec work: https://www.aiga.org/resources/aiga-position-on-spec-work
