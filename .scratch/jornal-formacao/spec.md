# Spec: a formação do jornal com imagem, check de leitura e quiz de sábado

Status: ready-for-agent

Origem: conversa de 2026-10-06, aberta e fechada com ele numa sessão de brainstorming, no mesmo dia
em que *Aprender hoje* passou de software para negócios. Estende o [spec do jornal](../noticias/spec.md),
que continua valendo em tudo o que esta não mexe. Glossário em `CONTEXT.md`. Pede o **ADR 0005**
(camada 6): a página do jornal passa a guardar o que ele marca, fora do vault, e o Whis lê de volta.

## Problem Statement

A formação do jornal (*Aprender hoje*, uma aula de negócios; *Para aprender*, duas de carro) é a
parte de que ele mais gosta, mas tem dois problemas:

1. **Só texto.** Aula de mecanismo (slip angle, turbo, margem) sem figura é difícil de entender numa
   leitura rápida no celular.
2. **A progressão supõe que ele lê todo dia.** A trilha avança sozinha a cada edição; o dia que ele
   pula vira um buraco no meio do que vem depois. E nada reforça o que ele leu.

## Solution

- **Imagem em toda aula**: o Claude escolhe, aula a aula, entre **foto** (o assunto é uma coisa:
  um carro, uma marca, uma pessoa) e **esquema** (é um conceito ou mecanismo). A foto o Python tira
  da página que a aula usou como fonte; o esquema o próprio Claude desenha em SVG, com rótulos em
  português.
- **Check de leitura**: cada aula na página ganha o botão **"Li esta aula"**. O toque grava no banco
  do próprio artifact; toda manhã o Whis lê esse banco antes de escrever a formação. **Uma área só
  avança quando a aula dela foi marcada**: aula não marcada volta igual no dia seguinte, sem custo.
- **Quiz de sábado**: no sábado não sai aula nova. Sai o **Quiz da semana** sobre as aulas lidas
  desde o último quiz, mais as perguntas que ele errou ou não respondeu antes, até acertar. Ele
  toca na alternativa e vê na hora se acertou e por quê.

## User Stories

- Toda aula abre com uma figura: a foto do carro de que ela fala, ou um esquema simples (caixas,
  setas, rótulos em português) do mecanismo ou do conceito.
- Embaixo de cada aula há um botão grande **"Li esta aula"**. Toco e ele vira **"Lida ✓"**. Se
  toquei sem querer, toco de novo e desmarco (vale até a edição seguinte ler).
- Se eu não marcar, amanhã a mesma aula volta, com **"Pendente desde 07/10"**, e a trilha daquela
  área não anda. Se eu ler só uma das duas de carro, amanhã volta a pendente e vem uma nova.
- Também posso marcar pelo Obsidian: na nota da aula, troco `status: pendente` por `status: lida`.
- No sábado o jornal abre com o **Quiz da semana**: perguntas de múltipla escolha sobre as aulas
  que li desde o último quiz e as que errei ou deixei em branco antes. Toco numa alternativa, ela
  fica verde ou vermelha e aparece a explicação. A resposta fica guardada.
- Pergunta que errei ou não respondi volta no sábado seguinte, até eu acertar.
- Sábado sem nenhuma aula lida e sem pergunta atrasada: o quiz diz em uma linha que volta no
  próximo sábado.
- Se a página não conseguir guardar (aberta deslogado, permissão negada), o botão aparece apagado
  com uma linha dizendo por quê, e eu ainda leio tudo; no quiz, vejo a resposta mas ela não fica
  guardada.
- Se o Whis não conseguir ler o que marquei, a edição diz isso no topo e as aulas pendentes
  continuam pendentes: nada avança sem eu ter marcado.

## Implementation Decisions

### Decisões dele (não derivam do código)

- Imagem: **foto da fonte + esquema desenhado pelo Claude**. Não um gerador de imagem pago (API à
  parte, e rótulo de imagem gerada não é confiável).
- **Carro é sempre foto** (2026-10-06, depois de ver a primeira simulação): o esquema de downforce
  desenhava um carro com linhas e ele achou pior que as imagens reais. Aula de carro usa a foto ou
  o diagrama da página da Wikipédia do assunto, mesmo quando é mecanismo; esquema só em negócios.
