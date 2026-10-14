Status: ready-for-agent

# Caçada logada

Aprovada por ele em 2026-10-14 ("pode usar o chrome da caçada, implementa"; "pode seguir com o plano").

## Por quê

Nas candidaturas de 13/10 (caçada `2026-10-12-1832`, 69 em *Tentar a sorte*), muito do que a caçada trouxe não dava para mandar, e só se via isso logado:

- Freelancer.com: 3 dos 6 melhores eram "aberto apenas a freelancers selecionados" (pede saldo de US$ 20); a conta grátis tinha só 3 lances e a caçada trouxe 44 projetos de lá; números de propostas do relatório não batiam com a página (282 contra 30); o mesmo anúncio veio duas vezes com IDs diferentes ("Build My Shopify Store").
- 99Freelas: 2 de 8 já tinham caído (cliente cancelou / já escolheu freelancer); cada proposta custa 1 a 3 conexões (sobravam 15).
- VintePila: os 3 estavam "Inelegível" (5 de 5 candidatos).
- freelancer.com.br: responder pede plano pago (R$ 75 / 3 meses).
- Bounties da SUSU-LABS eram isca com malware (já barrados em bdc666b).

## O que muda

A caçada usa o **Chrome da caçada** (perfil `%LOCALAPPDATA%\whis\navegador-cacada`, onde ele entra uma vez à mão pelo `whis navegador`) para buscar e conferir nos sites em que está logado. Onde não está logado, tudo segue como hoje (API, página pública, explorador web).

1. **Leitor logado**: Playwright em Python (`launch_persistent_context`, `channel="chrome"`, com janela fora da tela — o X mostrou que sem janela é barrado), sem agente do Claude. Detecta login por site. Perfil em uso (Chrome da caçada aberto à mão) → aviso no relatório e caçada segue sem login.
2. **Freelancer.com logado**: sai o "aberto apenas a freelancers selecionados"/saldo mínimo; número de propostas visto logado; lances restantes lidos ("N ofertas restantes de 6"); anúncios repetidos (mesmo cliente + mesmo título) viram um. Sem login, o caminho pela API de hoje continua.
3. **99Freelas logada**: sai fechado, cancelado ou com freelancer escolhido; detalhe com o custo em conexões e quantas sobram.
4. **VintePila**: busca logada na listagem; sai inelegível / 5 de 5. **freelancer.com.br**: detecta plano pago → site marcado como pago, nada de lá. O explorador web deixa de procurar nos sites cobertos pelo Chrome logado.
5. **Orçamento**: *Tentar a sorte* limitado por plataforma ao que dá para mandar (lances / conexões); Freelancer.com sem lance vira uma linha "sem lances até dia X"; nova chave `[cacada].encaixe_minimo_tentar` (padrão 40).
6. **Bounty**: organização do GitHub criada há menos de 90 dias ou sem histórico fica de fora (API pública).
7. **Relatório e `whis navegador`**: Fontes diz onde estava logado e avisa "entre de novo no X pelo whis navegador"; `whis navegador` sem argumento abre as abas dos sites para entrar.
8. **Limite da caçada** (pedido em 14/10): hoje ela vai até acabar o plano, o que serve para a madrugada de sexta (antes da virada de sábado 08:00). Fora disso precisa de limite. Nova feature: limite de tempo e de plano gasto, com padrão automático (sem limite quando a virada está perto; com limite nos outros dias), opções de linha de comando para mudar e `--sem-limite`.

## Critérios de aceite

- Cada item acima com teste (HTML real salvo em `tests/fixtures/cacada_logada/` para os leitores), suíte inteira verde.
- Sem login ou com perfil em uso, a caçada se comporta como antes e o relatório diz por quê.
- Prova na máquina dele: ele entra nos sites pelo `whis navegador`, roda `whis hunt --freelas` com limite, e o relatório mostra o filtro logado funcionando.

## Fora do escopo

Envio automático (`enviar_sozinho` fica como está), caçada de vagas, assinar planos, push.
