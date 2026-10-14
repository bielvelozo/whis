# Marcadores das páginas logadas

Coletado em 2026-10-14 pelo Chrome dele (Claude in Chrome, só leitura). Fixtures em `tests/fixtures/cacada_logada/`.

Como as fixtures foram limpas: sem `script`, `style`, `svg`, `img`, `iframe`, comentários; só ficam os atributos `class` (até 4–6 classes, sem `ng-*`), `id`, `href`, `name`, `type`, `value`, `title`, `role`, `aria-label`, `for`, `datetime`, `action`, `method` e `data-*` curtos (`data-status`, `data-type`, `data-color`, `data-size`, `data-id`, `data-content`...). Elementos sem texto (ícones) somem e `div`/`span` sem atributo com um filho só são colapsados. Por isso: casar por **texto + tag/classe estável**, nunca por caminho de DOM. As páginas do Freelancer.com são Angular renderizado (o HTML cru do servidor logado não é igual); as deslogadas vieram de `curl.exe` sem cookie. Nas fixtures logadas da 99Freelas a lista de conversas privadas do header (`li.mensagem-item`) foi tirada.

## Freelancer.com

| O quê | Marcador | Fixture |
|---|---|---|
| Logado | `<app-logged-in-shell>`; no header `app-navigation app-user-card fl-username p.Username-userId` com `@gabrielvelozodev` e `p.UserCard-balance` (`$0,00 USD`) | `freelancer_aberto.html` (todos os `freelancer_*` logados) |
| Deslogado | `<app-logged-out-shell>`; links `a[href^="/login?next="]` "Log In" e `/signup` "Sign Up"; página do projeto vem como `app-project-view-logged-out` (em inglês: "Project ID: N", "N proposals", "Open for bidding") | `freelancer_deslogado.html` |
| Projeto aberto | `fl-project-status[data-status="open"]` com texto "Aberto"; "O período para ofertar termina em <fl-relative-time>" | `freelancer_aberto.html` |
| Número de propostas (logado) | `app-project-summary`: `<p>Ofertas</p><p class="text-body-24 ...">113</p>`; oferta média em `p.AveragePrice` | `freelancer_aberto.html` (113), `freelancer_selecionados.html` (103), `freelancer_ja_ofertou.html` (98) |
| ID do projeto | `p` com "ID do Projeto: 40761662" (aparece 2×, mobile e desktop) em `.ProjectDetailsFooter` | `freelancer_aberto.html` |
| Selecionados + saldo | `fl-banner-alert[data-type="warning"]` com `<p class="font-bold ...">Este projeto está aberto apenas a freelancers selecionados</p>` e "Para poder ofertar, mantenha um saldo mínimo de US$20 ou equivalente." | `freelancer_selecionados.html` |
| Lances restantes | `app-insights-bid-summary-widget .ReplenishmentData`: "<span>0 ofertas</span> restantes de 6"; também `p.RemainingBids` "0/6 restantes" (bloco mobile em `app-employer-info`) | todos os logados |
| Sem lances | `fl-banner-alert[data-type="warning"]` "Parece que você está sem ofertas. Obtenha mais ofertas agora comprando um Pacote de Ofertas ou aprimorando seu Plano." — **com 0 lances o formulário de oferta não aparece**, então não há fixture do formulário | `freelancer_aberto.html` |
| Já ofertou | O único marcador validado é a aba `/proposals`: `h3` "Sua proposta" + `p.BidRank` "Sua proposta foi ranqueada em 60 entre 98 propostas." + `a[href^="/u/gabrielvelozodev?projectId="]` dentro de `app-bid-card` + botões "Retirar"/"Editar". Na aba Detalhes, com 0 lances, só some o banner "sem ofertas"; com lances sobrando essa aba pode mostrar outra coisa (não visto) | `freelancer_ja_ofertou.html`, `freelancer_ja_ofertou_propostas.html` |
| Dono/cliente | A página logada **não mostra o nome de usuário do cliente**: `app-employer-info` ("Sobre o Cliente") traz cidade, país, nota (`fl-rating .ValueBlock`), nº de avaliações (`fl-review-count`), "Membro desde 23 de dez. de 2016" e verificações. Para "mesmo cliente + mesmo título" usar o `owner_id` da API (já usada) ou a combinação cidade+país+membro desde | `freelancer_aberto.html` |
| Habilidades | `app-project-details-skills a[href^="/jobs/"]` | `freelancer_aberto.html` |