- O check fica **na página**, não só no Obsidian (o Obsidian vale como segundo caminho).
- **Trava por área**: aula não marcada volta e aquela área não avança.
- **Sábado**: o quiz vem **no lugar** das aulas novas; as pendentes ainda aparecem.
- **O quiz cobra** as aulas lidas desde o último quiz **e** as perguntas erradas ou sem resposta
  de antes, até acertar.
- *Aprender hoje* é de **negócios e visão de produto** desde 2026-10-06, do zero (já no `master`
  de trabalho; esta spec não mexe nisso).

### Camada 0 — sonda (portão das demais)

Descartável, em `.scratch/jornal-formacao/research/00-banco-e-fotos/`, como as sondas do jornal
(achados em `research/00-banco-e-fotos.md`). Responde, com teste real na montagem **exata** dos
adaptadores do jornal (`.venv` do repo, `dontAsk`, **o CLI que `caminho_do_cli` escolhe** — hoje o
`claude.exe` do npm, 2.1.274 ou mais novo; o empacotado no SDK, 2.1.238, não recebe `ArtifactData`
—, `CLAUDE_CODE_ARTIFACT=1`, modelo `haiku`), num **artifact de rascunho novo** (nunca o do
jornal). A sonda anota a versão do CLI e as ferramentas que a sessão recebeu (`init.tools`).

1. O rascunho nasce **sem** `capabilities` (como o do jornal nasceu) e é republicado **com**
   `capabilities: {"db": {}}`: passa em `dontAsk` sem prompt? Precisa de `user: {}` junto?
   Republicar de novo **sem** `capabilities` mantém a declaração; **com** a mesma, também?
2. Uma sessão com `tools=["ArtifactData"]` grava (`set`) e lista (`list`) as coleções `leituras`
   e `respostas`? **Qual é o formato exato do resultado** (o texto do resultado da ferramenta, ou
   os JSON que a leitura grava em disco, se gravar; é isso que o Python vai ler, não o texto do
   modelo)? Quantos documentos vêm por página, e como vem o cursor da página seguinte? Guardar
   como fixture: um `list` feito **antes** do republish que declara o banco (o primeiro dia da
   camada 3), um de coleção **que nunca recebeu escrita**, um com uma linha e um com cursor. Só
   essas respostas exatas viram "vazio" no adaptador; qualquer outro erro é erro.
3. As linhas sobrevivem a um republish com HTML novo?
4. A página, aberta no claude.ai, grava pelo `claude.use("db")` e a sessão headless lê o que ela
   gravou? Quando aparece o pedido de permissão: no carregamento ou na primeira escrita? Negar
   chega como `null` do `use` ou como rejeição na primeira chamada? Provado pelo agente no
   navegador embutido se o claude.ai estiver logado nele; senão, vira o primeiro passo do gate
   humano.
5. Custo e tempo de uma leitura (as duas coleções numa sessão), frio e quente.
6. Fotos: para 12 URLs reais de fonte (as da trilha e das notas das últimas edições, Wikipédia e
   não Wikipédia), quantas têm `og:image` (ou `twitter:image`) que baixa pela `_baixar_imagem`
   atual? A da Wikipédia é a foto do assunto?
7. SVG inline num `<div>` da página aparece no app do celular sem CSP? (Esperado que sim: é HTML.)

Se 2 ou 4 falharem, a camada 0 para e volta para ele com a alternativa B da conversa (a página se
republica com o estado embutido pelo `artifact` capability, e o Whis lê o estado do HTML vivo que o
passo 1 do republish já traz).

### Camada 1 — imagem nas aulas (`jornal_claude.py`, `jornal.py`, `pagina_do_jornal.py`, `vault.py`)

- **Id da aula** (usado daqui em diante): `AAAA-MM-DD-negocios`, `AAAA-MM-DD-carros-1`,
  `AAAA-MM-DD-carros-2`, com a data em que a aula nasceu. Aula de carro nova recebe o menor
  número ainda não usado naquela data.
- `_AULA` ganha `visual` (`"foto"` ou `"esquema"`), `foto_de` (uma URL que está em `fontes`) e
  `esquema` (SVG). `SISTEMA_FORMACAO` ganha a regra: **foto** quando o assunto é uma coisa que tem
  foto na fonte (carro, marca, pessoa, lugar); **esquema** quando é conceito ou mecanismo. Esquema
  simples: `viewBox`, até uns 12 elementos, caixas, setas e rótulos curtos em português, só `fill`
  e `stroke` com `currentColor` ou as cores da página; **nenhum número, nome ou dado que não esteja
  no texto da aula** (esquema errado é fato errado, mesma regra do "não invente").
