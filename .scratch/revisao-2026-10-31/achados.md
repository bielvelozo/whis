# Revisão de 31/10 (06:40 às 08:00): X, Instagram e fórum da Shopify

Do mais grave para o menos grave. Cada item diz se foi corrigido aqui ou se ficou para outra pessoa.

A suíte inteira, rodada sobre o HEAD `8c6e0e2` (cópia limpa, por `git archive`), passou (saída 0). Na working tree, a coleta para em `painel.py` com "O modelo tem a chave x.api_key, que CHAVES não conhece". É a sessão do botão "Enviar no X" no meio da mudança dela, não um defeito commitado.

## 1. O filtro do fórum da Shopify tirava vaga de verdade

`src/whis/fontes_da_cacada.py` (`40416dc`). "available", "we build" e "I can help" soltos, no título ou no resumo, tiravam da coleta quem contrata. Na versão commitada, as cinco vagas inventadas abaixo saíam todas:

- "Looking for a Shopify developer" / "Budget available for the right person. We build custom furniture."
- "Shopify Plus dev wanted" / "Full-time role available, remote OK"
- "Seeking Shopify expert for store migration" / "Is anyone available this week? Paid project."
- "Shopify developer position available, remote"
- "Need help with my Shopify store" / "I can help with the product photos myself, but need someone for the theme code"

O commit diz que testou com os 9 posts abertos daquele dia. É pouco para uma palavra como "available", que aparece em quase toda vaga.

**Corrigido em `f0b32b0`**: os três só contam quando dizem quem se oferece ("Team Available", "Shopify Expert Available", "available for work", "we build Shopify stores", "I can help you"). O teste ganhou as 4 vagas e 2 ofertas novas, e os 8 posts reais do teste antigo continuam com o mesmo resultado.

## 2. A conferência do rascunho da vigia do X deixava passar emoji, link, preço e "uso IA"

`src/whis/vigia_do_x.py`, função `problemas` (`f15c8be`). Todos os textos abaixo passavam sem nenhum problema:

- emoji: bandeira (🇧🇷), ⭐ e ⏰ (fora das faixas da regex);
- link: `bit.ly/abc`, `linktr.ee/velozo`, `velozo.org`, `discord.gg/abc`;
- preço: "USD 300 flat", "30/h", "30 an hour";
- IA: "I use AI to build faster", quando o post fala de IA. A exceção do post era para falar da integração de IA que o cliente pediu, não para ele dizer que usa;
- call: "Happy to jump on calls" (só pegava "call" no singular).

E o contrário: "eu ia te sugerir" (o verbo, em português) barrava o rascunho como "cita IA".

## 3. O mesmo autor recebia dois rascunhos na mesma rodada

`rodar` confere "autor que já recebeu rascunho na semana" antes de chamar o Claude, e só marca o autor depois de cada rascunho. Dois posts da mesma pessoa na mesma leitura viravam dois rascunhos no Telegram. Prova: dois posts de @maya, 2 rascunhos.

**Itens 2 e 3: correção pronta e testada, falta aplicar.** A sessão do botão "Enviar no X" (local_771ce56b) está mexendo em `vigia_do_x.py` e no teste agora, sem commit. Avisei e não toquei. A correção está em `aplicar_vigia.py`, no scratchpad desta sessão: substituições exatas mais 2 testes novos, conferidos sobre o HEAD (17 testes passam; a sonda pega tudo da lista acima). Ela também deixa o "diz que usa IA" barrar sempre, com o post falando de IA ou não, e ainda deixa passar "I'd hook the AI chatbot into the cart drawer".

## 4. O post 2 do X (Inkly) atribuía à Inkly causas que ela não teve e escondia que é loja de portfólio

`cacada/x/posts-semana-1.md`, post 2. Dizia "Inkly's storefront took 11.9 s" e "What weighed the most: photos uploaded straight from the camera, apps nobody used anymore and scripts loading before the page".

O README do tema (`shopify-portfolio`, seção 3 "Speed, measured") diz outra coisa:
- a home foi feita lenta de propósito, para medir e consertar, e "It is not a client's store";
- o que pesava era o hero de 3840 px em `background-image`, as fotos do grid em 1500 px sem `srcset`, jQuery, Slick e AOS síncronos no `<head>`, o Font Awesome inteiro e o Google Fonts com todos os pesos;
- app esquecido não aparece em nenhum lugar.

**Corrigido no vault**: "Inkly, one of my portfolio stores, took 11.9 s… Now it's 3.5 s, same products and photos." e "What weighed the most: a 3840 px hero image, product photos without srcset, and jQuery, a slider and fonts loading before the page." (252 caracteres, passa na conferência). Ainda falta o "pode publicar" dele.

