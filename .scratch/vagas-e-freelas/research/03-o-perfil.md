# Research 03 — O perfil

Levantado em 2026-10-02. Ticket: [03](../issues/03-o-perfil.md).

**Aviso de confiabilidade.** O vault real e o `config.toml` real estão no PC dele (Windows). Esta
pesquisa **não viu nenhuma nota de verdade**: tudo sobre o vault vem do **código** que escreve nele
(`src/whis/`), das specs e dos handoffs em `.scratch/`, e das fixtures de `tests/`, que são
inventadas (`Acme`, `Ana Lima`, `FN-123 frete`). O que os documentos registraram da máquina dele
(número de repositórios, nomes de projeto) está marcado com a fonte. Quem confere o vault real é ele.

## Resumo

- **O vault, por construção, guarda o trabalho do dia, não o profissional.** Diário, reuniões,
  cópias da daily e respostas descrevem *o que aconteceu no emprego atual*: o assunto dos commits,
  títulos de issue do time inteiro, mensagens de Slack, resumos de reunião. Não há nenhuma nota
  sobre ele como profissional: a pasta "perfil profissional" foi cogitada em 2026-08-14 e não
  entrou na estrutura (`vault.py:55-63`).
- **Dá para tirar o tipo de problema e o domínio; a stack, mal; a senioridade e o inglês, não.**
  O git do diário traz só hash, autor e assunto (`fonte_git.py:53`), sem arquivo nem linguagem. O
  idioma de trabalho é português com jargão em inglês (o prompt do resumo diz isso,
  `resumo_dia_claude.py:77-79`), mas o nível de inglês não aparece em lugar nenhum.
- **E a janela é curta e tem buracos.** O vault existe desde o fim de agosto de 2026, nada apaga nota
  (não há remoção em `vault.py`), mas **o diário só nasce quando ele roda `whis diario` à mão**:
  nenhuma tarefa agendada gera o diário (`automacao.py:59-62` registra só Daily, Vigia, Notícias e
  Reuniões). A Granola só vem desde 2026-08-31.
- **O "vault basta" de verdade são as fontes passivas relidas para o perfil, e não as notas.** Os
  repositórios em `[git].raiz` (15 repositórios e 8.815 commits na máquina dele,
  `fonte_git.py:222-223`) dão linguagens, frameworks (pelos manifestos), anos de histórico e a
  separação entre trabalho e pessoal pelo `user.email` e pelo remote. Isso tudo é local, gratuito e
  feito com um git que ele já tem instalado.
- **O Claude Code é a melhor fonte de "como ele trabalha", e a mais perigosa.** Os transcripts em
  `%USERPROFILE%\.claude\projects\<projeto>\<sessão>.jsonl` são texto puro com *cada mensagem,
  chamada de ferramenta e resultado*, inclusive o conteúdo dos arquivos do empregador. Pela documentação oficial, são apagados depois de
  `cleanupPeriodDays` dias (**30 por padrão**). Já o `history.jsonl` (cada prompt digitado, com o
  caminho do projeto) **nunca é apagado**. Uma leitura só de agregados (repositórios,
  extensões editadas, skills chamadas) é útil e não precisa mandar conteúdo a lugar nenhum.
- **A primeira corrida vai ter que pedir quase tudo o que uma candidatura leva**: currículo,
  formação e o semestre da faculdade, anos de experiência, nível de inglês, se pode citar a empresa
  atual, portfólio e GitHub público (o repositório do Whis é **privado**), o e-mail dedicado, o
  telefone, a cidade, o LinkedIn, a pretensão por regime, as horas livres por semana e, para cadastro,
  CPF, data de nascimento, endereço e, num freela, dados para receber.
- **Separar "julgar" de "candidatar" encurta a primeira pergunta.** Para julgar bastam cinco ou seis
  respostas (inglês, anos, formação, horas, o que não quer mais fazer, se aceita CLT/PJ fora). O
  resto só é pedido quando aparece a primeira oportunidade de chance boa ou o primeiro cadastro.
- **Onde o perfil mora tem três desenhos viáveis**: um arquivo dele criado uma vez a partir de modelo
  (como `noticias/fontes.md`); um arquivo derivado na zona do agente, regenerável; ou os dois, com
  o dele mandando. Dados de cadastro (CPF, RG, endereço) levantam uma pergunta à parte: o vault é
  lido pelo `ask` e vai ao Claude.