- `Aula` (em `portas.py`) ganha `visual`, `foto_de`, `esquema` e, depois do download, `foto`
  (caminho publicado `img/aula-<id>.jpg`) e `imagem` (a URL original da foto).
- **Foto**: o Python abre `foto_de` (só se estiver em `fontes`), tira `og:image` ou
  `twitter:image` do HTML e baixa pela `_baixar_imagem` que as capas já usam, para
  `img/aula-<id>.jpg`, que entra no mapa `files` da publicação junto com as capas. Falhou, a aula
  sai sem imagem (log, sem aviso: imagem é enfeite, como a capa).
- **Esquema**: o Python aceita só SVG que começa com `<svg`, tem até 30 KB e só usa elementos de
  uma lista fechada (`svg g rect circle ellipse line polyline polygon path text tspan defs marker
  title`) e atributos de desenho (sem `on*`, sem `href`/`xlink:href`, sem `style` com `url(`).
  Fora disso, descartado e a aula sai sem imagem. O SVG vai **inline** na página.
- Página: a figura no topo do cartão `.aula`, antes do texto. Foto com largura total, altura até
  280 px, `object-fit: contain` sobre o creme (não cortar o carro). Esquema num `<figure
  class="esquema">` com largura total e `color: var(--tinta)`.
- Nota da edição: foto como `![](<URL original>)` (como as capas); esquema como `![[<id>.svg]]`
  (o arquivo é escrito pela camada 2; nesta camada, sem nota de aula, o esquema fica só na página).
- Peso estimado: +1 a 2 mil tokens de saída por aula com esquema, uns US$ 0,10 a 0,15 por edição.
  A camada mede numa `--simular`.

### Camada 2 — a aula vira nota e a área só avança lida (`aulas.py` novo, `jornal.py`, `jornal_claude.py`)

- **Nota da aula**: `noticias/aulas/<id>.md`, zona do jornal, com o id da camada 1. Frontmatter:
  `tipo: aula`, `id`, `area` (`negócios`/`carros`), `data`, `status` (`pendente`/`lida`),
  `lida_em`, `visual`, `imagem` (URL original da foto), `trilha` (a linha da trilha), `quiz` (data
  do quiz em que entrou; vazio). Corpo: `# <título>`, a figura (`![](<imagem>)` ou
  `![[<id>.svg]]`), o texto, `Fontes: ...`. O esquema fica em `noticias/aulas/<id>.svg`.
- `aulas.py` é o módulo que **escreve e lê** essas notas (ida e volta testadas: o que ele escreve
  ele lê igual). O `status:` é lido como o dos pacotes da caçada (`acompanhamento.py`). Se ele editar
  o texto no Obsidian, a aula pendente volta com o texto dele.
- **Vagas**: negócios tem 1 vaga menos as pendentes de dias anteriores; carros, 2 menos as
  pendentes (nunca abaixo de 0). **Se já nasceu alguma aula hoje, não há vaga nenhuma**: a
  formação roda uma vez por dia. Sábado: 0 e 0 (camada 4).
- `PortaFormacao.ensinar(data, trilha, vagas)`: o pedido diz quantas aulas de cada área; o esquema
  só pede as áreas com vaga. **Sem nenhuma vaga, a formação nem é chamada** (custo zero).
- A edição mostra, por área, **as pendentes de dias anteriores (mais antigas antes), depois as
  nascidas hoje (já lidas ou não), depois as novas**. `Edicao.aprender` e `Edicao.para_aprender`
  continuam sendo onde elas aparecem. Aula pendente de dia anterior leva `pendente_desde` e a
  página e a nota mostram *"Pendente desde dd/mm"*.
- **A trilha não muda de regra**: ganha a linha quando a aula nasce, como hoje. Como aula nova só
  nasce depois de a anterior ser lida, a trilha continua sendo o que foi ensinado, sem buracos.
- **Rodar de novo no mesmo dia** não gera aula a mais nem colide id: as de hoje aparecem de
  novo, mesmo que ele já as tenha marcado entre uma rodada e outra (hoje a segunda rodada duplica
  as linhas da trilha; isso some).
- **Imagem da aula que volta**: a foto é baixada de novo da `imagem:` da nota a cada edição em que
  a aula aparece (o republish apaga os `img/*` fora do mapa); o esquema é relido de
  `noticias/aulas/<id>.svg`.
