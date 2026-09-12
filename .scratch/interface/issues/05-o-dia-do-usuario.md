# 05 — O dia do usuário

Type: grilling
Status: resolved
Blocked by: 02, 03, 04

**Os três tickets de pesquisa fecharam em 2026-09-10** — a conversa pode começar, e chega com
fatos e números em vez de achismo. A entrega 3 nasceu errada exatamente por pular esta ordem.

## Question

Como é o dia dele, e onde o Whis precisa estar para caber nele?

- **Conte o seu dia**: a que horas é a daily, onde você está 5 minutos antes (PC? celular? já no
  Meet?), quantas vezes por dia você pensa *"preciso lembrar disso na daily"*, e onde você está
  nessas horas.
- **Onde o aviso tem que aparecer** para você ver, quando o Whis precisar te avisar de algo —
  daily pronta, reunião gravada, diário falhou, **login vencido**?
- Você quer **ler** a daily ou quer que ela **apareça**? (nota no Obsidian versus mensagem na DM
  versus toast)
- O que você está disposto a **digitar**, e onde? (pergunta longa no celular? um *"anota X"*?
  **um áudio?**)
- **A resposta na DM**: o que exatamente incomodou — o tamanho do texto, o bloco de fontes, ou
  ambos? Em que situação você **abriria** o arquivo citado? (*"toda resposta cita"* foi decisão
  sua na entrega 3, e foi o que te deixou pegar a auto-correção do fake; a hipótese a testar é
  que o incômodo seja o **tamanho do bloco**, não a existência da fonte.)
- **Configuração**: você quer mexer em `config.toml` ou quer que a pasta privada, a blocklist e o
  contexto do time sejam perguntas na DM?
- **A agenda**: a daily tem hora fixa, ou vem do Google Calendar? Quem mais está na reunião?
  (isto reabre *"integrar com a agenda"*, decidido na demo de 04/09)
- **O que da reunião de 04/09 ainda vale**: *"sem personalidade"*, *"a nota de pontos como
  contexto de tudo"*.

Perguntas que a pesquisa 02–04 acrescentou, cada uma porque a resposta **muda o que se
constrói**:

- **A agenda da daily está numa conta pessoal ou do trabalho?** App OAuth em *Testing* dá refresh
  token que **expira em 7 dias**; numa conta Workspace dá para fazer app *Internal* e escapar
  disso. Se for conta pessoal, ler o Calendar tem custo recorrente e a hora fixa no `config.toml`
  passa a competir de verdade.
- **Vale gastar a segunda rodada com o admin do Slack?** Ela compra duas coisas, e só elas:
  slash command (`commands`) e **ler imagem e áudio na DM** (`files:read`). Tudo o resto — daily
  entregue na DM, botões, thread, resposta mais curta — **já cabe nos scopes de hoje**. Mandar
  áudio em vez de digitar no celular é a única razão de peso para pedir de novo. É?
- **`/daily` daria o que *"gera a daily"* escrito na DM não dá?** O texto já funciona e custa
  zero. O slash ganha aparecer na lista de comandos do Slack e perde uma rodada de aprovação.
- **Que plugins do Obsidian você usa, e tem Obsidian Sync?** O vault do Whis não tem
  `.obsidian/plugins/`, mas você tem outros dois vaults. *Bases* (núcleo) já está ligado e daria
  painel sem plugin comunitário.
- **Um segundo lugar com a mesma informação te ajuda ou te atrapalha?** Uma nota-painel
  (`daily/hoje.md`) custa uma linha, mas é um segundo artefato do mesmo dado, que pode divergir —
  o crime exato pelo qual a página HTML foi revertida.

Duas perguntas novas, que só existem por causa do ticket 01:

- **Você percebeu que a bandeja parou de subir?** Ela está morta desde 09/09 e nada te avisou.
  Isso muda o peso que "saber que algo falhou" tem na sua lista?
