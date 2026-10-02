# 09 — A amostra para o cliente

Type: research
Status: resolved
Blocked by: 06

## Question

No freela com chance boa, o Whis entrega *"tudo mastigado"* (ticket 06), inclusive **uma amostra
para mandar ao cliente** — o exemplo dele é uma landing page — com **um link** que ele só copia.
Levantar:

- **Onde a amostra mora com um link que o cliente abre.** O artifact do jornal é privado da conta
  dele; o cliente precisa de link público. Candidatas: GitHub Pages na conta dele, Vercel, Netlify,
  Cloudflare Pages — custo, limite, se o link expõe o nome dele ou o do Whis, e como tirar do ar.
  Hospedar o *entregável* não fere o ADR 0001 (o Whis continua sem servidor), mas vale dizer isso
  na spec.
- **O que cabe numa amostra** sem virar o trabalho de graça: tamanho, tempo de corrida, e quando
  ela não faz sentido (freela que não é web).
- **O pacote inteiro** de uma oportunidade com chance boa: a vaga, por que casa, preço sugerido
  (abaixo do mercado ou ligeiramente abaixo, ticket 06), o texto da proposta, a amostra, o link
  para aplicar.

Achados em `../research/09-a-amostra.md`.

## Answer

[Research 09](../research/09-a-amostra.md).

- **Hospedagem: Cloudflare Pages por direct upload** (`wrangler pages deploy`), grátis, uso
  comercial permitido, URL `<nome-neutro>.pages.dev`. Vercel Hobby descartada (uso comercial);
  GitHub Pages expõe o perfil dele; artifact do claude.ai não serve ao cliente.
- **A Workana suspende proposta com link externo**: lá a amostra vai como anexo (print). Upwork e
  99Freelas aceitam link de portfólio, sem contato.
- **Amostra é conceito**: uma página, `noindex`, aviso de demonstração, nada de nome, contato ou
  marca real do cliente; sai do ar em 30 dias. Freela que não é web visual não tem amostra.
- O pacote segue os campos da seção 5 da pesquisa.
