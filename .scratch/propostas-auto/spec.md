# Proposta automática na 99Freelas e aviso no celular

Pedido dele em 18/10: "fazer um módulo no Whis que acha isso daí, já envia as propostas, e com preço mínimo mesmo". Em 13/10, seis propostas baratas e específicas na 99Freelas (R$ 30 a R$ 50 líquidos) trouxeram um cliente (o Carmo, `cacada/2026-10-12-1832-propostas/painel-fotos-netlify.md`). A caçada chega tarde: projeto Shopify do Freelancer.com passa de 130 propostas em 2 h.

## O que muda

1. A **vigia de freelas** roda de hora em hora, das 07h às 23h (padrão de `[cacada].horarios_da_vigia_de_freelas`).
2. Cada projeto novo da 99Freelas que ele consegue entregar (Shopify continua sendo o nicho, mas fora dele também vale) ganha uma proposta específica escrita pelo Claude, no jeito das propostas de 13/10: sem citar IA, sem contato, sem link além do portfólio, sem preço no texto. O preço é a oferta mínima que o formulário aceita (o critério de 13/10). O Whis envia pelo Chrome da caçada e grava a nota em `cacada/propostas-auto/` com `status: enviada em <data> (...)`, que o *Funil* conta.
3. Travas em `[cacada]`, com estes padrões: aberto para quem não assina há menos de 24 h, menos de 80 propostas, nada de exclusivo de assinante, nada em que ele já propôs, no máximo 3 por dia, parar quando a proposta deixaria menos de 3 conexões.

   O pedido era "publicado há menos de 24 h e menos de 20 propostas". A leitura ao vivo de 18/10 às 02h mostrou que na 99Freelas todo projeto das últimas 24 h era exclusivo de assinante (9 de 9), e os que já tinham aberto para conta grátis estavam com 28 a 39 h e 40 a 136 propostas: nenhum passaria nunca. Ele escolheu contar as 24 h da hora em que o projeto abre para quem não assina (24 h depois de publicado) e aceitar até 80 propostas; com `propostas_auto_exclusivos = true` (se ele assinar) as horas contam da publicação.
4. Aviso no celular pelo bot do Telegram dele (`[celular]`), para cada proposta e para cada projeto novo do nicho no Freelancer.com: título, site, orçamento, propostas até agora e link. O toast continua.
5. Resumo do que saiu, por dia, em `cacada/propostas-auto.md`.

## Modos

`[cacada].propostas_auto`: `desligado` (padrão), `ensaio` (escreve, preenche o formulário sem clicar quando está logado, avisa no celular, não envia) e `ligado` (envia). O ensaio conta para a cota do dia, para mostrar exatamente o que teria saído. Só vai para `ligado` com o "pode ligar o envio" dele.

## Fora

- Freelancer.com: o User Agreement (seção 33) proíbe "robot, spider, scraper or other automated means" sem permissão escrita. Lá não há envio automático, só o aviso no celular.
- O piso de `[cacada].piso_freela` não vale aqui: ele pediu o preço mínimo de propósito.

## Regras dos sites

- 99Freelas: os termos não proíbem automação, mas punem spam (queda no ranking, bloqueio de propostas). Cada proposta é do projeto, nunca genérica, e são no máximo 3 por dia.