- **Discrição: nada do que identifica o empregador sai numa candidatura.** Isso vale para nomes de
  colegas, de clientes, de projetos e de repositórios, para IDs e URLs internas, para código e para
  métricas. A experiência atual só sai em termos abstratos ("e-commerce, cálculo de frete") e só se
  ele autorizar citar a empresa. A regra mais segura é estrutural: **quem escreve a candidatura lê o
  perfil, não o vault cru**.

---

## 1. O que o vault contém, por construção

As pastas que `preparar` cria são `reunioes/`, `transcricoes/`, `diario/`, `daily/`, `respostas/`,
`notas/` e `noticias/` (`vault.py:46-63`). `prompts/` nasce quando o primeiro prompt é guardado
(`prompts.py:24`). **Nenhum código apaga nota do vault**: a única remoção do pacote é em
`automacao.py:289` (atalho) e `configuracao.py:572` (temporário do TOML). A retenção, então, é
"para sempre, a partir de quando a nota nasceu", e o que limita a história é **quando** cada coletor
começou a rodar e **se** ele rodou.

### 1.1 Pasta por pasta

| pasta | quem escreve e quando | campos e corpo | retenção real | o que revela para o perfil |
|---|---|---|---|---|
| `diario/YYYY-MM-DD.md` | o coletor do diário, **só quando ele roda `whis diario`** (sem tarefa agendada: `automacao.py:59-62`; `[diario].hora_da_tarefa` é lido, `configuracao.py:312`, mas nada agenda) | frontmatter `data`, `tipo`, `janela`, `fontes`, `fontes_com_falha`, `temas`, `reunioes` (`vault.py:290-299`); narrativa, *Destaques*, *Pendências* (`vault.py:306-310`); listas cruas por fonte, uma linha por evento com hora, título, link e o detalhe em citação (`vault.py:419-426`) | regenera o dia ao rodar de novo (`diario.py:72-74`); nunca apagado; **só existe nos dias em que ele rodou** | **tipo de problema** (narrativa e destaques); **domínio** (`temas`: "nomes de projeto, repositório, sistema ou assunto", `resumo_dia_claude.py:101-103`); stack **só se** aparecer no assunto do commit; idioma: português com jargão em inglês (`resumo_dia_claude.py:77-79`) |
| ↳ git no diário | `fonte_git` | `` `hash` assunto ``, referência = nome da pasta do repositório, pessoas = autor (`fonte_git.py:191-197`); **sem corpo do commit** (`fontes-passivas/DEFERRED.md`), sem arquivos, sem diff | idem | volume e ritmo de commit; nomes de repositório (pessoal e trabalho misturados: "30 dos 52 commits eram de projeto pessoal", `fontes-passivas/spec.md:65`) |
| ↳ Linear no diário | `fonte_linear` | issue = `ID título — movida de X para Y / criada / atualizada`; comentário com o **corpo inteiro** em `detalhe` (`fonte_linear.py:338-456`); lê **tudo o que a chave enxerga**, não só o dele (`fonte_linear.py:3-7`); ~170 eventos num dia real (`fontes-passivas/DEFERRED.md:32`) | idem | tipo de problema do **time**; o dele só pelo `pessoas`/assignee; domínio do negócio pelos nomes de projeto |
| ↳ Slack no diário | `fonte_slack` (dorme desde 2026-09-11, mas o código segue) | `autor` + texto da mensagem em `detalhe` (`fonte_slack.py:690-691`), de canais, DMs e grupos (`fonte_slack.py:78`) | idem | quase nada de perfil; é o material mais sensível do empregador |
| `reunioes/YYYY-MM-DD-HHMM-<slug>.md` | coletor da Granola: pela palheta (`meetings`) ou pela tarefa `Whis-Reunioes`; puxa os **últimos 30 dias** que faltam (`reunioes.py:49`) e escreve **uma vez só** | `tipo`, `participantes` **sem e-mail e sem empresa** (`granola.py:115-125`), `granola`, `granola_id`; título, data por extenso e o **resumo da Granola literal** (`vault.py:244-261`); nota privada e transcrição não vêm (`granola.py:78-93`; plano gratuito) | permanente; começa em 2026-08-31 (`docs/adr/0002-gravacao-sai-do-whis.md`) | tipo de reunião (daily, planning, retro) → **processo** do time; domínio; o resumo pode vir **em inglês** por padrão da Granola (`docs/smoke-reunioes.md:45`), o que **não** mede o inglês dele |
| `transcricoes/` | ninguém escreve desde 2026-09-30 (`vault.py:6-8`) | transcrições diarizadas da era da gravação (Deepgram) | o que ficou, se ficou | fala dele em reunião, que é a única evidência de como ele se expressa; legado, provavelmente pouco |
| `daily/atual.md` (nota viva) | **ele**; o agente só acrescenta a pedido (`did`, `doing`, `note`, `doubt`, `do`, `done`) | seções *O que eu fiz*, *O que estou fazendo*, *Fazer*, *Dúvidas*, *Falar* (`nota_viva.py:25-37`) | **ele limpa depois da reunião**: guarda só o ciclo corrente | o trabalho **nas palavras dele**, que é a melhor evidência de tipo de problema e de como ele descreve o que fez |
| `daily/YYYY-MM-DD.md` | a geração da daily (tarefa `Whis-Daily` nos horários de `[daily].horarios`, ou `daily` na palheta) | `tipo`, `deck`, `gerada`; uma seção por slide com as linhas como ele as escreveu (`vault.py:434-458`) | permanente; **uma cópia por dia de daily**, desde 2026-09-30 neste formato (antes era roteiro do agente) | **é o histórico datado do que ele disse que fez**: a melhor fonte do vault para "o que ele já fez é fato" (regra do ticket 06) |
| `respostas/YYYY-MM-DD-HHMM-<slug>.md` | `ask` na palheta | `tipo`, `pergunta`, `achou`; a resposta e as fontes citadas (`vault.py:497-525`) | permanente | o que ele precisa lembrar e pergunta; sinal fraco de domínio |
| `noticias/YYYY-MM-DD.md` | o jornal, 08:20 (`Whis-Noticias`) | a edição: seções, *Aprender hoje*, *Para aprender*, custo, plano (`vault.py:658-760`) | permanente | interesses, não competência |
| `noticias/fontes.md` | **dele**; criado uma vez do modelo (`fontes_do_jornal.py:259-268`) | seções de feed; o modelo traz *Dev com IA*, *Música* (Guitar World, Production Expert, MusicTech, Universal Audio, Neural DSP, Kemper, Focusrite), *Time* (Corinthians) e *Nomes* (`fontes_do_jornal.py:33-115`) | dele | **o interesse por áudio e música** que sustenta "software de áudio como tentar a sorte" (ticket 06); foco em agentes de código. O arquivo dele pode ter mudado desde o modelo |
| `noticias/trilha.md` | o jornal, só acrescenta (`jornal.py:68-69, 357-366`) | `software: <assunto>`, `carros: <assunto>` por dia | permanente | o que o jornal **ensinou**, não o que ele sabe |
| `prompts/` | ele (e `stash` a pedido) | `.md` com `tags` e `favorito` (`prompts.py:1-9`) | dele | como ele usa IA: os prompts que reaproveita. Sinal bom de fluxo de trabalho com agente |
| `notas/` | **ele**; o agente nunca escreve | livre | dele | desconhecido; pode ter qualquer coisa, inclusive um currículo. O `ask` lê, salvo `[privacidade].pastas_privadas` (`ferramentas.py:69`) |

