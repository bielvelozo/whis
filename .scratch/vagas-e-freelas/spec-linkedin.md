# Spec: o LinkedIn (entrega 3 de vagas e freelas)

Status: ready-for-human — construída em 2026-10-03 e provada sem rede (14 testes em
`tests/test_linkedin.py`); a prova real é o [smoke](../../docs/smoke-linkedin.md).

Origem: tickets [01](issues/01-o-que-ele-procura.md) e [06](issues/06-os-limites-da-autonomia.md) (no
LinkedIn, nada automático: *"eles me seguem"*), [research 08](research/08-o-linkedin.md), e o pedido
de 2026-10-03: *"faz a entrega 2 e 3 agora"*.

## Solution

- **`linkedin`** (palheta) / `whis linkedin`: lê o export de dados do LinkedIn
  (`[linkedin].exportacao`, `.zip` ou pasta) e escreve `linkedin/perfil.md` — nota de 0 a 100,
  diagnóstico, os passos de discrição *antes de mexer*, e título, *Sobre*, experiências e
  competências prontos para colar. Escreve `[linkedin].posts_por_vez` rascunhos em
  `linkedin/posts/AAAA-MM-DD-<slug>.md`, `status: rascunho`, a partir do perfil e do que ele fez
  (vault e git), sem repetir assunto já publicado. **Nada é publicado.**
- **`posts`** (palheta, lista): os rascunhos e os publicados; **Enter publica o selecionado** — é
  o aval. `whis linkedin-publicar <nota>` faz o mesmo perguntando `[s/N]`.
- **`whis linkedin-login`**: OAuth do app dele (*Share on LinkedIn* + *Sign In with OpenID
  Connect*, self-serve), retorno em `http://localhost:8765/linkedin`, token de 60 dias cifrado com
  DPAPI em `cofre.bin` ao lado do config.
- Publicação pela Posts API (`/rest/posts`, `LinkedIn-Version` de dois meses atrás,
  `commentary` escapado como *little text*). Publicado, a nota ganha `status: publicado`, `url` e
  `publicado` no frontmatter; o corpo — o texto que ele editou — fica byte a byte.

## Implementation Decisions

- **Sem navegador logado no LinkedIn** (research 08): ler o perfil é o export; publicar é a API
  oficial; mudar o perfil e se candidatar ficam com ele, com o texto pronto. Por isso não há ADR.
- **O rascunho é dele depois de nascer**, como a nota viva: o Whis cria a nota e, ao publicar,
  só troca o frontmatter. O texto publicado é o da nota na hora do Enter.
- **Método da skill `li-post`** (gancho que sobrevive ao corte, uma ideia, fecho com uma pergunta)
  portado para o prompt em português; o humanizador dela não entrou (estraga português, medido).
- **Discrição no prompt e na análise**: nada de "novos desafios" nem *Open to Work*; nada do
  empregador, de clientes, colegas, código ou métricas internas.
- `linkedin/` é zona do agente, com a exceção dos rascunhos, que ele edita.

## Out of Scope

- Carrossel, imagem, agendamento de post, comentários e respostas (skills `li-carousel`,
  `li-comment`, `li-reply` da referência).
- Ler o feed ou as mensagens do LinkedIn.
