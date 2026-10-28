---
criado: 2026-10-28
de: sessão "Identidade visual e paleta de cores", no servidor (DESKTOP-FVOEMG4)
para: a próxima sessão no note-biel
---

# Handoff de 27 e 28/10: marca, site com PostHog, caixa nova, e-mails frios e Whis

Leia primeiro `docs/agents/maquinas.md`, que diz o que roda em cada máquina. Este handoff saiu do servidor, e quase tudo o que falta é do Whis, que só roda no note-biel.

## 1. O que você faz primeiro, no note-biel

1. **Trazer o código.** Este pacote veio no `whis-handoff.bundle`. O bundle precisa só do 5c4d551, de 20/10, que o note-biel já tem. Ele traz a branch `handoff-servidor-note` com 5 commits: os 3 do tema de fábrica, a regra de máquinas e este handoff. No checkout do Whis do note-biel:
   ```powershell
   git status
   git bundle verify $HOME\Downloads\whis-handoff.bundle
   git fetch $HOME\Downloads\whis-handoff.bundle handoff-servidor-note:handoff-servidor-note
   git log --oneline master..handoff-servidor-note
   ```
   O note-biel tem o a291d33 (Resend) e mudanças não commitadas em `agencias_email.py`, `configuracao.py`, `freelas_rapidos.py`, `propostas_auto.py` e nos testes. Commite essas mudanças antes, numa branch ou no master, e depois faça o merge de `handoff-servidor-note`.

   Os commits do tema de fábrica mexem só em `tema_de_fabrica.py`, `lojas_shopify.py`, `lojas_email.py`, `CONTEXT.md` e `tests/test_tema_de_fabrica.py`. Rode a suíte inteira depois do merge.
2. **Notas do vault que podem não ter chegado.** Elas foram escritas no servidor, onde o Obsidian não roda. Se faltarem em `C:\Users\gabri\whis-vault\cacada\`, copie de `.scratch/handoff-servidor-note/vault/cacada/`:
   - `voz.md`: o jeito de escrever dele, escolhido em 27/10.
   - `pesquisa-cold-email-2026-10-27.md`: a pesquisa de e-mail frio.
   - `envios-2026-10-28.md`: os 21 e-mails programados em 28/10.
   - `whis-rastreio-e-ab.md`: o pedido de rastreio e de teste A/B para o Whis.
3. **Conferir o config** (`%APPDATA%\whis\config.toml`). Ele já trocou em 28/10, mas vale conferir:
   - `[cacada]`:
     - `email = "gabriel@velozo.dev"`
     - `remetente = "gabriel@velozo.dev"`
     - `senha_de_app` = a senha de app nova da caixa
     - `resend_chave = ""`, que pausa a Resend: a política dela proíbe e-mail frio.
   - `[cacada].lojas_redesenho_por_dia` não pode estar em 0. O padrão é 1.

   A primeira senha de app foi colada no chat. Se a que está no config for essa, gere outra em myaccount.google.com/u/5/apppasswords e apague a antiga.
4. **Testar o envio pela caixa nova.** Rode `python .rota-teste-caixa-nova.py` na raiz do Whis (o arquivo foi mandado a ele em 28/10). Ele manda um e-mail de gabriel@velozo.dev para soares.velozog@gmail.com. O log fica em `.rota-teste-caixa-nova-log.txt`, com a branch, o commit e o estado do config, sem mostrar segredo.

   Se `agencias_email.gmail()` do note-biel tiver outra assinatura, ajuste o roteiro. Depois, toque "Enviar e-mail" num rascunho de teste no Telegram e confira que sai do gabriel@velozo.dev, sem o "por gmail.com".
5. **Implementar o rastreio e o teste A/B no Whis**, conforme `cacada/whis-rastreio-e-ab.md`:
   - envio pela caixa nova;
   - reenvio na mesma conversa (In-Reply-To);
   - variante `conversa` ou `direto`;
   - link `velozo.dev/br/?r=<código>&utm_source=email&utm_medium=frio&utm_campaign=AAAA-MM&utm_content=<variante>`;
   - eventos `email_enviado`, `email_respondido` e `email_voltou` no PostHog;
   - sequência de 3 e-mails, com no máximo 10 por dia na caixa nova;
   - os textos de agências e de lojas seguindo o `voz.md`.

   O e-mail de redesenho já segue o `voz.md` no cd3d4eb, com a variante fixa em `conversa`.
6. **Os 3º e-mails dos 21 de 28/10.** Saem de segunda, 02/11, a terça, 03/11, só para quem não respondeu, com um ângulo novo e uma saída clara (ver `voz.md`, "Tamanho e follow-up"). As contas, os códigos e as variantes estão em `envios-2026-10-28.md`.

## 2. O que ficou pronto

### Marca (27/10)
- **Logo:** "Velozo.", com o V desenhado à mão no traço da Bodoni, o "elozo" em Bodoni Moda e o ponto terracota. Os arquivos estão em `gabrielvelozo-site/marca/logo/` (6501d5b) e o guia em `marca/marca.md`. O guia publicado está em https://claude.ai/artifact/F4BzagV6KjXvTPTvfpNoTg.
- **Site:** o logo está no topo, o favicon é o V com ponto e os títulos passaram para a Bodoni (a014ef1).

### Site velozo.dev com PostHog (28/10)
Repositório `gabrielvelozo-site`, branch `especime-v4`. Commits c60bc9f, c0ff189 e a2e5a43, publicados do servidor em 28/10 por volta das 9h (deploy 7c1034ea).
- O snippet do PostHog está no `<head>` de `site/br/index.html`. A versão em inglês sai de `scripts/idiomas.py`.
- Em velozo.dev, os eventos passam por `/ingest`, a função `functions/ingest/[[path]].js` (proxy contra bloqueador). Fora de velozo.dev, vão direto para us.i.posthog.com.
- **Eventos:**
  - interação: `som_ligado`/`som_desligado`, `fonte_escolhida`, `cor_escolhida`, `estilo_aberto`, `peso_mexido`, `espaco_mexido`, `marca_digitada`;
  - navegação: `passo_visto` (o passo 9 é o portfólio), `loja_aberta`, `video_aberto`, `link_externo`, `email_copiado`;
  - conversão: `servico_adicionado`, `pedido_enviado` (faz identify pelo e-mail).
- **Visita que vem do e-mail:** `?r=<código>` faz identify como `email:<código>` e manda `email_clicado`. O `utm_content` vira a propriedade `variante` em todos os eventos da visita.
- O rastreio está desligado no Chrome do note-biel (opt-out), para as visitas dele não contarem.

### PostHog
- Conta Google gabrielvelozodev@gmail.com, região US, projeto "velozo.dev" (id 693025). A chave pública está no snippet.
- Gravação de sessão e mapa de calor ligados, URL autorizada https://velozo.dev, filtro de teste `$host` = velozo.dev.
- **Painel "velozo.dev"** (id 2269604, o principal), com 9 gráficos:
  - funil até o pedido;
  - até que passo da história eles vão;
  - cores escolhidas e fontes escolhidas;
  - som;
  - lojas abertas;
  - vídeos e links de fora;
  - e-mails frios por variante (enviado, clicado e respondido);
  - origem das visitas (utm_source).
- **Mandar evento de fora do site:** `POST https://us.i.posthog.com/i/v0/e/` com `api_key`, `event`, `distinct_id` (`email:<código>`) e `properties`.