URL: `https://www.freelancer.com/projects/<skill>/<slug>` redireciona para `/details`; a lista de propostas fica em `/proposals`.

## 99Freelas

| O quê | Marcador | Fixture |
|---|---|---|
| Logado | `header.header.freelancer` + `div.header-menu-logged`; `span.user-name`/`p.user-name` "Gabriel Velozo"; menu com `/connections/stock` ("Estoque de conexões") | `99freelas_aberto.html` e demais logados |
| Deslogado | `header.header` (sem `freelancer`), links `a[href="/login"]` "Login" e `/register` "Cadastre-se" | `99freelas_deslogado.html` |
| Aberto, sem proposta | `a.btn.blue.clickable[href^="/project/bid/"]` "Enviar proposta"; sem `button.btn.status-*` | `99freelas_aberto.html`, `99freelas_deslogado.html` |
| Cancelado | `button.btn.status-5` "Cancelado"; sem link `/project/bid/` | `99freelas_cancelado.html` |
| Freelancer escolhido | `button.btn.status-3` "Em andamento"; sem link `/project/bid/`; na lista de propostas `span.status-proposta.aceita.show` "Aceita" (as variantes sem `show` são modelos escondidos em toda proposta, ignorar) | `99freelas_escolhido.html` |
| Já propôs | o botão vira `a.btn.blue.clickable[href^="/project/bid/"]` **"Melhorar proposta"** | `99freelas_ja_propos.html` |
| Dados do projeto | tabela `.info-adicionais` com `<th>Propostas:</th><td>200</td>`, "Interessados:", "Tempo restante:" (`td.datetime-restante`), "Valor Mínimo:" (`td.valor-minimo`), "Visibilidade:", "Orçamento:" | `99freelas_aberto.html` |
| Cliente | `.info-usuario.cliente .info-usuario-nome a[href^="/user/"] span.name` | `99freelas_aberto.html` |
| Custo em conexões | no formulário `/project/bid/<slug>`: "Esta proposta requer <b>1 conexão</b>. Após enviar esta proposta, você terá <b>14 conexões</b> restantes." e "(Oferta mínima: R$&nbsp;50,00)" | `99freelas_bid.html` |
| Exclusivo (assinante) | `/project/bid/<slug>` de projeto com menos de ~24 h abre "Não foi possível acessar a página" com `div.content-box-message.fail` "Para enviar propostas em projetos exclusivos, assine um de nossos planos pagos ou aguarde até que ele seja liberado para todos os freelancers." | `99freelas_bid_exclusivo.html` |

Listagem logada (`99freelas_listagem.html`, `https://www.99freelas.com.br/projects?categoria=web-mobile-e-software&page=2`): `ul.result-list > li.result-item[data-id]`, título em `h1.title a[href^="/project/"]`, `p.item-text.information` com subcategoria | nível | "Publicado: <b class="datetime">" | "Tempo restante: <b class="datetime-restante">" | "Propostas: <b>N</b>" | "Interessados: <b>N</b>", descrição em `.item-text.description`, cliente em `p.item-text.client`. O ícone de exclusivo da listagem sumiu na limpeza (elemento sem texto); o exclusivo continua sendo lido na página do projeto. Atenção: o header logado também tem uma lista `li.novo-projeto-item[data-id]` (notificações de projetos novos), que não é a listagem.

## VintePila

| O quê | Marcador | Fixture |
|---|---|---|
| Logado | header com `span.vp-mc-g-nome` "Gabriel V." | `vintepila_listagem.html`, `vintepila_inelegivel*.html` |
| Deslogado | `a#__entrar` "Entrar" (href para login com `redirect_to`) | `vintepila_deslogado.html` |
| Inelegível | `div.ui.small.disabled.button.btn_tooltip` "Inelegível" | `vintepila_inelegivel.html`, `vintepila_inelegivel_0de5.html` |
| **Motivo do inelegível** | não é só 5/5: **toda** página mostra Inelegível porque a conta dele não tem serviço ativo. O motivo está só num script inline: `$(".btn_tooltip").popup({... content : 'Você precisa ter pelo menos um serviço ativo para fazer propostas.'})` (mantido de propósito no fim das duas fixtures) | `vintepila_inelegivel_0de5.html` (Candidatos 0/5 e ainda inelegível) |
| Candidatos | texto "Candidatos (5/5)" na página; nos cards `span[data-content^="Número de candidatos"]` com o número | `vintepila_inelegivel.html`, `vintepila_listagem.html` |
| Ofertas restantes | `a.ui.basic.left.label.bid_tooltip` ao lado do botão (ex.: "5"); tooltip no script: "Quantidade de ofertas restantes. O número de vendas será convertido em tokens de candidaturas para enviar ofertas." | `vintepila_inelegivel.html` |
| Preço | card: `span#project-price` "R$ 50,00 - R$ 180,00"; página: faixa + `span[data-content="Valor médio das ofertas recebidas"]` | `vintepila_listagem.html`, `vintepila_inelegivel.html` |
| Prazo | `span[data-content^="Prazo máximo estipulado"]` "20 DIAS" | idem |
| ID | card: `a.header[title="Project ID: 5550312"]` e `<small>#5550312</small>`, `div.item.h_p_<id>`; página: "Projeto ID : 5546692" | idem |