- **Você chegou a rodar a daily e o diário nesta semana, e como?** O diário nunca foi agendado
  por código nenhum, ao contrário do que `[diario].hora_da_tarefa` sugere — então toda daily e
  todo diário que existem foram digitados por você no terminal. Quantos ficaram para trás?

## Answer

<!-- em andamento: o grilling começou em 2026-09-11 -->

### Rodada 1 — respostas do usuário, 2026-09-11

**Q1 — o horário da daily: não é um horário.** São três, por dia da semana: **14:00** na maioria
dos dias, **10:30 na quarta e na sexta**. Uma linha de hora fixa no `config.toml` não serve.
*(Onde ele está cinco minutos antes ficou sem resposta — repetido na rodada 2.)*

**Q2 — a agenda é conta Workspace do trabalho.** Some a armadilha do refresh token de 7 dias: uma
app *Internal* da organização escapa dela. **O Google Calendar volta a ser opção viável**, e com
três horários variáveis ele deixou de ser luxo.

**Q3 — fonte nenhuma, e resposta muito mais curta.** Palavras dele, e são a régua:

> *"se eu pergunto isso pro Luan que foi a última pessoa quem fez, ele não responderia 'Bom, de
> acordo com o histórico git em 25/08 ficou decidido bla bla...'. Ele só me falaria: mano, da
> última vez o João me pediu para deixar em 120 dias, então agora está assim."*

**Isto reverte uma decisão da entrega 3** (*"toda resposta cita"*, escolha dele na época, e o que
lhe permitiu pegar a auto-correção do fake em 10/09). O que substitui a citação como defesa
contra resposta inventada é pergunta da rodada 2.

**Q4 — precisa do áudio, e o scope `files:read` já foi adicionado por ele.** A segunda rodada com
o admin **não é mais bloqueio**. (A confirmar na hora de construir: o scope está na app e a app
foi reinstalada?)

**Q5 — personalidade, sim: a do Whis de Dragon Ball.** *"Sem muita firula, a não ser que eu comece
a brincar com ele. A informação e a economia de token na saída devem ser prioridade."*
**Isto reverte a decisão da reunião de 04/09** (*"não terá personalidade nem falará com o
usuário"*). Não é contradição com a Q3: o Whis do desenho é sereno e econômico — nunca prolixo.

**Q6 — ele quer uma interface de configuração**, para *"salvar e alterar variáveis de maneira
fácil"*. Não é `config.toml`, e não é pergunta na DM. Reabre a superfície candidata 5 (janela
local própria), que o levantamento tinha deixado por último.

**Q7 — ele não percebeu que a bandeja caiu porque não está usando nada do Whis no momento.**

**Esta é a resposta mais importante do grilling inteiro.** Ela reformula a entrega 4: não se trata
de polir uma ferramenta em uso, e sim de entender por que uma ferramenta que funciona parou de ser
usada. O porquê é a primeira pergunta da rodada 2.

### Rodada 2 — respostas, 2026-09-11

**Q8 — por que parou: (a) o atrito do terminal e (c) o conteúdo não serviu, "principalmente (c)".**
O handoff tinha a prioridade invertida: **a frente do conteúdo vem antes da frente da superfície.**

**Q9 — no PC, com o Meet aberto.** Os cinco minutos antes seguem sendo o gesto certo.

**Q10 — tabela por dia da semana**, não Google Calendar. O Calendar fica para se a reunião começar
a se mexer.

**Q11 — a fonte existe, mas só aparece se ele pedir** (*"de onde?"*, que o fio de 24 h sustenta).

**Q12 — roteiro seco, personalidade só na DM.** Dois prompts.

**Q13 — todas as 24 chaves na janela local, segredos inclusive.** Não fere a regra da entrega 3: o
valor vai do teclado dele para o arquivo, sem passar pelo agente.

**Q14 — áudio para os dois casos** (perguntar e anotar), sempre devolvendo o que entendeu.

### Rodada 3 — o diagnóstico do conteúdo, 2026-09-11

Ele mencionou ter dailies feitas à mão *"que são perfeitas"*. Elas estavam no vault:
`notas/Minha Daily.md` e `notas/Daily 2.md`. A comparação com `daily/2026-09-08.md` é o achado
central desta entrega:

