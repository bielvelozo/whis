# 08 — O LinkedIn

Type: research
Status: open

## Question

No LinkedIn o Whis faz quatro coisas, todas **com o aval dele**: analisar o perfil, escrever posts,
publicá-los, e (talvez) aplicar em vagas. Como cada uma se faz, com que risco para a conta
principal dele?

Ponto de partida, levantado em 2026-10-02:

- **A skill que ele indicou** ([linkedin-agent-skill](https://github.com/Jakeschincariol/linkedin-agent-skill),
  MIT) são onze skills de Claude para escrever post, comentário, resposta, plano semanal, nota do
  perfil e "humanizar" o texto. **Ela não publica, de propósito**: entrega o texto para colar. Serve
  para o Whis *escrever*; publicar é com a gente.
- **Publicar no perfil pessoal tem caminho oficial e grátis**: o produto self-serve *Share on
  LinkedIn* (escopo `w_member_social`), sem revisão de parceiro, 150 chamadas por dia. Conferir na
  documentação da Microsoft antes de confiar — a skill diz o contrário.
- **Mudar o perfil e aplicar em vaga não têm API.** Só por navegador logado na conta dele, que fere
  os termos do LinkedIn — a mesma decisão do X ([ADR 0003](../../../docs/adr/0003-x-por-navegador.md)),
  com conta mais valiosa. Levantar o histórico de restrição de conta por automação.
- **Ler as vagas do LinkedIn** também é navegador logado. Medir o que dá para ler sem login.

Achados em `../research/08-o-linkedin.md`. Se o navegador logado entrar, vira ADR.

## Answer