O README também diz que a versão lenta foi feita assim de propósito. O post não diz isso. Se ele quiser ser mais explícito, dá para trocar "took 11.9 s" por "was built slow on purpose (11.9 s)".

## 5. A conferência do post do dia no X (ideias_do_x) tem os mesmos furos

`src/whis/ideias_do_x.py` (`8c6e0e2`). Todos os textos abaixo passavam:

- "Stores built with AI in two days." e "My AI workflow cuts build time in half.": `_USA_IA` só pega "I/we … AI";
- "Our stores start at $400 for a full theme." e "Full store from US$ 300": `_PRECO_DELE` só pega "I charge", "my rate", "R$" e "starting at $";
- 🇺🇸 e ⭐: mesma faixa de emoji da vigia;
- `bit.ly/…`, `linktr.ee/…` e `velozo.shop`: `_LINK` não tem `.ly`, `.ee`, `.shop`, `.me` nem `.ai`. Além de deixar link no corpo, o link não conta como 23 no tamanho.

**Não corrigido**: o arquivo está sendo mudado agora pela sessão do botão "Enviar no X". As regexes da vigia (item 2) servem aqui também. No preço, cuidado para não barrar número com fonte ("$4.4 trillion in sales"): o melhor alvo é "from/start at/for + $".

## 6. O post 1 do X (portfólio, para fixar) nunca vai ao Telegram

Ele tem "More at velozo.dev" no corpo, e o plano diz que o fixado é a exceção. Mas `fila()` só oferece post que passa em `problemas_da_ideia`, e este cai em "o post 1 tem link". Ele fica de fora sem aviso. Como o plano marca o post para hoje (sáb 31/10), à mão, não é bug: só precisa ser publicado à mão e ganhar a linha "- Publicado:".

## 7. Artes do X: um título cortado e o cursor no print

- `.scratch/x/posts/gravacao.png`: o print da página da Nocte é recortado em "left top" (`gerar_x.py`, linha 122) e corta o título do produto em "The Nocte Solitai…", junto com a fileira de tamanhos. No Instagram (3-nocte-2) o mesmo print aparece inteiro.
- `.scratch/x/posts/portfolio-4.png` (Inkly): o cursor do mouse aparece no canto de baixo do print.

**Não corrigido**: as duas pedem gerar de novo (ou outro recorte, ou outro print). Ficam com ele ou com a sessão das artes.

## 8. Fontes e textos que conferem

- Títulos: Fraunces em todas as artes do X e do Instagram (conferido no recorte do título e nos dois geradores). A Bodoni só aparece no logo "Velozo." e no "V." da foto de perfil, que é o logo.
- Números com fonte: 0,1 s → 8,4% (Deloitte e Google, "Milliseconds Make Millions", 2020), 50 ms (Lindgaard et al., 2006), 46% (Stanford Web Credibility, Fogg et al., 2002) e Inkly 11,9 s → 3,5 s (medição dele no Lighthouse, `criterios.md`). Todos estão certos e têm a fonte no slide.
- Listas do Instagram de 29 e 30/10: sem link, preço, IA nem emoji. Todas terminam em pergunta que oferece algo, no jeito do `voz.md`. As 10 mensagens de 30/10 usam quase a mesma frase ("…paga sozinha, a qualquer hora, sem esperar resposta"). Como vão para marcas diferentes, ninguém vê a repetição.
- Post 4 do X (Nocte) dizia "a Shopify theme I built from scratch for a fine jewelry brand", o que faz parecer cliente. **Corrigido no vault**: "Nocte is one of my portfolio stores, fine jewelry, with a Shopify theme I built from scratch.", como no Instagram.
- Thread do X, post 4: "What can wait loads after the page shows up, or with defer." **Corrigido no vault** para "What can wait should load after the page shows up, with defer."

## 9. Menores

- `__main__._rodar_ideia_do_x` cria `IdeiaClaude(cli=…)` sem `modelo=configuracao.claude_modelo`, diferente da vigia (`XClaude(modelo=…, cli=…)`). Com `claude_modelo` no config, a ideia do dia ignora o modelo escolhido.
- `ideias_do_x.do_dia` guarda só os últimos 40 temas. Um post preparado que ele não marcar como "Publicado:" volta à fila depois de umas 13 semanas.
- `vigia_do_x._Estado.avisos` nunca é podado (cresce uma chave por tipo de aviso, não por dia, então fica pequeno).