Listagem: `https://www.vintepila.com.br/trabalhos-freelance/` (paginação `?page=N`). **Não há filtro de categoria** — o "Filtros" é só ordenação (Mais recentes / Mais antigos); `?categoria=programacao` é ignorado (mesmos IDs na mesma ordem) e `/categorias/programacao-tecnologia/` é catálogo de serviços (gigs), não de pedidos. Cada card: `div.ui.segment > div.ui.unstackable.items > div.item.h_p_<id> > div.content` com `a.header` (título/link), `span#project-price`, `.meta` (rótulos URGENTE/PRO), `.description p`, `.extra` (publicado, prazo, candidatos) e `a#detalhesbtn` "VER DETALHES". Nas páginas 1–5 de hoje quase todos tinham 5 candidatos; com 0–4: `entrar-no-fivem-...`, `cadastrar-fanpage-...` (0), `procuro-profissional-comercial-...` (4), `urgente-modelagem-impressao-3d-...` (3). Não existe fixture "elegível": enquanto ele não tiver um serviço ativo, nenhum projeto é elegível.

## freelancer.com.br

**No Chrome dele de hoje o site está deslogado** (header com "Conecte-se" / "Se inscrever"), então as duas fixtures são deslogadas e não há fixture da tela de plano pago.

| O quê | Marcador | Fixture |
|---|---|---|
| Deslogado | `button.header-login-btn` "Conecte-se", `button.subscribe-btn` "Se inscrever", `form#headerLoginForm[action$="/conecte-se"]` | `freelancerbr_projeto_deslogado.html`, `freelancerbr_listagem_deslogado.html` |
| Logado | não coletado (precisa ele entrar de novo) | — |
| Status | `li.project-meta-row` com "Status do projeto" → `div.project-status.open` "Aberto" | `freelancerbr_projeto_deslogado.html` |
| Interessados | `li.project-meta-row` "Interessado" → `span.font-medium` "5"; na listagem `span.sub-text` "6 interessados" | ambas |
| Plano pago | não clicar em "Estou interessado". Visto em 13/10: clicado logado, leva a `https://freelancer.com.br/account/upgrade?origin=...&trigger=bid_project_no_product` (R$ 75 / 3 meses). Detectar pelo redirecionamento para `/account/upgrade` com `trigger=bid_project_no_product` | — |

Listagem: `https://freelancer.com.br/projetos` com `form.assignments-search-form` (GET): `category[]` (1 = Website and Apps, 106 Website Maintenance, 108 E-Commerce, 110 Front-end Development, 371 App Development, 387 Web Applications, 467 Web Design, 468 Back-end Development, 469 Wordpress), `budgetType`, `status` (`statusOpenProjects`, `postedSince-3`...). Links de projeto: `/projetos/<categoria>/<subcategoria>/<slug>-<ID>` (ex.: `/projetos/site-e-aplicativos/...`, `/projetos/softwares-e-sistemas/...`).

## URLs de listagem úteis para a busca logada

- Freelancer.com: a busca segue pela API (os projetos logados só servem para conferir cada um).
- 99Freelas: `https://www.99freelas.com.br/projects?categoria=web-mobile-e-software` (`&page=N`).
- VintePila: `https://www.vintepila.com.br/trabalhos-freelance/?page=N` (sem filtro de categoria).
- freelancer.com.br: `https://freelancer.com.br/projetos?category[]=1` (montado a partir do formulário GET, não testado: o site devolve 403 para `curl.exe`, então só dá para conferir pelo navegador; subcategorias acima).
