# Mapa: vagas e freelas

Labels: wayfinder:map

Aberto em 2026-10-02, a pedido dele: *"quero começar o planejamento da funcionalidade do whis de
buscas freelances e vagas de emprego para mim"*. **É levantamento antes de spec.** Nenhuma linha
de código antes de uma spec aprovada por ele.

## Destination

Uma **spec construível** da busca de vagas e freelas que diga, com user stories tiradas do dia
dele: **o que ele procura** (tipo de trabalho, critérios, o que o derruba), **de onde vem** (as
fontes e como cada uma se lê), **o que o Whis sabe dele** para julgar uma vaga, e **onde e quando
o resultado chega**. O caminho é: o que ele quer → onde as vagas estão → o perfil → onde a busca
vive no dia dele → spec.

## Notes

- Idioma: todos os artefatos deste esforço em português.
- **Origem**: é o item 4 da [ideia original](../../IDEA.md) (*"busca vagas de emprego e freelance
  usando o perfil que ele constrói a partir de tudo que observa"*), adiado como "fase 2" no
  [mapa do Second Brain](../second-brain/map.md) até o perfil existir, e o primeiro dos seis
  comandos futuros que ele listou no Q29 do [grilling da interface](../interface/issues/05-o-dia-do-usuario.md).
  Lá ficou escrito: *"o perfil existe"* — o vault tem diário, reuniões, a daily e as fontes
  passivas. **Falta conferir se isso basta para julgar uma vaga** (ticket 03).
- **A entrega certa é a que cabe no dia dele, não na arquitetura.** Lição de duas specs recusadas
  (entregas 3 e 4). Por isso o *grilling* do ticket 01 vem antes de qualquer pesquisa de fonte.
- **Não invente superfície nova onde uma que ele já usa serve.** O **Jornal** já é uma página
  diária no mesmo endereço, lida no celular, com fontes editáveis em `noticias/fontes.md`; a
  **Palheta** já tem slot para comando novo (hoje `vagas` dá "Não entendi"). Os dois são
  candidatos naturais a casa da busca — a decisão é do ticket 04.
- **Precedentes de rede aberta**: o jornal lê RSS e o X por navegador logado na conta dele
  ([ADR 0003](../../docs/adr/0003-x-por-navegador.md)). Se a melhor fonte de vaga for o LinkedIn,
  a pergunta é a mesma do X, com risco maior: o LinkedIn é conhecido por restringir conta que
  automatiza, e a conta é a vitrine profissional dele.
- **ADR 0001 vale**: tudo roda no PC dele, sem servidor. Claude pela conta dele.
- **Discrição**: ele está empregado. O que o Whis faz não pode sinalizar busca para fora (nada de
  "open to work", nada publicado em lugar que o time veja). A página do jornal é artifact privado.
- **Sem personalidade**: o Whis só entrega informação direta (regra da demo de 04/09).
- **Custo é por gesto e é medido**: uma pergunta ≈ US$ 0,56 e 60 s. Julgar dezenas de vagas por
  dia contra um perfil precisa de número antes de virar tarefa agendada.
- Comandos da palheta são em inglês (`jobs`? `gigs`?) — o nome sai da spec.
- Skills da casa: `/grilling` e `/domain-modeling` nos tickets de decisão, `/research` nos de
  pesquisa, `/to-spec` no último. Achados de research ficam em [research/](research/).

## Decisions so far

<!-- uma linha por ticket fechado: gist + link -->

## Not yet specified

- Candidatura assistida (rascunho de proposta, carta, adaptação do currículo) — só depois de a
  busca provar que traz coisa que presta.
- Acompanhamento de candidaturas (vi, apliquei, entrevista, recusa).

## Out of scope

<!-- trabalho conscientemente excluído deste esforço -->
