# Research 08 — O LinkedIn

Levantado em 2026-10-02.

Pergunta do [ticket 08](../issues/08-o-linkedin.md): como o Whis faz cada coisa no LinkedIn (analisar
o perfil, escrever posts, publicar, mudar o perfil e aplicar, ler vagas) e com que risco para a conta
principal dele, sabendo que **lá nada é automático** porque os colegas o seguem.

**Como ler**: **[fato]** é o que está na fonte citada ou foi medido aqui; **[inferência]** é leitura
do agente; **[de memória]** é conhecimento anterior que não pôde ser conferido nesta sessão.

**Limite desta pesquisa**: a rede desta sessão bloqueia `learn.microsoft.com`, `linkedin.com` e quase
toda a web; só o GitHub abriu. A documentação oficial da Microsoft foi lida pelos **trechos que o
buscador devolve das próprias páginas oficiais** (links abaixo), não abrindo a página. A skill e o
JobSpy foram clonados e lidos inteiros; o humanizador foi rodado num texto em português. Nada foi
testado contra o LinkedIn de verdade. Os pontos marcados **conferir** se resolvem no primeiro dia da
entrega 3, ao criar o app.

## Resumo

- **Analisar o perfil: ele exporta, o Whis lê.** A API não entrega o perfil: o escopo aberto
  `profile` dá só nome, foto e e-mail, e a API completa só existe na Europa [fato]. O caminho limpo é
  o **"Baixar seus dados"** do LinkedIn (o pacote parcial, em uns 10 minutos, já traz Profile,
  Positions, Education e Skills em CSV) somado ao **texto colado** do título e do "Sobre". O Whis
  cruza isso com o vault. Risco zero. Navegador logado só para ler o próprio perfil não compensa.
- **Escrever: copiar a skill para o repositório, sem instalar.** Ela é boa no método (ganchos,
  rubrica, "nunca inventa número", sai só o texto para colar) e é MIT, mas é **toda em inglês e
  feita para quem vende serviço**. O humanizador estraga português (troca "crucial" por "important")
  e o detector não reconhece pronome nem palavra acentuada [fato, medido]. O Whis já roda o Claude
  com `skills=[]` e `setting_sources=[]` [fato]: o natural é **portar os prompts** de `li-post` e
  `li-profile` para `prompts.py` em português, reaproveitar só os passes **invisível + tipográfico**
  de `humanize.py` como função Python testada e escrever um léxico de clichês em português.
- **Publicar: pela API oficial, grátis e sem navegador, só no clique dele.** *Share on LinkedIn*
  (`w_member_social`) + *Sign In with LinkedIn using OpenID Connect* são **self-serve, sem revisão**
  [fato], e o README da skill está errado ao dizer o contrário. São 150 chamadas por membro por dia.
  O token dura **60 dias e não tem refresh token** para app self-serve [fato]. Então de dois em dois
  meses ele refaz o login (`python -m whis linkedin-login`, como o `x-login`). Texto, link, imagem e,
  pela Posts API, PDF em carrossel e várias imagens. O post pode ser apagado pela API, e isso dá o
  "desfazer" do registro.
- **Mudar o perfil: o Whis prepara, ele cola.** A API de edição de perfil é restrita a parceiros
  aprovados [fato]. Automatizar pelo navegador fere o User Agreement 8.2 na conta que mais importa:
  **não fazer.** O Whis entrega cada seção pronta (título, "Sobre", experiência), na ordem de mais
  pontos perdidos, com o link da tela de edição. Antes, ele **desliga "Compartilhar mudanças de
  emprego…"** para a rede não ser avisada.
- **Aplicar (Easy Apply): o Whis prepara, ele clica.** Não existe API do lado do candidato: o Apply
  Connect é só para ATS parceiro [fato]. Robôs de Easy Apply são o caso clássico de conta restrita:
  o criador do AIHawk foi banido em 2024, e em 2026 houve o banimento da HeyReach e restrições em
  cerca de 40% das contas que usavam ferramentas na nuvem, segundo um fornecedor concorrente [fato,
  com fontes interessadas]. O LinkedIn escaneia 6.236 extensões do Chrome em cada página
  (*BrowserGate*, abril de 2026) [fato]. Na prática: vaga do LinkedIn com chance boa vai para o
  relatório com link, respostas prontas e currículo ajustado. As de tentar a sorte do LinkedIn ficam
  de fora ou só são listadas, como ele decidiu.
- **Ler vagas: pela busca pública, sem login, nunca pela conta dele.** O endpoint de visitante
  `jobs-guest/jobs/api/seeMoreJobPostings/search` segue no ar em 2026 [fato] e traz título, empresa,
  local, data e link. Pela página pública da vaga vêm também a descrição, a senioridade, o regime e
  a área [fato, código do JobSpy]. Filtra por remoto, data, Easy Apply e empresa. Bloqueia (429) por
  volta da 10ª página por IP [fato, JobSpy]. Para uma corrida por mês, com poucas buscas e pausas de
  3 a 7 s, cabe [inferência]. Nenhuma conta fica exposta. Ler logado (como o X) daria mais, como
  número de candidatos e vagas recomendadas, mas põe a conta dele em jogo **por pouco ganho**.
