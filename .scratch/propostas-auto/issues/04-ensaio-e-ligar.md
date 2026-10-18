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
