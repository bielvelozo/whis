Status: ready-for-human
Blocked by: 01, 02, 03

# Ensaio de um dia e ligar o envio

1. Ele cria o bot no @BotFather e roda `whis celular`.
2. Ele entra na 99Freelas pelo `whis navegador` e fecha o Chrome.
3. `[cacada].propostas_auto = "ensaio"` no config real, pela tarefa descartável; um dia de vigia de hora em hora.
4. Ele vê no celular as propostas que teriam saído; o tom passa pelo humanizer e o pedido ao Claude é ajustado.
5. Com o "pode ligar o envio" dele, `propostas_auto = "ligado"`.

## Comments

18/10, 02h: passos 3 feito pela tarefa descartável (`execucao/ligar.ps1`): `propostas_auto = "ensaio"` e a vigia de hora em hora no config real, `Whis-Vigia-Freelas` com 17 gatilhos (07:00 a 23:00). A leitura ao vivo mudou as travas (spec, item 3). Primeira rodada real disparada à mão às 02:13: 5 chamadas ao Claude (plano 7 d em 10%), 2 "não entrega" e 3 ensaios em `cacada/propostas-auto/`, sem login (formulário não aberto). A primeira rodada real quebrou antes, às 02:11: o Playwright deixa um loop rodando na thread e o `asyncio.run` do SDK recusa; a chamada do Claude foi para uma thread própria. Faltam os passos 1, 2, 4 e 5.

18/10, 10h–11h: passo 1 feito (bot @whis_02_bot; ele colou o token no chat e eu gravei pela descartável, `ligar-telegram.ps1`), os 3 ensaios mandados ao celular (`reenviar-ensaio.ps1`). Passo 2: o primeiro login dele caiu no Chrome principal (o histórico do perfil da caçada não tinha /login); reabri a janela pela descartável e ela passou a se chamar "Chrome da caçada (Whis)" (58338d0). Formulário de verdade preenchido sem clicar às 11:07 (`testar-formulario.ps1`): oferta 50,00, final 62,50, 3 dias, 1 conexão, sobram 14, botão conferido com click de teste. Passo 5: "pode ligar o envio" dele às 11:14; `ligar.ps1 -Modo ligado` gravou `propostas_auto = "ligado"`.