Observações transversais:

- **A busca só lê `.md`** (`ferramentas.py:28`). Um currículo em PDF solto no vault não é visto pela
  busca de hoje.
- **O `ask` também consulta git, Linear e Slack ao vivo**, até 14 dias para trás
  (`fontes_ao_vivo.py:37-40`), pelo mesmo coletor do diário.
- **O filtro `[privacidade].excluir` age antes do vault** (`coleta.py:66`): o que casa com ele
  nunca entrou numa nota, então o perfil também não o verá.

### 1.2 O que o `config.toml` sabe (`configuracao.py:47-100`)

- `vault` (o caminho), `[obsidian].vault` (ID).
- `[git].raiz` (na máquina dele, `C:/Users/gabri/development`, `fontes-passivas/issues/02-coletor-de-git.md:54`),
  `profundidade`, `excluir`, `autores`: **dizem onde estão todos os repositórios dele**.
- `[linear].api_key`: chave **Read**, limitada aos times dele (`fonte_linear.py:3-7`).
- `[slack].*`: tokens, `conversas_excluidas`, `so_com_mencao`.
- `[daily].horarios`: os dias e horas da daily, que mostram a rotina do time.
- `[privacidade].excluir` e `pastas_privadas`.
- **Não sabe** quais repositórios são pessoais. A chave `[daily].referencias_pessoais` existiu
  (`fontes-passivas/contrato-fonte-passiva.md:545`) e saiu com o roteiro da daily: não está mais
  em `CHAVES` (`configuracao.py:131-157`) e some quando o painel reescreve o arquivo
  (`configuracao.py:8-11`).

