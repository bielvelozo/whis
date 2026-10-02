# 08 — O LinkedIn

Type: research
Status: resolved

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

[Research 08](../research/08-o-linkedin.md). **Navegador logado no LinkedIn não é necessário.**

- **Ler vagas**: a busca pública (*guest*), sem login, nunca a conta dele — entrou na entrega 1.
- **Analisar o perfil**: o export de dados (*Baixar seus dados*), que ele baixa e o Whis lê.
- **Escrever posts**: portar `li-post` e `li-profile` da skill indicada para prompts em português
  (o humanizador estraga português, medido).
- **Publicar**: API oficial *Share on LinkedIn* (`w_member_social`), self-serve, token de 60 dias.
- **Mudar o perfil e se candidatar**: sem API; o Whis prepara, ele cola e clica.
- **Discrição**: nunca *Open to Work*; desligar o aviso de mudanças antes de mexer em experiência.

As quatro últimas são a entrega 3.