- **Ele mantém uma lista viva; o Whis gera uma narrativa nova a cada execução.** Os dois arquivos
  dele são o mesmo trabalho com um dia de diferença, com itens subindo de *"O que estou fazendo"*
  para *"O que eu fiz"* e o que continua aberto **carregado com as mesmas palavras** (os Problema
  A/B/C do FN-1784 aparecem idênticos nos dois). O Whis re-descreve o mesmo trabalho com palavras
  novas todo dia — **e é por isso que ele lia e não conseguia explicar**.
- **Ele organiza por quem pediu** (*"as correções que o Ribeiro apontou"*, *"o Lucas queria"*,
  *"o Gideon pediu"*); o Whis organiza por status de entrega.
- **Ele ancora no sintoma** (*"Antes: esse toast aparecia quando você só reordenava as fotos"*);
  o Whis ancora no commit.
- **Metade do que ele escreve não está em fonte nenhuma** — *"teve uma cliente que tentou 5 vezes
  e desistiu"* é observação dele.
- **O `notas/daily.md` que o Whis criou está vazio.** Nunca foi usado. O `daily --anotar` e o
  `anotar X` da DM escrevem num arquivo que ele não usa.

**Respostas:**

- **Q20 — confirmado, e refinado por ele**: *"a parte do 'estou fazendo' que depois vira 'o que foi
  feito' é o **core** da minha daily"*. Não é a lista: é a **transição** entre as duas seções.
- **Q21 — uma nota viva só**, que ele edita. As listas cruas podem continuar por dia.
- **Q22 — as duas seções dele, mais uma de Dúvidas que ELE anota** — *"é muito difícil ele
  entender em que eu tenho dúvida"*. Seção de dono declarado dentro da nota: o agente nunca
  propõe nem escreve ali.
- **Q23 — agrupar por quem pediu é estrutura de verdade**: *"é importante saber quem pediu"*.
- **Q18 — a bandeja continua com o gravar e ganha um item que abre a janela.**
- **Q19 — uma tarefa agendada separada** confere se o resto está de pé e avisa por DM.
- **Q17 — a janela local deve ter "tudo de função possível"**, e ele perguntou se seria muito mais
  complexo fazer um app aberto por atalho de teclado, **no estilo Raycast**. Virou pesquisa:
  [research/05-janela-local-e-launcher.md](../research/05-janela-local-e-launcher.md).
- **Q16 — o diário: ele respondeu "NÃO", e a pergunta era dupla.** Ambíguo de propósito não
  resolvido: repetido na rodada 4.

### Rodada 4 — 2026-09-11

- **Q24 — o diário não serve e ele nunca leu.** **Suspender**, não agendar.
- **Q25 — o agente move o item sozinho** quando o sinal é forte (PR mergeada, issue em Done), e
  ele corrige o que estiver errado. **Regra dura junto: ao mover, carrega o texto dele sem
  reescrever uma palavra.** É o conserto exato do que o fez parar de usar.
- **Q26 — o agente lê a seção de Dúvidas, nunca escreve nela.** Mesmo contrato de `notas/`.
- **Q27 — a divisão que ele desenhou**: a DM para **perguntar e anotar**; a janela para **ações**
  (gravar, gerar a daily). E a frase que abriu a rodada 5: *"se fizer algo tipo o raycast, um
  atalho rápido para perguntas e anotação, aí o Slack pode morrer"*.

### Rodada 5 — o escopo verdadeiro aparece, 2026-09-11

- **Q28 — ele aceita matar o Slack, e o áudio junto**: *"se formos pra algo tipo raycast, sim, tá
  bem não termos o áudio pelo celular"*. **O Whis passa a ser 100% de mesa.** Custo assumido por
  ele: perguntar, anotar e receber a daily fora do PC deixam de existir, e o scope `files:read`
  que ele acabou de pedir ao admin fica sem uso.