- **Discrição: os três sinais que os colegas veem.** (1) **Open to Work**: nunca, nem "só
  recrutadores", porque o LinkedIn diz que não garante esconder do recrutador da empresa atual
  [fato]. (2) **Avisar a rede sobre mudanças de perfil**: desligar antes de qualquer edição de
  emprego ou formação, porque mudança de emprego vai ao feed em até 2 h [fato]. (3) **Ritmo e tema**:
  posts sobre "novos desafios", muitas mudanças de perfil na mesma semana ou um "Prestando serviços"
  aparecendo de repente leem como busca [inferência]. Comentários e curtidas também aparecem no feed
  dos colegas.
- **Se o navegador logado entrar no LinkedIn, vira ADR** (como o 0003 do X). Esta pesquisa
  recomenda **não** entrar: tudo o que ele pediu cabe em API oficial, exportação, busca pública e
  "o Whis prepara, ele clica".

## 1. A skill indicada (linkedin-agent-skill)

Fonte: [github.com/Jakeschincariol/linkedin-agent-skill](https://github.com/Jakeschincariol/linkedin-agent-skill),
clonada em 2026-10-02, commit `add2c23` de 2026-09-07, o **único commit** ("v1.0"). Lida inteira:
README, as 11 `SKILL.md`, `templates/voice.md`, `li-human/humanize.py`, `detect.py`, `slop.json`,
`li-profile/rubric.json`, `li-post/hooks.json` e `.claude-plugin/*.json`.

### O que é [fato]

- Onze skills no formato de Claude Code (`skills/li-*/SKILL.md` com front-matter `name`/`description`)
  e um plugin de marketplace (`.claude-plugin/`). Instalação sugerida: `cp -r skills/li-* ~/.claude/skills/`
  ou `/plugin install linkedin-agent`.
- **Licença MIT**, "Copyright (c) 2026 Jake Schincariol". Pode copiar, mudar e redistribuir desde que
  mantenha o aviso.
- **Não publica, de propósito**: toda skill termina num bloco para copiar e colar. Também não loga, não
  raspa e não lê caixa de entrada; pede ao usuário que cole o texto ou mande print.
- **Não inventa**: número que falta vira `{{your number}}` com aviso.
- Tudo lê `~/.claude/linkedin/voice.md` (o perfil de voz) e algumas escrevem `~/.claude/linkedin/log.md`
  e `plan.md`.

### As onze, uma a uma

| skill | o que faz | entrada que pede | serve ao Whis? [inferência] |
| --- | --- | --- | --- |
| `li-post` | Uma ideia vira post: três ganchos de 21 fórmulas (`hooks.json`), um rascunho de 900–1.300 caracteres, passa por `li-human`, imprime o bloco final e "POST READY". Regras: uma ideia por post, número no lugar de adjetivo, no máximo 3 hashtags, link no 1º comentário. | `voice.md` (ou três posts antigos dele), a ideia, e um fato específico (o que aconteceu, com quem, quanto custou/rendeu). | **Sim, é o núcleo.** As ideias saem do vault (diário, daily, o que ele construiu, como o próprio Whis). |
| `li-profile` | Nota de 0 a 100 numa rubrica de 12 itens (`rubric.json`) e reescreve na ordem do que mais perdeu ponto: título (220 caracteres), 2 primeiras linhas do "Sobre", corpo do "Sobre", destaques, experiência, banner. Reavalia no fim e mostra a diferença. | Título, "Sobre", cargo atual e as duas últimas experiências **colados**; se tem banner/destaques. "Não entre no LinkedIn em nome dele." | **Sim, adaptada.** A rubrica é de quem vende serviço ("quem você ajuda", "link de agenda"); para dev empregado buscando discretamente, o peso tem de ir para palavras que recrutador busca (stack, senioridade, local/remoto) e tirar a chamada para contratar. |
| `li-human` | Dois scripts Python sem dependência: `humanize.py` (apaga caracteres invisíveis, troca travessão por vírgula e aspas curvas por retas, troca 113 clichês por palavras simples, aponta estruturas como "não é só X, é Y") e `detect.py` (5 notas de 0 a 100: variação de frase, concretude, densidade de clichê, "impressão digital" tipográfica, voz). | O rascunho em arquivo ou stdin. | **Em parte** (ver "Idioma" abaixo). |
| `li-plan` | Plano da semana: 4 posts (prova, opinião, ensino, história, oferta), horários, e 10 pessoas para interagir (5 alcance, 3 pares, 2 compradores). | `voice.md`, `log.md`, temas, o que aconteceu na semana, lista de pessoas. | Pouco. A lógica de "comprador" é de venda; "interagir 20 min por dia" é visível aos colegas. Talvez só a cadência. |
| `li-carousel` | Carrossel em PDF: 8–12 slides, capa de 6 palavras, recapitulação, CTA; gera HTML 1080×1350 e imprime em PDF. | A ideia com sequência (passos, antes/depois). | Talvez, mais tarde. A API aceita PDF (seção 2). |
| `li-comment` | Comentário em post alheio: 9 tipos (dado, caso que falta, discordância respeitosa…), 2 opções. | O texto do post colado. | Pouco; ele comenta à mão. |
| `li-reply` | Responde comentários no post dele, triados em lead/substância/par/apoio/ruído. | Os comentários colados. | Pouco. |
| `li-repurpose` | Um conteúdo longo (vídeo, newsletter, transcrição) vira uma semana de posts. | O texto/transcrição. | Talvez: uma reunião do Granola ou um texto do diário vira post. |
| `li-dm` | Nota de convite (200 caracteres), 1ª mensagem e 2 lembretes. "No máximo 20 convites por dia." | Quem, o motivo, o que ele quer. | Talvez, para falar com recrutador de vaga com chance boa, mas ele envia. |
| `li-inbox` | Tria mensagens em lead/recrutador/par/pedido/spam e escreve respostas. | Mensagens coladas. | Talvez, para recrutadores (ver "Not yet specified" do mapa). |
| `li-audit` | Pós-morte dos posts publicados: taxa de engajamento, razão de comentários, alcance sobre seguidores. | Export de analytics (CSV) ou prints. | Mais tarde, quando houver posts. |

### Qualidade [inferência, com base no que foi lido]

- **O método é bom e alinhado ao Whis**: só afirma o que o usuário deu, para em `{{lacuna}}`, entrega
  texto e não age. É a regra da Q12 ("o que ele fez não se inventa").
- **Honesta sobre o detector**: diz que são heurísticas locais, que não são GPTZero e que não prometem
  "indetectável".
- **Fresca e sem histórico**: um commit, v1.0, de 25 dias atrás. Não há testes. Não é dependência para
  atualizar; é material de partida.
- **Erra num fato central**: o README diz que *"There is no official API for posting to a personal
  profile without an approved partner app"*. A documentação oficial diz que `w_member_social` é
  self-serve (seção 2). Ou seja: a escolha de não publicar é boa, mas o motivo dado está errado.
- **Público-alvo**: consultor/agência que vende. Exemplos em dólar, "buyers", "offer", "booking link".
  Para ele (dev empregado, discreto) o tom de venda é inadequado e pode até sinalizar "estou
  disponível".

### Idioma: serve para post em português? [fato, medido nesta sessão]

Rodei `humanize.py` e `detect.py` num post curto em português com um travessão e quatro clichês
("crucial", "robusta", "alavanca", "ecossistema"):

- **O léxico estraga o texto**: "é crucial notar" virou **"é important notar"**, porque "crucial"
  existe nas duas línguas e a troca é para o inglês. "robusta", "alavanca" e "ecossistema" passaram,
  porque o léxico só tem formas em inglês.
- **O detector é cego para português**: `WORD_RE = [A-Za-z']+` quebra palavras acentuadas; os pronomes
  contados são `i|me|my|we|you…` e as contrações são as do inglês. O texto, escrito em primeira pessoa
  ("eu levei", "eu parei"), tirou **VOICE 30/100, "0.0 personal pronouns"**, e o veredito ficou em
  REVIEW por causa disso.
- **O que funciona em qualquer língua**: o passe de caracteres invisíveis e o tipográfico (travessão,
  aspas curvas, reticências). O travessão virou vírgula corretamente.
- Os prompts (`SKILL.md`) estão em inglês, mas o Claude escreve em português se pedido; a perda está
  nas regras específicas de inglês (contrações, "Thoughts?") e nos 21 ganchos, cujos exemplos são
  americanos.

### Como o Whis reaproveitaria [inferência]

O Whis **não carrega skills**: todas as chamadas ao Agent SDK passam `skills=[]`, `setting_sources=[]`,
`strict_mcp_config=True` e um `system_prompt` próprio
([`src/whis/jornal_claude.py`](../../../src/whis/jornal_claude.py), `resumo_dia_claude.py`,
`busca_claude.py`). As três opções:

1. **Instalar como skill do Agent SDK** (copiar para `.claude/skills/` e abrir `setting_sources`):
   quebra o padrão da casa (o Whis decide o que o Claude vê) e traz junto as regras em inglês e o tom
   de venda. **Não.**
2. **Copiar o repositório inteiro para dentro do Whis**: muito do que vem não serve (li-dm, li-inbox,
   li-plan de venda). **Não.**
3. **Portar o que serve, em português, com crédito** (recomendado):
   - `li-post` e `li-profile` viram prompts em `prompts.py`, reescritos em português para um dev, com
     as regras boas mantidas (uma ideia, número real, `{{lacuna}}`, link no 1º comentário, até 3
     hashtags, tamanho, "nunca publica sem o sim").
   - `rubric.json` vira uma rubrica própria (mesma ideia de 100 pontos), com pesos de quem quer ser
     **achado por recrutador**, não de quem vende.
   - De `humanize.py`, só `pass_invisible` e `pass_typographic`, como funções Python com testes
     (o Whis já testa parsers com fixtures). O léxico vira `cliches.json` em português ("alavancar",
     "robusto", "ecossistema", "jornada", "no cenário atual", "vale ressaltar", "em suma",
     "potencializar"…), a escrever e ajustar com ele.
   - `detect.py` fica de fora, ou é reescrito para português. É heurística; o que importa é ele ler
     e aprovar.
   - `voice.md` é **gerado pelo Whis** a partir do que ele escreve (diário, mensagens dele), e ele
     corrige. É o que a própria skill sugere ("paste three of your own posts").
   - Crédito: manter o aviso MIT no topo dos arquivos portados (exigência da licença).

## 2. Publicar no perfil pessoal pela API oficial

### Os dois produtos self-serve [fato]

- **Share on LinkedIn** dá o escopo `w_member_social` ("Post, comment, and like posts on behalf of an
  authenticated member"). Adiciona-se no Developer Portal → app → aba *Products*. É self-serve: marcar
  e aceitar os termos, sem conversa de revisão.
  [Share on LinkedIn](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin),
  [Getting Access](https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access).
- **Sign In with LinkedIn using OpenID Connect** dá `openid`, `profile` e `email`. Serve para descobrir
  o `sub` (o id da pessoa) e montar o autor `urn:li:person:{sub}` do post.
  [Sign In with LinkedIn using OpenID Connect](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2).
- Relato de terceiros: esses dois produtos não convivem no mesmo app com o *Community Management
  API* (o de páginas de empresa), que não é necessário aqui
  ([postiz-app #1582](https://github.com/gitroomhq/postiz-app/issues/1582)).

### Precisa de Company Page para criar o app?

- **[fato]** O formulário de criação de app pede uma **LinkedIn Page** associada, e a verificação
  pela página é exigida para produtos de marketing (Conversions, Lead Sync)
  ([Associate an app with a LinkedIn Page](https://www.linkedin.com/help/linkedin/answer/a548360),
  [Getting Access to Conversions API](https://learn.microsoft.com/en-us/linkedin/marketing/conversions/getting-access-conversions)).
- **[fato, fonte secundária]** Para projeto individual existe a opção **"Default Company Page for
  Individual Developer"** no campo da página (citada em guias de 2025–2026 no resultado de busca;
  não foi possível abrir a página).
- **[inferência] Conferir ao criar o app.** Se a opção padrão não aparecer, ele cria uma página neutra
  (por exemplo "Whis"). Criar página não gera post no feed da rede [de memória], mas a página fica
  pública e ligada a ele como administrador. Para os produtos self-serve, a página **não precisa ser
  verificada** [inferência: a verificação só aparece nos produtos que passam por revisão].

### Token: 60 dias, sem refresh para self-serve [fato]

- "All access tokens are issued with a 60-day lifespan."
  [Authorization Code Flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow).
- **Refresh token programático só para parceiros aprovados**, como os do Marketing Developer
  Platform: refresh de 365 dias, access de 60 dias.
  [Refresh Tokens with OAuth 2.0](https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens).
  App self-serve recebe só o `access_token`, sem `refresh_token`; no dia 60 o membro entra de novo
  ([OpenTweet, set/2026](https://opentweet.io/answers/linkedin-api-token-expires-60-days),
  [Nango](https://nango.dev/blog/linkedin-oauth-refresh-token-invalid-grant)).
- **Consequência para o Whis [inferência]**: um comando `python -m whis linkedin-login` (como o
  `x-login`) a cada ~60 dias. O Whis guarda `expires_in`, avisa uma semana antes (toast/jornal, como o
  "login vencido" do X) e, se o token venceu, a publicação aprovada espera o novo login em vez de
  falhar calada. Se ele ainda estiver logado no navegador e já tiver autorizado o app, o LinkedIn
  costuma pular a tela de consentimento [de memória].

### OAuth num app desktop local [fato + inferência]

- É o fluxo de 3 pernas padrão: abre-se `https://www.linkedin.com/oauth/v2/authorization` com
  `response_type=code`, `client_id`, `redirect_uri`, `state` e
  `scope=openid profile w_member_social`. O LinkedIn volta ao `redirect_uri` com `code`, trocado por
  token em `/oauth/v2/accessToken` com o `client_secret`. O `redirect_uri` tem de bater **exatamente**
  com um dos cadastrados (caso, protocolo e porta)
  ([Authorization Code Flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow)).
  O código vale pouco tempo: troca-se na hora.
- **`http://localhost:PORTA/callback` é aceito** no portal; vários projetos o usam
  ([robotsix-linkedin](https://github.com/damien-robotsix/robotsix-linkedin), guias no resultado de
  busca). Como a correspondência é exata, a porta é **fixa** (por exemplo 8765) e o Whis sobe um
  servidor HTTP só durante o login.
- **PKCE sem segredo** (fluxo "native client", servidor em loopback com porta aleatória) **precisa ser
  ligado pelo contato do LinkedIn**, ou seja, não é self-serve
  ([Authorization Code Flow — Native](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow-native)).
  Então o `client_secret` fica no PC dele, no config fora do repositório, como os outros segredos
  [inferência; aceitável num app de um usuário só que roda local, ADR 0001].
- O login abre o **navegador padrão dele** (sem Playwright): nada de automação na página do LinkedIn.

### Posts API ou ugcPosts? [fato]

- A página do *Share on LinkedIn* ainda documenta `POST https://api.linkedin.com/v2/ugcPosts` com
  `shareMediaCategory` = `NONE` (texto), `ARTICLE` (link) ou `IMAGE`, e o upload de imagem em três
  passos (`/v2/assets?action=registerUpload` com a receita `urn:li:digitalmediaRecipe:feedshare-image`,
  envio do binário, post referenciando o `asset`)
  ([Share on LinkedIn](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin)).
- A **Posts API** (`POST https://api.linkedin.com/rest/posts`, cabeçalhos `LinkedIn-Version: AAAAMM` e
  `X-Restli-Protocol-Version: 2.0.0`) "replaces the ugcPosts API". O ugcPosts aparece como **Legacy**
  ([Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api),
  [UGC Post API (Legacy)](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/ugc-post-api)).
  As APIs v2 sem versão tiveram o prazo de descontinuação estendido até julho de 2028 (trecho de
  release notes no resultado de busca).
- A Posts API **aceita `w_member_social` para post pessoal**, sem Community Management, segundo guias
  e integrações de 2026 ([Blotato](https://www.blotato.com/blog/linkedin-posting-api),
  [postizn #9](https://github.com/nilamadhab47/postizn/issues/9)). **Recomendação [inferência]**: usar
  `/rest/posts` e, se o primeiro teste devolver 403, cair para `/v2/ugcPosts`, que é o que a página do
  self-serve documenta.
- **Visibilidade**: o post leva `visibility` = `PUBLIC` ou `CONNECTIONS` [de memória, conferir]. Os
  colegas são conexões, então nenhum dos dois esconde deles.
- **Apagar**: `DELETE /rest/posts/{urn}` com o mesmo escopo [de memória, conferir]. Dá o "desfazer"
  do registro de ações externas (ticket 06).

### Imagem, carrossel, vídeo [fato]

- **Imagem**: Images API (`/rest/images?action=initializeUpload`) na Posts API, ou `registerUpload` no
  ugcPosts. O upload tem de terminar antes de criar o post, senão o post fica invisível
  ([Image API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api)).
- **Várias imagens**: MultiImage API
  ([MultiImage](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/multiimage-post-api)).
- **Carrossel em PDF ("documento")**: Documents API (`/rest/documents?action=initializeUpload`), com
  PDF, PPT(X) ou DOC(X) de até 100 MB e 300 páginas, que vira `urn:li:document:{id}` no post
  ([Documents API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/documents-api)).
  Funcionar com `w_member_social` em app self-serve é **[inferência — conferir]**: a página está na
  seção de Community Management.

### Limites [fato]

- *Share on LinkedIn*: **150 chamadas por membro por dia** e 100.000 por app por dia, zerando à
  meia-noite UTC ([Rate Limits](https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/rate-limits)).
  Para quem publica uns poucos posts por semana, sobra.
- O post pela API é um post normal dele: aparece no feed dos colegas como qualquer outro.

### Risco [inferência]

Publicar pela API oficial, com o escopo que o LinkedIn oferece para isso, um post por vez, aprovado
por ele, **não fere o User Agreement**: é o uso que o produto prevê. O risco que sobra é de conteúdo
(o que o post diz), não de conta.

## 3. Analisar o perfil: de onde vem o texto

| caminho | o que traz | risco | veredito [inferência] |
| --- | --- | --- | --- |
| **API, `openid profile email`** | `sub`, `name`, `given_name`, `family_name`, `picture`, `locale`, `email` [fato] ([OIDC](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2)). Sem título, "Sobre" ou experiência. | nenhum | Só serve para o autor do post. |
| **API de perfil completo** (`r_basicprofile`, `r_fullprofile`) | Fechada; só programas de parceiro [fato] ([Full Profile Fields (Closed)](https://learn.microsoft.com/en-us/linkedin/shared/references/v2/profile/full-profile)). | — | Fora. |
| **Member Data Portability API** (DMA) | O perfil inteiro em 17 domínios, por API oficial, **só para membros do EEE e da Suíça** [fato] ([LinkedIn Help](https://www.linkedin.com/help/linkedin/answer/a6214075), [NetEye, 03/2026](https://www.neteye-blog.com/blog/2026/03/18/thanks-eu-linkedin-finally-gave-me-my-cv-data/)). | — | Fora: ele está no Brasil. |
| **"Baixar seus dados"** (Configurações → Privacidade dos dados) | Pacote parcial em ~10 min (Profile, Positions, Education, Skills, Certifications, Recommendations, Shares) ou completo em até 24 h, em CSV [fato] ([Help 50191](https://www.linkedin.com/help/linkedin/answer/50191)). | nenhum | **Base da análise.** Ele baixa o zip; o Whis lê os CSVs da pasta de Downloads. |
| **Texto colado / print** | O que ele vê na tela, inclusive título, "Sobre", destaques, banner. | nenhum | **Complemento**: a skill pede exatamente isso. O "Sobre" e o título podem não vir completos no CSV [de memória — conferir no primeiro export]. |
| **Navegador logado** (como o X) | Tudo, como o mundo vê. | Fere a 8.2 (raspar) na conta principal; o escaneamento de extensões e a impressão do navegador estão ativos (seção 4). | **Não.** Ler o próprio perfil uma vez por mês não justifica. |

Fluxo sugerido [inferência]: o Whis pede o export (com link direto da tela), ele baixa, o Whis lê
`Profile.csv`, `Positions.csv`, `Skills.csv` etc., cruza com o vault (o que ele fez de verdade, o que
falta no perfil) e com a rubrica adaptada, e entrega a nota e as reescritas na ordem de mais ponto
perdido. O que o CSV não tiver, ele cola.

## 4. Mudar o perfil e aplicar em vagas

### Não há API [fato]

- **Edição de perfil**: a *Profile Edit API* existe, mas "restricted to those developers approved by
  LinkedIn" ([Profile Edit API](https://learn.microsoft.com/en-us/linkedin/shared/integrations/people/profile-edit-api)).
- **Candidatura**: as APIs de Talent (Job Posting, Apply Connect, Apply with LinkedIn, RSC) são de
  ATS e parceiros, do lado de quem contrata. Não há API do lado do candidato nem para o Easy Apply
  ([Apply Connect](https://learn.microsoft.com/en-us/linkedin/talent/apply-connect),
  [Talent](https://learn.microsoft.com/en-us/linkedin/talent)).

### O que sobraria: navegador logado na conta dele

**User Agreement, seção 8.2 ("Don'ts")** [fato, texto citado em
[contentin.io](https://contentin.io/blog/linkedin-mcp-terms-of-service/) e
[linagora/twalk #201](https://github.com/linagora/twalk/issues/201); versão em vigor desde 3/11/2025;
original em [linkedin.com/legal/user-agreement](https://www.linkedin.com/legal/user-agreement)]:

- proíbe "Develop, support or use software, devices, scripts, robots or any other means or processes
  (including crawlers, browser plugins and add-ons or any other technology) to scrape the Services or
  otherwise copy profiles and other data from the Services";
- e usar "bots or other unauthorized automated methods to access the Services, add or download
  contacts, send or redirect messages, create, comment on, like, share, or re-share posts, or
  otherwise drive inauthentic engagement".
- A central de ajuda repete: não permite software de terceiros que "scrape, modify the appearance of,
  or automate activity on LinkedIn's website".

Preencher um Easy Apply ou editar o perfil por Playwright é "automate activity" sem rodeio.

### Histórico de restrição (2024–2026) [fato, com a ressalva das fontes]

- **AIHawk** (robô de Easy Apply com IA, open source, viral em 2024): o próprio criador disse ter sido
  **banido pelo LinkedIn** por usar a ferramenta
  ([Business Insider/AOL](https://www.aol.com/free-ai-tool-help-apply-110301118.html)).
- **Proxycurl** (raspagem): processado pelo LinkedIn em 24/01/2025 (caso 3:25-cv-00828, N.D. Cal.),
  fechou em 4/07/2025 com acordo
  ([Nubela](https://nubela.co/blog/is-scraping-linkedin-legal-in-2026/),
  [Bloomberg Law](https://news.bloomberglaw.com/artificial-intelligence/linkedins-war-against-bot-scrapers-ramps-up-as-ai-gets-smarter)).
- **HeyReach** (automação de prospecção na nuvem): em 25/03/2026 o LinkedIn removeu a página da empresa
  (16,4 mil seguidores) e restringiu os perfis pessoais do CEO, CTO, CRO e CMO
  ([HeyReach](https://www.heyreach.io/blog/heyreach-ban), [Valley](https://joinvalley.co/blog/linkedin-automation-safety-2026)).
- Levantamento da Northlight sobre o 1º trimestre de 2026: **~40% das contas** que usavam
  HeyReach, Expandi, Dripify ou Waalaxy tiveram alguma restrição
  ([Northlight](https://northlight.ai/blog/what-happens-when-linkedin-bans-your-tool)). **Ressalva**:
  é fornecedor concorrente, número não auditado.
- Relatos em fóruns citados por esses blogs: conta "de uma vida, com mais de 1.000 conexões" perdida
  com Expandi, e uma conta de cliente banida de vez depois de uma rodada de **Dux-Soup** (extensão
  local). Ou seja, rodar no navegador local não é imune. Os fornecedores de extensão (Dux-Soup,
  LinkedHelper) se vendem como "risco menor" por rodarem no IP e na máquina do usuário; é argumento
  de venda, não garantia.
- Contraponto: o estudo do `twalk` sobre as pontes `mautrix/linkedin` e `beeper/linkedin` (leitura
  de mensagens) achou **zero casos de conta restrita** em 168 issues de 2022–2026. A reação observada
  foi invalidar a sessão (o cookie `li_at`), por exemplo quando a versão anunciada do Chrome não batia
  ([twalk #201](https://github.com/linagora/twalk/issues/201)).

### Detecção [fato]

- ***BrowserGate*** (abril de 2026): em cada página, o LinkedIn roda um script que testa **6.236
  extensões** do Chrome (eram ~2.000 em 2025) e coleta dados do aparelho, só em navegadores Chromium.
  O BleepingComputer confirmou parte disso
  ([BleepingComputer](https://www.bleepingcomputer.com/news/security/linkedin-secretely-scans-for-6-000-plus-chrome-extensions-collects-data/),
  [Tom's Hardware](https://www.tomshardware.com/software/browsers/linkedin-scans-visitors-browsers-for-over-6000-chrome-extensions-and-collects-device-data)).
- Os gatilhos citados pelos fornecedores são IP estranho, rajadas e horário fora do padrão
  [fato, fontes interessadas].
- **[inferência]** Um Chrome dirigido por Playwright via CDP deixa marcas que um site atento pode
  detectar. O LinkedIn investe nisso explicitamente; o X, pelo que o ADR 0003 mostra, até agora não.

### Recomendação: risco zero, ele clica [inferência]

- **Perfil**: o Whis entrega cada seção pronta para colar, na ordem de ganho, com o link direto da
  tela de edição e o lembrete de **desligar o aviso à rede antes** (seção 6). Ele cola. Depois, o Whis
  confere pelo próximo export, sem navegador.
- **Vaga do LinkedIn com chance boa**: entra no relatório como as outras ("tudo mastigado"): por que
  casa, o link da vaga, as respostas das perguntas do Easy Apply que dá para prever (anos de
  experiência por stack, pretensão, disponibilidade, inglês), o currículo ajustado em PDF e uma nota
  ao recrutador se valer (`li-dm` adaptado). Ele abre e clica.
- **Vaga do LinkedIn de tentar a sorte**: pela regra dele ("no LinkedIn, nada"), não sai sozinha.
  Sugestão: listar só as que têm candidatura **fora** do LinkedIn (o link "Candidatar-se no site da
  empresa"), que aí caem na regra geral do ticket 06. As de Easy Apply puro ficam numa lista curta
  para ele, ou somem.
- Isso mantém o LinkedIn **fora de qualquer automação de navegador**, sem ADR novo.

## 5. Ler vagas do LinkedIn

### Sem login: a busca pública [fato]

- `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=…&location=…&start=N`
  devolve HTML com 10–25 cartões, sem login. **Segue no ar em 2026** (guias de 2026 no resultado de
  busca; o [JobSpy](https://github.com/speedyapply/JobSpy), MIT, v1.1.82, último commit em
  01/10/2026, usa esse endpoint).
- **Filtros** (lidos no código do JobSpy, `jobspy/linkedin/__init__.py`): `keywords`, `location`,
  `distance`, `f_WT=2` (remoto), `f_JT` (regime), `f_TPR=r{segundos}` (publicadas há menos de X),
  `f_AL=true` (só Easy Apply), `f_C` (ids de empresa), `start` (paginação, teto ~1.000 por busca).
- **O que o cartão traz**: título, empresa e link da empresa, local (cidade/estado/país), data de
  publicação, link `linkedin.com/jobs/view/{id}`.
- **Com uma requisição a mais por vaga** (`/jobs/view/{id}`, página pública): descrição completa,
  faixa salarial quando a empresa publica, senioridade, regime, área e setor. Se o LinkedIn manda para
  `/signup` (authwall), volta vazio.
- **Limite**: "LinkedIn is the most restrictive and usually rate limits around the 10th page with one
  ip" (README do JobSpy). O JobSpy espera 3–7 s entre páginas e para no primeiro 429. Relato de 2026:
  sem pausa, 429 em ~15 requisições; com 2 s de pausa, 55 de 55 passaram (dev.to/agenthustler, no
  resultado de busca).
- **Detalhe para o Brasil** [fato, código]: o JobSpy só converte salário em `$`, `CA$`, `£`, `€` e `₹`;
  faixa em `R$` volta sem valor. É um parser a ajustar se o Whis reaproveitar a lógica.

### Logado (como o X)

- Traria mais [de memória]: número de candidatos, "vagas recomendadas para você", o selo de quem a
  rede conhece na empresa, o status "candidatura vista".
- O custo é a conta dele na mira da 8.2 ("scrape the Services") e do escaneamento acima. É a mesma
  troca do ADR 0003, com a diferença de que **a conta do LinkedIn é a vitrine profissional dele e os
  colegas estão lá**.

### Risco e legalidade da leitura pública

- **[de memória — conferir]** *hiQ Labs v. LinkedIn*: o 9º Circuito (2022) entendeu que raspar dado
  público não viola a lei americana de fraude computacional (CFAA). Depois, no mesmo ano, o tribunal
  distrital decidiu que a hiQ violou o User Agreement, e o caso terminou em acordo em dezembro de 2022.
- **[inferência]** A 8.2 vale para "Visitors" também, mas sem login **não há conta para restringir**:
  o pior caso realista é o IP de casa dele levar 429 ou ver a authwall por um tempo. Esse IP é o
  mesmo da conta logada dele; em volume de uma corrida por mês, a chance de o LinkedIn ligar uma
  coisa à outra e agir na conta é remota, mas não é zero.

### Recomendação [inferência]

- **Busca pública, sem login, sem navegador**: `httpx` (o Whis já usa HTTP puro nas fontes) com a
  lógica do JobSpy como referência, ou o próprio `python-jobspy` como dependência (MIT). Poucas
  buscas por corrida (web dev remoto Brasil; web dev Ribeirão Preto/São Paulo; games/áudio), no
  máximo umas 5–8 páginas cada, pausas de 3–7 s, parar no primeiro 429 e seguir para o próximo site.
  A descrição só das vagas que passaram no primeiro filtro (título, local, data).
- Se a busca pública morrer, o LinkedIn sai das fontes da caçada e o relatório diz isso, como o "X
  indisponível hoje". **Não** escalar para navegador logado sem um ADR e o "sim" dele.

## 6. Discrição: o que os colegas veem

| sinal | o que acontece | como evitar |
| --- | --- | --- |
| **#OpenToWork** (moldura verde) | Visível a todos. | Nunca. |
| **Open to Work "Recruiters only"** | O LinkedIn "takes steps" para não mostrar a recrutadores **da empresa atual**, mas diz que **não garante** (conta pessoal de Recruiter, ferramenta de terceiros) [fato] ([Help 67405](https://www.linkedin.com/help/linkedin/answer/67405)). | Não ligar. Para ele, o risco não compensa [inferência]. |
| **Aviso de mudanças à rede** | A opção *Compartilhar mudanças de emprego, formação e aniversários de trabalho do perfil* (Configurações → Visibilidade → Visibilidade da sua atividade) gera post no feed, notificação ou e-mail para a rede. Emprego vai em até 2 h, formação em até 24 h [fato] ([Help 86236](https://www.linkedin.com/help/linkedin/answer/86236)). | **Desligar antes** de qualquer edição de experiência ou formação. O Whis lembra disso no topo de toda entrega de "mude o perfil". Título e "Sobre" não geram post na rede [de memória — conferir]. |
| **"Prestando serviços" / Open for business** | Aparece no perfil como cartão [de memória]. Anuncia freela a quem visita. | Não ligar enquanto a discrição valer. |
| **Posts** | Vão ao feed de conexões e seguidores; os colegas veem tudo. | Tema de dev e IA, do que ele fez; nada de "novos desafios", "fechando um ciclo" ou "aberto a propostas". O Whis evita isso no prompt e ele aprova [inferência]. |
| **Curtidas e comentários** | Aparecem no feed da rede ("Fulano comentou"). | Comentar em post de recrutador ou em "estamos contratando" sinaliza. `li-plan` manda interagir todo dia; para ele, só onde não sinaliza [inferência]. |
| **Ritmo** | Muitas mudanças de perfil na mesma semana, ou sair de zero para quatro posts semanais, chama atenção [inferência]. | Mudanças do perfil espalhadas em semanas; posts num ritmo estável e baixo. |
| **Visitas a perfis** | Quem ele visita vê "Gabriel viu seu perfil" [de memória]. | Ao abrir perfil de recrutador por link do Whis, usar o modo privado de visualização. Como o Whis não navega no LinkedIn, ele próprio não deixa rastro. |
| **Candidatura (Easy Apply)** | Vai para quem anunciou; não é publicada na rede [de memória]. O risco é a vaga ser da empresa dele ou de cliente. | O Whis marca no relatório vaga do empregador atual ou de cliente conhecido (o vault sabe quais são) [inferência]. |

## Fontes

- Skill: [Jakeschincariol/linkedin-agent-skill](https://github.com/Jakeschincariol/linkedin-agent-skill) (clonada, `add2c23`, 2026-09-07).
- Documentação oficial (lida pelo trecho do buscador; acesso direto bloqueado nesta sessão):
  [Share on LinkedIn](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin) ·
  [Sign In with LinkedIn using OpenID Connect](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2) ·
  [Getting Access](https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access) ·
  [Authorization Code Flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow) ·
  [Native (PKCE)](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow-native) ·
  [Programmatic Refresh Tokens](https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens) ·
  [Rate Limits](https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/rate-limits) ·
  [Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api) ·
  [UGC Post API (Legacy)](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/ugc-post-api) ·
  [Images](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api) ·
  [MultiImage](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/multiimage-post-api) ·
  [Documents](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/documents-api) ·
  [Full Profile Fields (Closed)](https://learn.microsoft.com/en-us/linkedin/shared/references/v2/profile/full-profile) ·
  [Profile Edit API](https://learn.microsoft.com/en-us/linkedin/shared/integrations/people/profile-edit-api) ·
  [Apply Connect](https://learn.microsoft.com/en-us/linkedin/talent/apply-connect).
- Central de ajuda do LinkedIn: [User Agreement](https://www.linkedin.com/legal/user-agreement) ·
  [Associar app a uma Page](https://www.linkedin.com/help/linkedin/answer/a548360) ·
  [Baixar seus dados](https://www.linkedin.com/help/linkedin/answer/50191) ·
  [Portabilidade (DMA)](https://www.linkedin.com/help/linkedin/answer/a6214075) ·
  [Open to Work](https://www.linkedin.com/help/linkedin/answer/67405) ·
  [Compartilhar mudanças do perfil](https://www.linkedin.com/help/linkedin/answer/86236).
- Vagas: [speedyapply/JobSpy](https://github.com/speedyapply/JobSpy) (clonado, v1.1.82, 2026-10-01).
- Restrição e detecção: [twalk #201](https://github.com/linagora/twalk/issues/201) ·
  [contentin.io (8.2)](https://contentin.io/blog/linkedin-mcp-terms-of-service/) ·
  [HeyReach](https://www.heyreach.io/blog/heyreach-ban) · [Valley](https://joinvalley.co/blog/linkedin-automation-safety-2026) ·
  [Northlight](https://northlight.ai/blog/what-happens-when-linkedin-bans-your-tool) ·
  [AIHawk (Business Insider/AOL)](https://www.aol.com/free-ai-tool-help-apply-110301118.html) ·
  [Nubela/Proxycurl](https://nubela.co/blog/is-scraping-linkedin-legal-in-2026/) ·
  [Bloomberg Law](https://news.bloomberglaw.com/artificial-intelligence/linkedins-war-against-bot-scrapers-ramps-up-as-ai-gets-smarter) ·
  [BleepingComputer (BrowserGate)](https://www.bleepingcomputer.com/news/security/linkedin-secretely-scans-for-6-000-plus-chrome-extensions-collects-data/).
- Tokens e OAuth (terceiros): [OpenTweet](https://opentweet.io/answers/linkedin-api-token-expires-60-days) ·
  [Nango](https://nango.dev/blog/linkedin-oauth-refresh-token-invalid-grant) ·
  [Blotato](https://www.blotato.com/blog/linkedin-posting-api) ·
  [postiz-app #1582](https://github.com/gitroomhq/postiz-app/issues/1582) ·
  [robotsix-linkedin](https://github.com/damien-robotsix/robotsix-linkedin).
- Código do Whis: `src/whis/jornal_claude.py` (opções do Agent SDK), [ADR 0003](../../../docs/adr/0003-x-por-navegador.md).
