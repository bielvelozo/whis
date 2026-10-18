Status: resolved
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

18/10, 11h45–11h56: bandeja de verdade reiniciada pela descartável (`execucao/reiniciar-bandeja.ps1`, uma instância só, log "Celular: ouvindo os botões do Telegram"); as 3 do ensaio reoferecidas com o botão (`execucao/pendentes.ps1`). Prova sem enviar: o Chrome da caçada abre logado de dentro de uma thread num pythonw (`execucao/prova_thread.py`). Às 11:53 ele tocou Enviar no "Redesenho UX/UI das telas de site no ar (PT e EN)": R$ 50, 18 dias, 61 propostas antes; a resposta "Enviada" chegou no Telegram, o estado ficou `enviada` com `aprovada`, a nota virou `status: enviada` (origem "aprovada no celular") e o resumo do dia conta 1. Depois do clique a 99Freelas não abre modal: o botão vira "Enviando…" e o projeto passa a mostrar "Melhorar proposta".