- **Q29 — as ações que ele planeja não são botões, e não são pequenas**: buscar **vagas e
  freelas** com base no que ele faz, trazer **notícias de IA e tecnologia**, montar a
  **weekly/planning**, montar **slides** para uma daily mais formal, criar **reminders** — *"ele
  vai ficar um assistente pessoal realmente"*.

  Três consequências diretas para a spec:
  1. **É palheta de comandos, não painel com abas.** Quase tudo pede texto livre e é aberto.
  2. **Quase todo comando é longo e custa dinheiro** (o agente + rede). A palheta precisa de um
     contrato uniforme: dispara, não trava, o resultado cai em lugar durável e avisa quando fica
     pronto.
  3. **Duas capacidades novas aparecem**, e nenhuma existe hoje: **rede aberta** (notícias, vagas)
     e **artefato que não é nota** (slides). A entrega 4 precisa dizer se abre espaço para elas ou
     as recusa por ora.

  "Busca de vagas e freelance usando o perfil acumulado" já estava em *Not yet specified* no mapa
  original — o gatilho previsto era "depois que o perfil existir". O perfil existe.

### Rodada 6 — 2026-09-11

- **Q30 — o watchdog avisa por toast**, não por DM. Uma tarefa agendada que só sabe consultar
  `Get-ScheduledTaskInfo` e disparar um toast: não depende de rede, do Slack, nem de nada do Whis.
- **Q31 — o Slack dorme, não morre.** Código e tokens ficam; o atalho de logon não é instalado.
  Reavaliar em seis meses, quando o launcher tiver provado ou decepcionado.
- **Q32 — comando é "dispara e some"**: a janela fecha, roda em segundo plano, o resultado vira
  nota no vault e um toast avisa. Nenhum comando cabe numa janela que se fica olhando — a
  pergunta leva 60 s e a daily 40.
- **Q33 — a entrega 4 é só a casca mais o conserto da daily.** Ele recusou incluir um comando novo
  de prova. Os seis comandos futuros encaixam em slot pronto, um por vez.

### Rodada 7 — 2026-09-11

- **Q34 — terceira zona declarada**, com regra escrita no `CONTEXT.md`: o agente acrescenta e move,
  **nunca reescreve texto que já está lá**, e nunca encosta nas seções do usuário.
- **Q35 — a pesquisa noturna é feature futura; não projetar para ela agora.** *Risco assumido por
  ele, registrado aqui*: quando ela chegar, o contrato de comando provavelmente será reescrito,
  porque um comando de 8 horas atravessa suspensão, logoff e reboot, e o desenho de agora não.
- **Q36 — escritor de TOML nosso**, regenerando o arquivo a partir do `MODELO_DE_CONFIGURACAO`
  (que já carrega os comentários de cada chave), com backup antes de cada escrita. Zero
  dependência nova. Preço aceito: comentário escrito à mão no arquivo se perde.
- **Q37 — toast com botão** que abre a nota no Obsidian. Nada de janela abrindo sozinha na cara de
  quem está entrando na reunião.
- **Q38 — a nota viva é `daily/atual.md`.** Uma só. As `daily/YYYY-MM-DD.md` continuam nascendo ao
  lado, com as listas cruas de cada dia.
- **Q39 — quatro seções**: duas que o agente mantém (*O que eu fiz* / *O que estou fazendo*) e
  duas que são só dele (*Dúvidas* / *Falar*). `anotar X` passa a escrever em *Falar*.
  `notas/daily.md`, nunca usado, é aposentado.
- **Q40 — arrumar a casa é a camada zero da entrega 4**: renomear a pasta do repositório, refazer
  o `pip install -e .`, recriar atalhos e tarefa com os nomes novos. Não por higiene: a entrega
  inteira depende de um processo residente que hoje não sobe, e **o modo como isso quebrou é o
  próprio assunto da entrega**.

**Frontier vazio em 2026-09-11**, e o entendimento compartilhado foi confirmado por ele. A spec
saiu em [../spec.md](../spec.md) — ticket [06](06-spec-da-entrega-4.md).