### 1.3 Veredito por eixo: dá para julgar uma vaga só com o vault?

| eixo | do vault | qualidade |
|---|---|---|
| **stack** | assunto de commit, `temas`, títulos de issue | **fraca**. Só aparece se alguém escreveu "React" num commit ou numa issue. O diário não guarda arquivo, linguagem nem dependência |
| **tipo de problema** | narrativa e destaques do diário, cópias da daily (*O que eu fiz*), resumos de reunião | **boa**, mas é tudo do emprego atual e em linguagem do domínio do empregador |
| **senioridade** | indireta: o merge é dele mesmo, depois de uma aprovação só (`fontes-passivas/contrato-fonte-passiva.md:531-533`); toca projeto pessoal com agentes | **não dá**: anos de experiência, cargo e escopo não estão em nota nenhuma |
| **idioma** | português com jargão técnico em inglês | **só o idioma de trabalho**; o nível de inglês para vaga "remoto para fora" é desconhecido |
| **domínio do negócio** | projetos do Linear, canais, `temas`, títulos de reunião | **boa**, e é exatamente o que não pode sair (seção 6) |
| **interesses** | `noticias/fontes.md` | **boa** para games e áudio como "tentar a sorte" |

Conclusão: **para julgar, o vault diz "o que ele faz agora", mas não "o que ele sabe"**. Faltam a
stack medida e a senioridade. As duas saem melhor das fontes da seção 2 (git e Claude Code) do que
das notas.

---

## 2. O que as fontes passivas dão além do vault, se lidas para o perfil

### 2.1 Git local (`[git].raiz`): a melhor relação valor/risco

Hoje o coletor pede só `%H %h %aI %an %s` (`fonte_git.py:53`). Uma leitura **para o perfil**, feita
uma vez por corrida e que roda **inteira no PC**:

