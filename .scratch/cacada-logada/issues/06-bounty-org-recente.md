Status: resolved

# Bounty de organização recente

Organização do GitHub criada há menos de 90 dias ou sem histórico fica de fora (API pública), contada em Fontes.

## Answer

`fontes_da_cacada.barrar_contas_recentes`, chamada em `filtrar_o_que_da` logo depois de `barrar_organizacoes_bloqueadas` (SUSU-LABS continua contando como malware). Vale só para freela com link `github.com/<login>/...` (vaga em repositório, como frontendbr/vagas, é quadro de vagas e fica). Cada login vai uma vez a `https://api.github.com/users/<login>`; sai quando `created_at` tem menos de 90 dias ou quando `public_repos <= 2` e `followers == 0`. Erro de rede, HTTP de erro ou resposta sem esses campos deixam passar. Novo contador `Filtrado.conta_recente`, somado no checkpoint (`conta_recente`) e mostrado em Fontes: "N bounties de conta do GitHub recente ou sem histórico ficaram de fora." Testes em `tests/test_freelas_rapidos.py` com `httpx.MockTransport`.

Risco: a API sem token aceita 60 pedidos por hora por IP. Passando disso, as contas que sobram ficam sem conferência e passam.

