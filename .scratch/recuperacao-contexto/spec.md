# Spec: recuperação de contexto — o vault responde

Status: ready-for-agent

Origem: [mapa second-brain](../second-brain/map.md) e a decisão em [Como o agente recupera
contexto](../second-brain/issues/08-recuperacao-de-contexto.md). As três decisões de escopo desta
spec foram fechadas com o usuário em 2026-09-04, logo depois de a daily rodar numa reunião real.
Glossário em `CONTEXT.md`; ADR 0001 (projeto separado, 100% local) governa a arquitetura.

## Problem Statement

O vault já tem memória: reuniões transcritas, diários e dailies com as listas cruas de git,
Linear e Slack. Hoje ele só responde a quem abre o Obsidian e procura à mão, sabendo de antemão
em que dia a coisa aconteceu. Perguntas que uma pessoa faz de verdade — "o que ficou decidido com
o Luan sobre o link coringa?", "quando foi que a gente mudou a retenção para 180 dias?", "o que
eu falei na daily de sexta?" — exigem abrir vários arquivos e reconstruir a resposta na cabeça.

É o último elo que falta: o Second Brain **guarda** bem e não **lembra**. E foi justamente para
ser lido por esta entrega que a daily passou a carregar as listas cruas.

## Solution

Um comando que responde perguntas sobre o próprio trabalho, com **busca agêntica** sobre o
vault: o Claude recebe ferramentas para procurar e ler notas, decide sozinho onde olhar, e
responde **citando os arquivos** de onde tirou cada afirmação. Sem índice, sem embeddings, sem
serviço novo.

Duas entradas sobre o mesmo código: uma pergunta avulsa (`second-brain perguntar "..."`) e uma
conversa no terminal (`second-brain chat`) para as perguntas de acompanhamento.

Quando o vault não bastar, ele pode **consultar as fontes ao vivo** — git, Linear e Slack —
pelos mesmos coletores que a daily já usa, herdando blocklist, filtro e régua de menção.

## User Stories

1. Como usuário, quero perguntar em português e receber a resposta no terminal, para não abrir o Obsidian e caçar arquivo.
2. Como quem confere, quero a resposta **citando as notas** de onde veio, para eu abrir a fonte e checar.
3. Como quem investiga, quero fazer perguntas de acompanhamento na mesma conversa, para refinar sem repetir contexto.
4. Como quem só quer um dado, quero uma pergunta avulsa que responde e sai, para caber num alias do terminal.
5. Como dono das minhas notas, quero uma pasta privada que a busca **nunca** abre, para escrever coisa pessoal no vault sem ela ir ao Claude.
6. Como usuário, quero que a resposta diga "não achei" quando não achar, para eu nunca confundir invenção com memória.
7. Como quem trabalha hoje, quero que ele consulte git, Linear e Slack ao vivo quando o vault não tiver a resposta, para perguntar sobre o que aconteceu há dez minutos.
8. Como dono da minha privacidade, quero que a consulta ao vivo respeite as mesmas réguas da daily, para a blocklist do Slack continuar valendo.
9. Como usuário com teto de custo, quero saber quanto cada pergunta pesou, para não descobrir tarde que o hábito ficou caro.
10. Como usuário, quero que ele escreva em `notas/` só quando eu pedir, para a minha zona continuar minha.

## Implementation Decisions

- **Costura única**: `responder(pergunta, *, configuracao, busca) → Resposta`, com o serviço
  externo atrás de uma porta injetada, como em toda entrega deste repo. Chat e one-shot são duas
  cascas finas sobre ela.
- **O agente não recebe o vault cru — recebe ferramentas nossas.** Esta é a decisão central e
  **refina o que o ticket 08 decidiu**. Lá está escrito "agente com `cwd` no vault, grep/leitura";
  na prática isso não entrega a **pasta privada** que o usuário pediu, porque um `cwd` com bash
  livre lê qualquer arquivo e a exclusão passaria a depender de o modelo obedecer. Com ferramentas
  próprias (`buscar_no_vault`, `ler_nota`), a fronteira é verificada no **nosso** código, em um
  ponto só, e testável. O espírito do ticket 08 continua: busca agêntica, sem índice, o modelo
  decidindo onde olhar.
