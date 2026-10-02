# Mapa: vagas e freelas

Labels: wayfinder:map

Aberto em 2026-10-02, a pedido dele: *"quero começar o planejamento da funcionalidade do whis de
buscas freelances e vagas de emprego para mim"*. **É levantamento antes de spec.** Nenhuma linha
de código antes de uma spec aprovada por ele.

## Destination

Uma **spec construível** do *buscador de mais dinheiro* — palavras dele — que diga, com user
stories tiradas do dia dele: **onde o Whis caça** (os sites e como cada um se lê e se usa), **o que
deixa pronto** para cada vaga ou freela, **até onde age sozinho** em nome dele, **como a corrida
longa sobrevive** a horas de execução e aos limites da assinatura, e **o que faz no LinkedIn** com o
aval dele. O caminho é: o que ele quer (01, feito) → os limites da autonomia (06) → os sites (02),
o perfil (03), a corrida longa (07), o LinkedIn (08) e a amostra para o cliente (09) → onde o relatório e a aprovação vivem (04) →
spec (05).

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
  Com a autonomia que ele deu (ticket 01), isso vira também: não aplicar onde o empregador vê.
- **É a primeira vez que o Whis age fora do PC em nome dele.** Até aqui ele lê (git, Linear, Slack,
  X, Granola) e escreve no vault e no artifact dele. Criar conta, aplicar e publicar levam o nome
  dele, saem do PC e não voltam atrás. E o agente que age vai ler texto de terceiros (a vaga, o
  pedido do cliente) — o clássico caminho de *prompt injection*. As bordas são do ticket 06.
- **A corrida longa é a "pesquisa noturna" que a interface previu** (Q35): o contrato *dispara e
  some* foi desenhado para minutos e, nas palavras de então, *"provavelmente será reescrito"*.
  Ticket 07.
- **Rodada 3, curta, a perguntar**: *"sem freela por projeto"* contradiz o resto da resposta da
  rodada 2 (lido como *sim*); qual é a região dele; o provedor do e-mail dedicado; a divisão em
  entregas abaixo.
- **Termos candidatos ao glossário**, a fixar na spec: a oportunidade com **chance boa** (vai para
  ele) e a de **tentar a sorte** (o Whis envia) — o eixo que decide quem age.
- **Recomendação do agente, a confirmar com ele**: dividir em entregas. (1) **A caçada** — a
  corrida longa, os sites, e cada oportunidade com tudo pronto (por que casa, proposta, currículo
  ajustado) no relatório, sem enviar nada; prova se o que ela acha presta. (2) **Agir sozinho** fora
  do LinkedIn — contas, perfis, e enviar as de tentar a sorte. (3) **O LinkedIn** — análise do perfil, posts e
  publicação com aval. Mandar candidatura ruim no nome dele em escala é pior do que não mandar;
  a (1) mede a qualidade antes.
- **Sem personalidade**: o Whis só entrega informação direta (regra da demo de 04/09).
- **Custo**: ele decidiu (ticket 01) que a corrida gasta o que precisar, chamada à mão na véspera da
  renovação da assinatura, com o que sobrou da semana. O que importa medir não é o preço, é não
  comer a cota do trabalho (ticket 07).
- Comandos da palheta são em inglês (`hunt`? `jobs`?) — o nome sai da spec.
- Skills da casa: `/grilling` e `/domain-modeling` nos tickets de decisão, `/research` nos de
  pesquisa, `/to-spec` no último. Achados de research ficam em [research/](research/).

## Decisions so far

<!-- uma linha por ticket fechado: gist + link -->

- [O que ele procura](issues/01-o-que-ele-procura.md) — **um buscador de mais dinheiro**: vaga e
  freela nos sites de TI mais famosos, numa corrida longa chamada à mão na véspera da renovação da
  assinatura, que deixa tudo pronto e entrega um relatório. Perfil: o vault basta, o que faltar o
  Whis pede. Autonomia total fora do LinkedIn (contas, perfis, candidaturas); no LinkedIn, análise,
  posts e publicação só com o aval dele. Abriu os tickets 06 (limites da autonomia), 07 (a corrida
  longa) e 08 (o LinkedIn).
- [Os limites da autonomia](issues/06-os-limites-da-autonomia.md) — **o Whis só envia sozinho o que
  tem pouca chance**: o que tem chance boa chega a ele *"tudo mastigado"* (proposta, link, e no
  freela uma amostra como uma landing page) e ele envia; tentar a sorte (inclusive games e software
  de áudio) o Whis envia, fora do LinkedIn; no LinkedIn, nada. Emprego acima de R$ 5 mil, remoto ou
  perto da região dele, qualquer regime; freela abaixo do mercado se for rápido com IA, descartado se
  for grande com prazo curto. E-mail dedicado, nunca o do trabalho. O que ele fez não se inventa; o
  que ele consegue fazer pode esticar. Abriu o ticket 09 (a amostra para o cliente).

## Not yet specified

- Acompanhamento de candidaturas (vi, apliquei, entrevista, recusa) e respostas de cliente — com o
  Whis aplicando sozinho, alguém vai responder; ler a caixa dele é outra capacidade.
- Lembrar dele de rodar a caçada na véspera da renovação.

## Out of scope

<!-- trabalho conscientemente excluído deste esforço -->
