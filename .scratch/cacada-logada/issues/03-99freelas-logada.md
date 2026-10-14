Status: resolved
Blocked by: 01

# 99Freelas logada

Sai fechado, cancelado, com freelancer escolhido; detalhe com custo em conexões e saldo.

## Answer

`fontes_da_cacada.conferir_99freelas_logada`, usada por `conferir_99freelas` quando a sessão está logada na 99Freelas. Pela página logada saem o cancelado (`status-5`), o em andamento/freelancer escolhido (`status-3`) e o fechado (sem link `/project/bid/`), todos somados em `fechadas`. O que ele já propôs ("Melhorar proposta") sai também, com contador próprio `ja_propostas`. Do aberto, o formulário `/project/bid/<slug>` põe nos detalhes "99Freelas: custa N conexão(ões); sobram M", onde M é o estoque atual (custo + restantes), e o estoque vai para o checkpoint (`conexoes_99freelas`). O exclusivo de assinante (`content-box-message fail`) fica com a regra de antes: a hora em que abre ou "até 24 h depois de publicado". Sem login, segue o `conferir_99freelas` público de antes.
