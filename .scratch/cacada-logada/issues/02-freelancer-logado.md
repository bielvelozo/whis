Status: resolved
Blocked by: 01

# Freelancer.com logado

Logado: sai 'aberto apenas a freelancers selecionados'/saldo; propostas vistas logado; lances restantes; anúncios repetidos (mesmo cliente + título) viram um. Sem login: caminho da API de hoje.

## Answer

`fontes_da_cacada.conferir_freelancer_logado`, chamada em `filtrar_o_que_da` depois do filtro pela API quando a sessão está logada no Freelancer.com. Abre cada projeto que passou pela API. Sai o "aberto apenas a freelancers selecionados"/saldo mínimo (contador `freelancer_so_para_selecionados`). Os detalhes passam a ter "Propostas: N (visto logado)" no lugar do número da API, e o aviso do saldo sai. Os lances restantes ("N ofertas restantes de 6" ou "N/6 restantes") vêm da primeira página que os mostra e vão para o checkpoint (`lances_freelancer`).

Repetidos: no `barrar_freelancer` (API, com ou sem login), o mesmo começo de descrição (minúsculas, espaços colapsados, 300 caracteres) com a mesma moeda e faixa de orçamento fica um só (contador `freelancer_repetidos`); a API pública devolve `owner_id` nulo e o anúncio repostado muda o título (40761844 e 40761877), então o dono só entra na chave quando vem preenchido. A consulta de projetos pede `full_description=true`. Página que não abre deixa o projeto como estava. Sem login, o caminho da API e o `AVISO_DE_SALDO_MINIMO` continuam iguais. Fontes ganha as linhas dos selecionados, dos repetidos e dos lances.