- `--simular` lê as notas de aula mas não escreve nenhuma; as aulas novas existem só na pasta
  temporária.
- Primeira edição depois da mudança: não há nota de aula, então não há pendente; a formação
  segue pela trilha que já existe.
- Nesta camada o único jeito de marcar é o Obsidian (`status: lida`); a página entra na camada 3.

### Camada 3 — o check na página e a leitura do banco (`pagina_do_jornal.py`, `marcacoes_claude.py` novo, `jornal.py`)

- **Publicação**: `pedido_de_primeira_publicacao` e `pedido_de_republicacao` passam a mandar
  `capabilities` exatamente como a camada 0 provou (esperado `{"db": {}}`) em **todo** publish, no
  lugar de "sem capabilities". O resto do republish (os três passos) não muda.
- **Banco** (regras padrão: ele é o dono e o único leitor): `leituras/<id da aula>` =
  `{lida: bool, em: ISO}`; `respostas/<id da pergunta>` = `{escolha: int, certa: bool, em: ISO}`.
- **Página**: o primeiro `<script>` da página (até aqui ela não tem nenhum). Cada aula ganha
  `<button class="li" data-aula="<id>">Li esta aula</button>`, com alvo de toque de pelo menos 44 px.
  No carregamento: `window.claude?.use("db")` (fora do claude.ai, como a página local do
  `--simular`, `window.claude` nem existe). Vindo `null` ou nada, o botão fica apagado com *"Para
  marcar, abra logado no claude.ai."*. Com o banco, lê `leituras` e pinta "Lida ✓"; essa leitura
  pode trazer o pedido de permissão do claude.ai já no carregamento, e uma **rejeição** (permissão
  negada chega assim, não como `null`) apaga o botão com a mesma frase. O toque grava
  `{lida: !atual, em}` em `leituras/<id>`. Uma escrita por vez por aula; erro na escrita volta o
  botão ao estado anterior e diz *"Não consegui guardar"*. A página é lida inteira sem script. O que
  a camada 0 provar sobre permissão vale sobre o que está escrito aqui.
- **Leitura**: porta nova `PortaMarcacoes.ler(url) -> Marcacoes` (`leituras: {id: lida_em}`,
  `respostas: {id: Resposta}`), adaptador `MarcacoesClaude` em `marcacoes_claude.py`: Haiku,
  `tools=["Artifact", "ArtifactData"]` (só `ArtifactData` nasce sem ferramenta nenhuma),
  `AMBIENTE_DA_PUBLICACAO`, o CLI de `caminho_do_cli`. **Lê só o que interessa, com `query`**:
  `leituras` com `where em >= <data da aula pendente mais antiga>` e `respostas` com `where quiz in
  [<datas dos quizzes com pergunta ainda sem resultado>]`, `limit` 1000, seguindo o `next_cursor`
  até a última página. Sem aula pendente nem pergunta sem resultado, **a leitura nem roda**.
  `out_dir` é negado em `dontAsk` (camada 0), então **o Python lê o texto do resultado da
  ferramenta** (uma linha JSON por documento entre `=== BEGIN ARTIFACT DB` e `=== END`), nunca o
  texto do modelo, como `url_publicada` já faz. Resultado com `next_cursor` sem a página seguinte
  lida, permissão negada ou texto fora do formato → `ErroDeMarcacoes`: nunca perder marcação em
  silêncio. Os dois "vazios" exatos da camada 0 (coleção nunca escrita; banco ainda não
  declarado) são vazio, não erro.
- **Quando**: depois da escolha e antes da formação, só se existe `ultima_url(vault)` e há algo a
  ler. Custo
  esperado na faixa da publicação (US$ 0,01 a 0,05); a camada 0 mede. **No primeiro dia** da
  camada, a leitura roda antes do primeiro publish que declara o banco: banco não declarado conta
  como vazio, sem aviso.
- Em `--simular` a leitura roda (só lê) e o resultado vale na memória para as vagas daquela
  simulação; nada é escrito no vault.
- **Sincronização** (não em `--simular`): aula `pendente` com `leituras[id].lida` vira `lida`, com
  `lida_em`. Aula já `lida` no vault não volta a pendente (desmarcar vale só até a edição seguinte
  ler). `status: lida` posto à mão no Obsidian conta igual. As respostas vão para as notas de quiz
  (camada 4).