| o que | como (git/arquivos) | revela |
|---|---|---|
| repositórios | a mesma varredura de `FonteGit.repositorios()` (`fonte_git.py:144-163`) | quantos projetos existem e quais estão vivos |
| **trabalho × pessoal** | `git config user.email` por repositório (já usado em `fonte_git.py:199-211`: e-mail do trabalho ≠ pessoal) e `git remote get-url origin` (org do empregador × `github.com/bielvelozo`) | a separação que a chave `referencias_pessoais` fazia à mão. Os documentos registram dois pessoais (`second-brain`/Whis e `renovo-hub`) e um monorepo do trabalho (`fontes-passivas/contrato-fonte-passiva.md:527-528`) |
| **linguagens** | `git ls-files` → contagem por extensão (ou bytes) | stack real e proporção |
| **frameworks e bibliotecas** | ler os manifestos: `package.json` (deps), `pyproject.toml`, `requirements.txt`, `composer.json`, `go.mod`, `Cargo.toml`, `*.csproj`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/` | React/Next/Nest, Django, Laravel etc.; testes, CI, containers |
| **anos de experiência (piso)** | data do primeiro commit dele em cada repositório (`git log --reverse --author=<email>`) | evidência mínima, só do que está na máquina |
| volume e constância | commits por mês, por repositório, só dele | ritmo; projetos pessoais vivos (portfólio) |
| o que ele escreve | assuntos e corpos de commit **só dos pessoais** | material citável |

Custo: o histórico inteiro de 15 repositórios saiu em 0,9 s (`fonte_git.py:222-223`), e `ls-files`
mais a leitura dos manifestos ficam na mesma ordem. **Risco**: nomes de repositório, de pacote
interno (`@empresa/...`) e de arquivo do trabalho são do empregador (seção 6). A saída precisa ser
agregada ("TypeScript 60 %, React, NestJS, Postgres"), nunca a lista crua.

O próprio Whis é evidência: Python 3.12, `claude-agent-sdk`, MCP com OAuth/PKCE, Playwright,
`pywin32`, pytest (`pyproject.toml`), com 63 commits dele desde 2026-09-04 (`git log`). Mas o
repositório `bielvelozo/whis` é **privado** (`gh api repos/bielvelozo/whis`), então não serve de
portfólio sem decisão dele. Para torná-lo público seria preciso limpar os documentos, que citam o
nome do monorepo do trabalho (`fontes-passivas/issues/02-coletor-de-git.md:55`).

### 2.2 Linear

Hoje lê `identifier`, `title`, `url`, `state`, `team`, `project`, `creator`, `assignee`, o
histórico de estado e os comentários (`fonte_linear.py:68-138`). Para o perfil, com a mesma chave
Read:

- **filtrar pelo `assignee` = ele** (hoje não filtra: lê o time inteiro, `fonte_linear.py:3-7`);
- acrescentar `labels { name }` (bug, feature, chore…), `estimate`, `cycle`, `priority`, em uma
  janela longa (90–180 dias), dentro do limite de 10.000 pontos por consulta e 2.500 req/h
  (`fonte_linear.py:20-22`);
- daí sai a **proporção bug × feature × infra** e o tamanho típico do que ele pega, que é o "tipo de
  problema" em forma de número.

Tudo ali é do empregador: o Linear serve para **medir**, não para **citar**. Ele não dá stack.

### 2.3 Slack

Não recomendado como fonte de perfil. É conversa do empregador (`fonte_slack.py:690-691`), dorme
desde 2026-09-11 e não diz nada de stack que o git não diga melhor.

---

## 3. Claude Code como fonte (candidata levantada por ele)

Confirmado na documentação oficial, em [Explore the .claude directory](https://code.claude.com/docs/en/claude-directory#application-data)
e em [settings-reference](https://code.claude.com/docs/en/settings-reference#cleanupperioddays),
lidas em 2026-10-02.

### 3.1 Onde e em que formato

- No Windows, `~/.claude` é **`%USERPROFILE%\.claude`** (ou `CLAUDE_CONFIG_DIR`, se definida).
- `projects/<projeto>/<sessão>.jsonl` guarda o *"Full conversation transcript: every message, tool
  call, and tool result"*. `<projeto>` é o caminho do diretório de trabalho com tudo o que não é letra
  nem dígito trocado por `-` (ex.: `C--Users-gabri-development-whis`), então **o nome da pasta já diz
  o repositório**.
- Ao lado ficam `projects/<projeto>/<sessão>/subagents/` (transcripts de subagentes),
  `.../tool-results/` (saídas grandes), `file-history/<sessão>/` (snapshots dos arquivos antes da
  edição), `plans/` (planos do plan mode) e `usage-data/` (relatório do `/insights`).
- **JSONL, uma entrada por linha.** Numa sessão real desta máquina as chaves comuns são `type`
  (`user`, `assistant`, `system`, `attachment`…), `sessionId`, `uuid`/`parentUuid`, `timestamp`,
  **`cwd`**, **`gitBranch`**, `version`, `entrypoint` e `message` (com `role` e `content`; no
  assistente, os blocos `tool_use` com `name` e `input`, por exemplo `file_path` e `command`; no
  usuário, os `tool_result`). **O formato é interno e não é contrato**: a versão observada tem dezenas
  de chaves que mudam entre versões. Um leitor tem que ser tolerante, como o da Granola
  (`granola.py:1-9`).
- "These files are plaintext… Transcripts and history are not encrypted at rest."

### 3.2 Retenção

- `cleanupPeriodDays`: *"The default is 30 days and the minimum is 1; setting `0` fails with a
  validation error."* A limpeza roda **na inicialização** do Claude Code e apaga transcript,
  subagentes, tool-results, file-history, plans etc. mais velhos que o período. No settings-reference
  a chave aparece como *Default: unset*, e o comportamento sem ela é o de 30 dias.
- **Não são apagados**: `history.jsonl` (*"Every prompt you've typed, with timestamp and project
  path"*, guardado até ele apagar) e a auto memory em `projects/<projeto>/memory/`.
- Transcripts do Claude Desktop/Cowork são guardados sem limite de idade, salvo
  `desktopSessionCleanupPeriodDays`.
- Consequência: para o perfil, o Claude Code dá **uma janela móvel de 30 dias de detalhe** (ou mais,
  se ele subir `cleanupPeriodDays` no `~/.claude/settings.json`, que é decisão dele) e **o histórico
  inteiro de prompts por projeto** no `history.jsonl`. Se o Whis quiser memória mais longa, ele
  teria que **destilar** agregados para o vault a cada corrida: o dado cru some em 30 dias.

### 3.3 O que dá para extrair (só agregados, calculados no PC)

| sinal | de onde | serve para |
|---|---|---|
| em que repositórios ele trabalha com agente | nome da pasta em `projects/` + `cwd` + `gitBranch` | lista de projetos ativos (cruza com a seção 2.1) |
| linguagens e tipos de arquivo que ele mexe | extensões em `tool_use.input.file_path` (Edit/Write/Read) | stack **viva** dos últimos 30 dias |
| ferramentas da linha de comando | primeira palavra de `tool_use.input.command` (Bash): `npm`, `pnpm`, `pytest`, `docker`, `gh`, `psql`… | ecossistema, testes, infra |
| **fluxo com agentes** | chamadas a `Skill`/slash commands (`/grilling`, `/research`, `/to-spec` aparecem no próprio map), subagentes, plan mode, worktrees, MCPs conectados | o diferencial dele, *"desenrolado com uma IA poderosa"* (ticket 06): spec-driven, multiagente, TDD com agente |
| quanto usa | sessões por dia, por projeto, duração | intensidade (vale como frase, não como número numa proposta) |
| como ele pede | `history.jsonl` (prompts digitados) | estilo de trabalho; **conteúdo sensível**, então só contagem e tema |

### 3.4 Riscos

- **Material do empregador está ali por inteiro**: o conteúdo dos arquivos lidos, a saída de
  comandos, o diff, às vezes segredo (*"If a tool reads a `.env` file… that value is written"*).
  Nada disso pode sair do PC, nem ir ao Claude como "contexto do perfil" de uma corrida que também
  lê vagas de terceiros (*prompt injection*, map).
- **As corridas do próprio Whis também viram transcript.** O resumo do dia, a busca, o jornal e o
  deck rodam pelo Claude Agent SDK (`busca_claude.py:462`, `resumo_dia_claude.py:314`,
  `jornal_claude.py:326`, `deck_claude.py:97`). O resumo do dia, por exemplo, manda os eventos
  de Linear e Slack. Esses transcripts caem em `projects/<cwd do Whis>`, e o leitor tem que **pular** essas pastas, senão o perfil
  mede o Whis e não ele. A documentação diz que o SDK Python não tem a opção `persistSession` do
  SDK TypeScript, e só a variável `CLAUDE_CODE_SKIP_PROMPT_HISTORY` evita a gravação.
- **A caçada também vai gerar transcript**, com o perfil e os dados de cadastro dentro (seção 5).
- Mitigação que a pesquisa sugere sem decidir: um extrator **determinístico em Python** (sem modelo)
  que lê os JSONL e devolve só contagens e nomes genéricos (extensões, comandos, skills), com
  `[git].excluir` e uma lista de pastas de projeto ignoradas. O modelo nunca vê o transcript.

---

## 4. O que o vault NÃO tem e o Whis vai precisar pedir

Regra que vem do ticket 06: *o que ele já fez é fato e não se inventa*. Logo, tudo o que é fato
biográfico ou contratual e não está no vault **é pergunta**, e não dedução.

### 4.1 Precisa para **julgar** (pergunta na primeira corrida, antes de caçar)

| item | por quê |
|---|---|
| anos de experiência como dev (e desde quando no emprego atual) | senioridade: filtra júnior/pleno/sênior; nada no vault diz |
| cargo atual e o escopo (front, back, full stack) | "web developer" (ticket 06) é largo demais para casar requisito |
| **nível de inglês** (leitura, escrita, conversação) | decide se "remoto para fora" (ticket 06) é chance boa ou tentar a sorte |
| formação: curso, instituição, semestre e previsão de conclusão | vaga que exige diploma; estágio/trainee x efetivo; e a agenda da faculdade |
| **horas livres por semana** e em que horários (concilia trabalho, faculdade e freela) | descartar freela grande com prazo curto (ticket 06) pede um número |
| o que ele **não** quer mais fazer (stack, tipo de empresa, tipo de tarefa) | o ticket 03 pede, e o vault não tem |
| pretensão por regime: CLT, PJ, em dólar (o piso de R$ 5 mil já existe; falta o PJ, que costuma ser maior) | comparar vagas de regimes diferentes |
| restrições contratuais: cláusula de exclusividade ou de não concorrência no emprego atual | freela e segundo emprego podem violar o contrato atual |

### 4.2 Precisa para **candidatar** (pede quando a primeira oportunidade exigir)

| item | observação |
|---|---|
| **currículo** atual (PDF ou texto) | base do "currículo ajustado" da entrega 1; se ficar no vault em PDF, a busca de hoje não o lê (`ferramentas.py:28`) |
| **a empresa atual pode ser citada?** nome, período, cargo | sem isso a experiência atual vira "empresa de e-commerce, desde 20XX" |
| experiências anteriores, projetos e conquistas que ele aceita contar | o vault só cobre desde o fim de agosto de 2026 |
| contato: e-mail **dedicado** (Gmail, vai no config, ticket 06), telefone/WhatsApp para cadastro | o e-mail do trabalho, nunca |
| cidade/UF (Matão-SP, ticket 06) e disponibilidade para presencial em Ribeirão Preto/São Paulo | formulário de vaga sempre pede |
| **LinkedIn URL** | só leitura e link; nada automático lá (ticket 06) |
| **GitHub público** e portfólio (projetos pessoais publicáveis, URLs ao ar) | o Whis é privado; `renovo-hub`, publicável? |
| foto | perfil de Workana/99Freelas/GeekHunter pede |
| data de nascimento, **CPF**, RG, endereço completo, PIS (só CLT, na admissão) | cadastro; o ticket 06 deixou o Whis preencher e "sair fora se for golpe" |
| dados para receber no freela (PIX/conta, CNPJ/MEI se tiver) | Workana e 99Freelas pedem para sacar; **saque nunca é sozinho** (o Whis nunca gasta nem move dinheiro) |
| apresentação curta (bio) e valor/hora de referência para os perfis dos sites | o perfil dos sites de freela é público |
| pronomes/gênero, PcD, raça | formulários de diversidade: **opcionais**, perguntar se ele quer responder sempre, nunca ou caso a caso |

---

## 5. Onde o perfil mora no vault (opções, sem decidir)

A **Zona de propriedade** (CONTEXT.md) tem três contratos: a zona do agente (regenerável), a do
usuário (`notas/`, intocável) e os arquivos do usuário que o agente cria uma vez a partir de modelo
(`noticias/fontes.md`, `fontes_do_jornal.py:259-268`) ou que escreve só a pedido (`prompts/`).

| opção | como | prós | contras |
|---|---|---|---|
| **A. Arquivo dele, do modelo** (ex.: `vagas/perfil.md`, com a mesma exceção de `noticias/fontes.md`) | o Whis cria uma vez com as perguntas da seção 4 em branco; ele preenche no Obsidian; o Whis nunca mais escreve | precedente que ele já usa; ele vê e corrige tudo; "o que ele fez é fato" vira literalmente o que ele escreveu | tudo o que o Whis mede (stack, ritmo) não tem onde ficar; a primeira corrida "pede" por arquivo, não por conversa; perfil defasa se ele não atualizar |
| **B. Arquivo derivado do agente** (ex.: `vagas/perfil-derivado.md`, zona do agente) | cada corrida regenera a partir de git, Claude Code e vault, com a fonte de cada afirmação, como o diário | atual sem esforço; mostra **de onde** veio cada fato (o que ele pediu nas respostas); corrige pelo "vault basta" | não serve para fatos biográficos; regenerar apaga correção feita à mão; o que o agente **deduz** pode ser lido como fato numa proposta |
| **C. Os dois, o dele manda** | `perfil.md` (dele, do modelo: fatos, preferências, respostas) + `perfil-derivado.md` (agente: evidências medidas); conflito → vale o dele, e o relatório aponta a divergência | separa fato declarado de evidência medida, que é a fronteira do ticket 06; cada um no contrato que já existe | dois arquivos para entender; precisa de regra clara de precedência na spec |
| **D. Em `notas/`** | ele cria `notas/perfil.md` à mão | zero exceção nova na zona de propriedade | o agente não pode criar nem do modelo; nada garante o formato; se `notas/` estiver em `pastas_privadas`, a busca não lê |
| **E. Fora do vault** (`%APPDATA%\whis\`, como o `config.toml` e o `granola.json`) só para **dados de cadastro** | CPF, RG, endereço, PIX numa chave/arquivo local, eventualmente cifrado para o usuário do Windows como o `granola.json` (`configuracao.py:198`) | dado de identidade fora do que o `ask` lê e manda ao Claude (`ferramentas.py:158`, busca no vault inteiro); fora de backup/sync do vault | o agente que preenche formulário ainda precisa ler; ele não vê no Obsidian; mais um lugar |

Pontos que valem para qualquer opção:

- **Dado de cadastro e perfil profissional têm sensibilidades diferentes.** O perfil pode ir ao
  Claude a cada corrida; CPF e endereço só no momento de preencher um formulário. Uma divisão do tipo
  A/C + E respeita isso.
- **Se o perfil ficar no vault, `ask` passa a responder sobre ele** (bom: "qual meu piso?"), e o
  `[privacidade].pastas_privadas` pode esconder a pasta do `ask` sem esconder da caçada, se a spec
  quiser.
- **O currículo**: guardar o texto em `.md` (a busca lê) ou o PDF (que a busca de hoje ignora,
  `ferramentas.py:28`). O "currículo ajustado" por vaga é saída da caçada, então mora na zona do
  agente, junto do relatório (ticket 04).
- **A primeira corrida "pede" como?** Com a palheta *dispara e some*, perguntar no meio da corrida
  não cabe. O natural é a corrida **parar antes de caçar** se faltarem os itens de 4.1, deixar a lista
  no relatório ou no arquivo do modelo e avisar por toast. É pergunta para o ticket 04/07.

---

## 6. Discrição: o que do vault é do empregador e nunca entra numa candidatura

Nota de escopo: no ticket 06 (Q10) ele disse que **discrição de busca** (não sinalizar que procura
emprego) só importa no LinkedIn. Esta seção trata de outra coisa: **confidencialidade do
empregador**, que vale em todo site. O que está no vault foi coletado do trabalho dele, e uma
proposta pública num site de freela não pode carregar isso.

**Nunca sai** (em proposta, currículo, perfil de site, amostra para cliente ou post):

- **Nomes de pessoas**: participantes de reunião (`reunioes/`, `participantes`), autores de
  comentário e de mensagem (diário: Linear e Slack), revisores.
- **Nome da empresa, de clientes, de parceiros e de fornecedores**, salvo autorização explícita
  dele para a empresa atual (pergunta da seção 4.2).
- **Nomes internos**: projetos e times do Linear, canais do Slack, nomes de repositório do trabalho
  (o monorepo), pacotes internos, nomes de sistema e codinomes.
- **Identificadores e links internos**: IDs de issue (`FN-123`), URLs `linear.app/<workspace>`,
  permalinks do Slack, links da Granola, de deploy e de staging.
- **Código, trechos, diffs, esquemas de banco e arquitetura interna**, venham do diário, dos
  transcripts do Claude Code ou do `file-history`.
- **Números do negócio**: volume, faturamento, clientes, incidentes, métricas de erro.
- **Conteúdo de reunião**: decisões, planejamento, roadmap, retros.
- **Segredos** que um transcript do Claude Code possa ter capturado (`.env`, tokens).

**Pode sair, se abstraído e se ele aprovar o nível de abstração**:

- **o tipo de problema** ("cálculo de frete e checkout num e-commerce", "integrações com APIs de
  terceiros", "automação com agentes de IA");
- **a stack** medida (linguagens, frameworks, ferramentas), que é dele e não do empregador;
- **o processo** em termos genéricos ("time ágil com daily, code review automatizado, deploy
  contínuo");
- **o tempo de casa e o cargo**, se ele liberar citar a empresa;
- **projetos pessoais** (Whis, `renovo-hub`), citáveis por inteiro se ele quiser torná-los públicos.

Sugestões estruturais para a spec, sem decidir:

1. **O redator de candidatura lê só o perfil** (seção 5), nunca o vault cru nem os transcripts. O
   perfil já nasce abstraído, e o que não está nele não pode aparecer numa proposta. É a mesma ideia
   da fronteira de `Ferramentas` (`ferramentas.py:1-13`).
2. **Uma lista de termos proibidos** gerada das próprias fontes (nomes de projeto e de time do
   Linear, participantes, nomes de repositório do trabalho, o domínio do e-mail do trabalho) e
   checada **por código** antes de qualquer envio, como o filtro de exclusão (`fontes.py:110-133`).
   Pelo mesmo motivo do diário, uma regra de prompt *"que o modelo pode escorregar é fraca demais"*
   (`fontes-passivas/spec.md:66`).
3. **A amostra para o cliente (ticket 09) nunca reaproveita código do empregador**, nem o que o
   Claude Code tem em `file-history`.

---

Fontes externas: [Explore the .claude directory — Application data](https://code.claude.com/docs/en/claude-directory#application-data),
[Settings reference — cleanupPeriodDays](https://code.claude.com/docs/en/settings-reference#cleanupperioddays).