- **Pasta privada configurável**: `[privacidade].pastas_privadas = []`, caminhos relativos ao
  vault. O que estiver sob elas não aparece na busca, não é lido e não é citado — nem por engano,
  nem sob pedido. Lista vazia = vault inteiro visível.
- **Toda resposta cita a fonte.** Uma afirmação sem arquivo ao lado é indistinguível de invenção,
  e o valor desta entrega é confiar na resposta sem reconferir tudo.
- **"Não achei" é resposta válida e melhor que um palpite** — a mesma regra que a daily já tem
  para lista vazia.
- **Fontes ao vivo pelos coletores existentes** (`fonte_git`, `fonte_linear`, `fonte_slack`), como
  ferramentas que o agente pode chamar. Reaproveitar não é economia de código: é o que faz a
  blocklist do Slack, o `so_com_mencao` e o filtro de exclusão **continuarem valendo** numa
  consulta ao vivo, sem ninguém precisar lembrar de reimplementá-los.
- **Fonte ao vivo é o segundo recurso**, não o primeiro: o prompt manda procurar no vault antes,
  porque a nota é gratuita e a API não.
- **Entradas na mesma camada** (decidido pelo usuário): `second-brain perguntar "..."` e
  `second-brain chat`, sobre a mesma costura. O nome `brain` do ticket 08 fica como alias
  opcional depois; o padrão continua sendo subcomando de `second-brain`, como todo o resto.
- **Escrita sob pedido explícito**: o agente pode escrever em `notas/` quando o usuário mandar na
  conversa, e em lugar nenhum por iniciativa própria. `vault.escrever` com zonas já garante isso.
- **Custo no log e no fim da resposta**, no formato que a camada 06 da entrega anterior fixou:
  equivalente da tabela da API, com o aviso de que a assinatura não cobra por token.
- **Idioma**: tudo em português — pergunta, resposta, mensagens de erro e log.

## Testing Decisions

- **Costura única**: `responder(pergunta, busca=BuscaFake()) → Resposta`. O fake guarda o que
  recebeu, como `DailyFake` já faz, e é assim que se prova o que **não** foi enviado ao Claude.
- **A fronteira da pasta privada é o teste que mais importa**: um arquivo dentro dela não aparece
  em `buscar_no_vault`, não é lido por `ler_nota` nem por um caminho com `..`, e não chega ao
  fake. Vale sondar nos dois sentidos, como a zona de propriedade já é sondada.
- **As ferramentas são testadas direto**, sem rede: busca, leitura, limites de tamanho e recusa
  fora da fronteira.
- **O adaptador real** ganha teste de tradução sem rede e um `@pytest.mark.rede` opcional, que
  gasta a assinatura e só roda de propósito.
- **As duas entradas pela CLI** (`main([...])`), verificando o que sai no terminal.
- Prior art: as duas entregas anteriores. Mesma forma — costura única, fakes nas portas, zero
  mock de detalhe interno.

## Out of Scope

- **Índice semântico e RAG** — o gatilho de reavaliação continua o do ticket 08: mais de ~2.000
  notas ou buscas conceituais falhando na prática.
- **Comportamento proativo** (o agente avisar sem ser perguntado) — depende de uso real, e o mapa
  já o registra como não especificado.
- **Interface gráfica** e qualquer coisa fora do terminal.
- **Busca de vagas e freelance** — em escopo do esforço, mas depende do perfil acumulado.
- **Backup do vault** — segue no mapa como não especificado.

## Further Notes

- O usuário escolheu as três decisões de escopo em 2026-09-04: pasta privada em vez de vault
  inteiro ou só zonas do agente; as duas entradas na mesma camada; e fontes ao vivo **incluindo o
  Slack**. A última foi escolhida sabendo que reabre a questão das DMs — e a resposta de projeto é
  reaproveitar os coletores, para as réguas já ajustadas valerem sem esforço novo.
- `[privacidade].excluir` continua **vazio** na máquina do usuário: o filtro de exclusão nunca foi
  exercitado com um padrão real. Vale exercitá-lo antes de a busca ao vivo entrar.
- O vocabulário desta spec segue o glossário: **Vault**, **Zona de propriedade**, **Fonte
  passiva**, **Sob demanda**.