- **Falha na leitura**: aviso da edição *"não consegui ler o que você marcou na página; as aulas
  pendentes continuam"*, edição parcial (código 3); vale o que está no vault. Nada avança por
  falha.
- `MarcacoesFake` em `fakes.py` para `--fakes`.

### Camada 4 — o quiz de sábado (`quiz.py` novo, `quiz_claude.py` novo, `jornal.py`, `pagina_do_jornal.py`, `vault.py`)

- **Sábado** é o dia da edição em BRT. Na edição de sábado não há vaga de aula (camada 2): as
  pendentes aparecem, a formação não é chamada, e entra o **Quiz da semana** como a primeira seção
  da página e da nota.
- **Perguntas novas**: **1 por aula lida e ainda sem `quiz:`**, sem teto: cada aula lida desde o
  último quiz entra (por construção, no máximo umas 21 numa semana: 6 dias × 3 aulas, mais as
  pendentes antigas lidas na semana). O primeiro quiz cobre tudo o que foi lido desde que a
  camada 2 entrou no ar; como as camadas saem juntas, é uma semana, no máximo. Porta `PortaQuiz.perguntar(aulas) -> tuple[Pergunta, ...]`, adaptador `QuizClaude`
  (modelo padrão da conta, sem ferramentas, saída estruturada). Cada pergunta: `pergunta`,
  `alternativas` (3 ou 4), `certa` (índice), `explicacao`, `aula` (id). Regras do prompt: só o que
  está no texto da aula; alternativas erradas plausíveis; português; para quem está aprendendo.
  Pergunta fora do formato é descartada.
- **Perguntas atrasadas**: de quizzes anteriores, as com resultado `errada` ou `sem resposta` cuja
  pergunta original ainda não foi acertada em nenhum quiz, as mais antigas primeiro, até 10. Voltam
  com texto igual e **id novo**, levando `origem` (o id da primeira vez). Uma pergunta sai da fila
  quando qualquer versão dela é acertada.
- `id` da pergunta: `<data do quiz>-q<N>`.
- **Nota do quiz**: `noticias/quiz/AAAA-MM-DD.md`, zona do jornal, escrita e lida por `quiz.py`
  (ida e volta testadas): por pergunta, o id, a aula, a `origem`, as alternativas com a certa
  marcada, a explicação e o `Resultado:` (`certa`, `errada`, `sem resposta`). As aulas que entraram
  ganham `quiz: <data>`. A sincronização diária (camada 3) escreve o `Resultado:` das que ele
  respondeu; as que estão sem resposta no sábado seguinte contam como `sem resposta`.
- **Página**: cada pergunta com as alternativas como botões grandes. Toque: as alternativas
  travam, a escolhida fica verde ou vermelha, a certa fica verde e a explicação aparece; com banco,
  grava `respostas/<id>` (uma vez; respondida não se responde de novo). Respondida antes (o doc
  existe): já carrega mostrando o resultado. Sem banco: revela igual, com *"Sua resposta não vai
  ficar guardada."*. A resposta certa vai no HTML (ele não é adversário de si mesmo).
- **Sem nada para perguntar**: a seção diz *"Nenhuma aula lida desde o último quiz. O quiz volta no
  próximo sábado."*.
- **Falha do `QuizClaude`**: as atrasadas saem mesmo assim e o aviso *"quiz novo indisponível
  hoje"* entra na edição.
- **Rodar de novo no sábado**: a nota do quiz de hoje já existe e é reaproveitada (mesmos ids).
- `QuizFake` em `fakes.py`.

### Camada 5 — testar o sábado sem esperar o sábado (`__main__.py`)

- `whis news --simular --sabado` e `whis news --fakes --sabado` fazem a edição de sábado em
  qualquer dia. `--sabado` sem `--simular` ou `--fakes` é erro de uso (código 2): a edição de verdade
  só é de sábado no sábado.

### Camada 6 — a casca (docs)

- **ADR 0005**: o jornal guarda o que ele marca (leitura e resposta) no banco do artifact, fora do
  vault, e o Whis copia para o vault toda manhã. Por quê: o check tem de estar onde ele lê, no
  celular; o vault não é alcançável de lá. Consequência: a regra "nenhum estado fora do vault"
  ganha uma exceção de entrada (o vault segue sendo a verdade depois da cópia); depende de duas
  coisas não documentadas (`CLAUDE_CODE_ARTIFACT=1` e a ferramenta `ArtifactData` em headless).
