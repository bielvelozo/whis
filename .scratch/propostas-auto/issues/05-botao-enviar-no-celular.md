Status: ready-for-human
Blocked by: 04

# Botão "Enviar esta proposta" no Telegram

Pedido dele em 18/10: "se eu ver uma proposta boa, eu falo para ele já enviar pelo Telegram, para mim não ter que acessar o meu computador".

## O que faz

- A proposta da 99Freelas que não sai sozinha (cota do dia cheia, 80 propostas ou mais, conexões na reserva) é escrita mesmo assim, até `[cacada].propostas_auto_para_aprovar` por dia (o config nasce com 5), e chega no celular com o botão "Enviar esta proposta". A do ensaio também.
- A bandeja ouve os botões (`celular.Ouvinte`, thread própria, long polling no `getUpdates` só de `callback_query`, só o chat de `[celular]`).
- O toque responde na hora ("Recebido"), e `propostas_auto.tocou_enviar` confere tudo de novo (login, projeto aberto, nada proposto antes, texto, formulário), envia pelo Chrome da caçada e responde na conversa. Quando tocar de novo não faria nada, o botão sai.
- A cota do dia e a reserva não barram o toque: são do automático. A aprovada não gasta a cota.
- O texto que sai é o da nota (a editada no Obsidian sai editada).
- A rodada da vigia e o toque usam a mesma trava (`propostas-auto.trava` em `%LOCALAPPDATA%\whis\cacada`): com o toque no Chrome, a vigia deixa a proposta para a próxima hora; com a vigia no Chrome, o toque espera até 10 min.
- `whis celular --pendentes` manda de novo as que esperam o toque (últimos 2 dias).
- O Freelancer.com continua só com aviso (User Agreement, seção 33).

## Para ligar

1. Reiniciar a bandeja de verdade (pela tarefa descartável) para subir o código novo.
2. `propostas_auto_para_aprovar = 5` já vale pelo padrão; não precisa gravar.
3. Mandar de novo as 3 do ensaio de 18/10 com o botão (`whis celular --pendentes`).
4. Ele toca em uma e confere na 99Freelas.

## Comments