### Caixa gabriel@velozo.dev (Google Workspace)
- Plano Business Standard, conta /u/5 no Chrome. O teste grátis começou em 27/10 e a cobrança começa depois dele.
- Registros no DNS da Cloudflare:
  - DKIM `google._domainkey`, ativo;
  - SPF `v=spf1 include:_spf.google.com ~all`;
  - DMARC `v=DMARC1; p=none; rua=mailto:gabriel@velozo.dev`.
- O MX já aponta para o Google. O logo (avatar escuro com o V) é a foto do perfil, trocada pelo Google Admin.

### E-mails frios programados para quarta, 28/10 (Gmail, envio programado)
- 15 reenvios no gabrielvelozodev@gmail.com, das 9h00 às 11h20, um a cada 10 minutos, como resposta na conversa do primeiro e-mail (18 a 21/10).
- 6 novos no gabriel@velozo.dev, das 10h05 às 11h25, com o link rastreado em "velozo.dev".
- Metade de cada variante. O `email_enviado` dos 21 foi registrado no PostHog.
- A lista completa está em `envios-2026-10-28.md`.
- **Ficaram de fora:**
  - Alfinet: o Jeferson respondeu e pediu o currículo.
  - Dash Otimiza: o Felipe respondeu e marcou conversa.
  - Baggio: o setor de compras pediu cadastro no Portal de Fornecedores, e quem faz é ele.
  - O endereço da Benuv em .com.br não existe. O reenvio foi para contato@benuv.com.
- **As respostas ainda não são contadas sozinhas.** Até o Whis fazer isso, o `email_respondido` vai à mão, pelo POST acima.

### Whis: tema de fábrica (branch `claude/tema-de-fabrica-acha-lojas-323211`)
- **Causa:** desde o 5c4d551, a loja só contava como de fábrica se tivesse as cores iguais às da demonstração. Como todo lojista troca a cor, nenhuma loja passava.
- **Agora:** decidem as variáveis de layout (larguras, espaçamentos, cantos, colunas). A loja precisa ter pelo menos 75% iguais.
  - Nas 30 lojas reais medidas, eram 0 e agora são 5: Unifoccus, AFP, Vishfi, Máquinas&Café e Style Me.
  - A procura também passou a ler o fórum da Shopify.
  - Dois defeitos na leitura das seções foram corrigidos.
- **Rascunhos:** há 4 prontos no jeito dele. Unifoccus e Máquinas&Café já estão em `cacada/lojas-shopify.md` como lentas. Para receberem o e-mail de redesenho, falta a linha "Tema de fábrica:" à mão.
- **Limites:**
  - A margem é curta: a positiva mais baixa ficou em 0,77 e a negativa mais alta em 0,70.
  - A AFP só mostra e-mails `nf@` e `ti@`.
  - Na suíte, 3 testes falham por precisarem de tela; não têm a ver com a mudança.

## 3. O que ficou para depois (decisões dele)
- Assinatura do e-mail só em texto (recomendado) ou com logo.
- Se os e-mails do Whis seguem o modelo novo da marca: o voz.md já é a base.
- Cookies no site: hoje não há banner. Existe o modo sem cookies do PostHog, que perde parte do rastreio.
- UTM nos links do velozo.dev das descrições do YouTube e dos perfis (Fiverr, Shopexperts, 99Freelas, LinkedIn, GitHub): não foi feito. Sugestão: `utm_source=youtube|fiverr|...&utm_medium=perfil`.
- A imagem `og` do site ainda tem a marca antiga.
- Ligar o OpenSSH Server no note-biel com a chave do servidor (comandos de 28/10), para o servidor poder agir lá.
- A mudança do Whis para o servidor foi descartada em 28/10: o Obsidian Sync, a Granola e a bandeja dependem do notebook. O servidor só ganhou um `.venv` no clone velho, que o git ignora.