- `CONTEXT.md`: **Aula** (pendente ou lida, a nota em `noticias/aulas/`), **Quiz da semana**; o
  verbete **Trilha** ganha que uma área só ganha linha nova depois de a aula anterior ser lida;
  **Jornal** ganha que a página guarda as marcações.
- `docs/smoke-jornal.md`: tocar "Li" no celular e ver a área avançar na edição seguinte; não tocar
  e ver a aula voltar pendente; marcar pelo Obsidian; `--simular --sabado`; o sábado de verdade,
  errar uma pergunta e vê-la voltar no sábado seguinte.

## Testing Decisions

- A sanitização do SVG: aceito; `<script>`; `onload=`; `href` externo; elemento fora da lista;
  acima de 30 KB; não começa com `<svg`.
- A foto: `og:image` e `twitter:image` de HTML de fixture; `foto_de` fora de `fontes` é ignorado;
  sem meta; download que falha → aula sem imagem e sem aviso; o arquivo entra no mapa `files`.
- Página e nota com aula de foto, de esquema e sem imagem; aula pendente com "Pendente desde".
- `aulas.py`: ida e volta da nota (com texto que tem `:`, `#` e quebra de linha); `status` posto à
  mão; vagas com 0, 1 e 2 pendentes de carro; formação não chamada sem vaga; rodar duas vezes no
  mesmo dia não duplica trilha nem aula; `--simular` não escreve nota.
- A leitura do banco com as fixtures da camada 0: coleção que nunca recebeu escrita (vazia, sem
  erro), uma aula lida, uma desmarcada, uma resposta, duas páginas pelo cursor; página seguinte não
  lida ou resultado ilegível → `ErroDeMarcacoes`; o texto do modelo é ignorado.
- Vagas com aula de hoje já lida entre duas rodadas: não abre vaga, a aula aparece de novo, o id
  de carro novo não colide.
- A sincronização: pendente → lida; lida não volta; Obsidian conta; falha da leitura vira aviso e
  nada avança.
- Os pedidos de publicação levam a declaração de `capabilities` da camada 0.
- O quiz: sábado sem vaga; 1 pergunta por aula lida sem `quiz:`, todas; teto de 10 atrasadas; atrasada volta com id novo e `origem`; sai da fila quando acertada em qualquer versão;
  sem resposta conta como errada no sábado seguinte; pergunta fora do formato descartada; falha do
  `QuizClaude` com atrasadas; nada para perguntar; reaproveitar no mesmo dia; ida e volta da nota.
- O script da página não roda na suíte (não há navegador nela). A suíte confere o HTML: botões com
  `data-aula`, alternativas com o índice certo, e que a página tem todo o conteúdo sem script. O
  comportamento no claude.ai é da camada 0 e do gate humano.
- `--sabado` sem `--simular`/`--fakes` dá código 2.
- Nada na suíte chama o Claude de verdade nem abre o artifact.

## Out of Scope

- Gerador de imagem pago e imagem gerada por IA em pixel.
- Repetição espaçada além de "errou, volta no sábado seguinte".
- Placar, histórico de acertos ou estatística do quiz.
- Quiz em outro dia que não sábado; marcar pela palheta ou pelo toast.
- Mudar o assunto ou o tom das aulas (negócios do zero e carros para iniciante continuam).

## Further Notes

- **Riscos**: `ArtifactData` em headless e `files` dependem de interruptores não documentados
  (`CLAUDE_CODE_ARTIFACT=1`; ver `noticias/research/09`). `ArtifactData` só vem no CLI do npm
  (2.1.274 ou mais novo): **sem ele, `MarcacoesClaude` falha todo dia** e a trilha para. Se a
  leitura quebrar, nada avança e a edição avisa, o que é o lado certo de errar, mas a trilha para
  até consertar.
- **Permissão no celular**: o claude.ai pode pedir permissão para a página guardar dados, talvez
  já ao abrir. Negada, o botão fica apagado até a próxima carga.
- **Ambiente do agente**: a prova de verdade (tarefa das 08:20, toque no celular, sábado) é dele
  ou de tarefa agendada descartável (ver a memória da sessão sobre `%APPDATA%` virtual).
- Sessões paralelas mexem neste working tree; cada camada confere `git status` antes de editar.
