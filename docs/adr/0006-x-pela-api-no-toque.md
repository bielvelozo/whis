# O post do X sai pela API no toque dele, e a resposta da vigia abre o X pronta

> Registro de 2026-10-31.

A conta da velozo.dev no X (em inglês) recebe dois rascunhos no Telegram: o post do dia (seg, qua e
sex, `ideias_do_x.py`) e a resposta a quem está contratando (`vigia_do_x.py`). Ele pediu um botão que
publicasse os dois, para ligar depois de duas semanas de conta (14/11), pela API oficial e não pelo
navegador do jornal (ADR 0003, que só lê).

- **Post do dia**: o botão "Publicar no X" chama `whis celular --tocar` e publica pela API paga por
  uso, com o app dele no console.x.com (OAuth 1.0a, Read and Write, quatro chaves em `[x]`). As
  imagens de `.scratch/x/posts/` sobem primeiro, cada post da thread responde ao anterior e a resposta
  com o link vai por último. O botão só aparece com as quatro chaves preenchidas, então é ele quem liga.
- **Resposta da vigia**: o botão "Responder no X" é um link do Telegram para
  `x.com/intent/tweet?in_reply_to=<post>&text=<resposta>`. Abre o X com a resposta escrita, na conta
  ativa do app (que precisa ser a velozo.dev); quem aperta Post é ele. O texto continua no bloco que copia
  num toque, e `[cacada].x_botao_responder` desliga o botão. A DM continua no copiar e colar: o link de
  DM pede o id numérico do autor, que o leitor não guarda.

## Por quê

Desde 23/02/2026, a API só aceita resposta quando o autor do post marcou ou citou a conta
(docs.x.com, *Manage Posts*: "Replies via the API are only permitted if the replying account has been
explicitly summoned by the original post's author"). Vale para o plano pago por uso. A vigia acha os
posts por busca de palavra, então toda resposta dela pela API voltaria com 403. Responder ao próprio
post continua liberado (equipe do X no fórum, 24/02/2026), e por isso a thread passa.

Preços de 31/10/2026: US$ 0,015 o post e US$ 0,20 o post com link. Uma thread de quatro posts, mais a
resposta com o link, sai por US$ 0,26. A subida de imagem não aparece na tabela.

## Considered Options

- **Resposta da vigia pela API**: barrada pelo X, como explicado acima. O plano Enterprise não tem a
  trava, mas é negociado à parte e caro demais para uma conta nova.
- **Postar pelo Chrome da conta da velozo.dev**: é automação de conta de usuário, proibida pelas
  regras do X e pela ADR 0003.
- **Publicar sozinho, sem toque**: recusado por ele. Cada post só sai com o "pode publicar" dele.

## Consequências

- **Uma vez só**: o estado (`cacada\x-ideias.json`) vira `enviando` antes do primeiro pedido e guarda o
  id de cada post confirmado. Recusa clara do X (4xx) ou falta de conexão antes do primeiro post
  devolvem o botão. Fora isso, o que o X não confirmou vira `incerta` e nunca é repetido: ele confere
  no perfil e termina à mão.
- O post da lista `cacada/x/posts-*.md` ganha "- Publicado: dd/mm" quando o primeiro post sai.
- As regras de automação do X continuam valendo para a conta. Com o toque dele em cada post, o envio
  é dele, mas o risco de limite na conta nova não some.
- Curtir, seguir, mandar DM e responder a terceiros pela API ficam fora do Whis.
