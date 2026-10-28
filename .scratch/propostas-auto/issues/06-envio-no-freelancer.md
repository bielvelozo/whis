Status: wontfix

Em 28/10 ele pediu para ignorar o Freelancer.com em todas as estratégias ("lá só tem coisa que eu tenho que pagar para aplicar e é mt concorrido"): o site entrou em `[cacada].plataformas_pagas`, e a vigia, a caçada e o modo freelas não leem mais nada de lá.

# Envio da proposta no Freelancer.com

Pedido dele em 18/10: a proposta automática não pode ficar presa à 99Freelas. Sobre o Freelancer.com, ele disse: "pode arriscar minha conta, a freelancer em si é um site que tem que pagar e mt difícil lá ent não me importo se perder a conta". A seção 33 do User Agreement proíbe meio automático, inclusive pela API, sem permissão escrita; ele aceitou o risco.

## O que já está pronto

- O Chrome da caçada está logado no Freelancer.com (@gabrielvelozodev) desde 18/10 às 15h10. Ele entrou pelo Google com "Remember me" marcado; sem essa opção, os cookies `GETAFREE_AUTH_HASH_V2` e `GETAFREE_USER_ID` morrem quando o Chrome fecha.
- A outra sessão (branch claude/zen-pascal-43131d) pôs a média dos lances em `detalhes` ("Propostas: 83 | Média: 24.10 USD") e criou `[cacada].max_propostas_freelancer` (30), que corta o aviso, não o envio.

## O que bloqueia

A página do projeto logada diz "Parece que você está sem ofertas" e "Suas Ofertas: FREE MEMBRO 0/6 restantes". Sem lance, o formulário nem aparece, então não dá para ler os campos nem provar o envio.

## Quando os lances voltarem

1. Rodar `execucao/sonda_freelancer.py` logado e ler o formulário (valor, prazo, texto e o botão de enviar) e o "N/6 restantes".
2. Fazer `rodar` atender vários sites: preço um pouco abaixo da média dos lances (ele pediu "um pouquinho mais baixo da média"), dentro do orçamento; texto na língua do projeto; corte por `max_propostas_freelancer`; reserva de lances.
3. Como na 99Freelas: ensaio, botão "Enviar esta proposta" no Telegram e só depois ligado, com o ok dele.

## Comments
