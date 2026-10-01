# Whis

Agente pessoal local que observa o trabalho do usuário no PC e recupera contexto, com um vault Obsidian como memória durável. Reunião não é gravada aqui: desde 2026-09-30 ela fica no Granola (ADR 0002).

## Language

**Coletor**:
Componente que captura um tipo de sinal (as fontes passivas de trabalho) e o transforma em notas no vault.
_Avoid_: watcher, observador, collector

**Fonte passiva**:
Dado de trabalho que já existe sem o Whis rodando — git local, Linear, Slack, histórico de navegador — lido retroativamente por um coletor.
_Avoid_: monitoramento, tracking

**Vault**:
O vault Obsidian local no PC do usuário — a memória durável do Whis, novo e sem legado de outros projetos.
_Avoid_: workspace, base de conhecimento, context/

**Sob demanda**:
Modo de operação de todo coletor: só roda entre um liga e um desliga explícitos do usuário; nunca escuta ou captura contínua.
_Avoid_: always-on, background

**Diário**:
Nota diária em `diario/` que resume o trabalho do dia a partir das fontes passivas.
_Avoid_: daily note, log

**Daily**:
Roteiro falado que o usuário lê na reunião diária do time. Vive na **Nota viva** (`daily/atual.md`); cobre da última daily até agora — não um dia civil. Cada geração deixa ao lado uma nota datada `daily/YYYY-MM-DD.md` com a janela e as listas cruas, que é o registro durável e de conferência. `[daily].ativa = false` desliga a daily: a tarefa `Whis-Daily` fica no Agendador mas não gera nada, e a palheta esconde *Generate daily*; só `whis daily` no terminal ainda gera uma.
_Avoid_: standup, resumo diário

**Nota viva**:
`daily/atual.md` — a terceira zona de propriedade: uma nota só, que agente e usuário mantêm juntos, dividida por seção. O agente cuida de *O que eu fiz* e *O que estou fazendo*: **acrescenta** o que é novo e **move** um item de *fazendo* para *fiz* quando o sinal é forte (PR mergeada, issue em Done), transportando a linha **literalmente** — nunca reescreve texto que já está lá, nunca apaga um item aberto. *Fazer*, *Dúvidas*, *Pontos* e *Falar* são só do usuário: o agente lê, nunca escreve por conta própria — os comandos `note` (→ *Pontos*), `doubt` (→ *Dúvidas*) e `do` (→ *Fazer*, com a caixa `- [ ]`) acrescentam uma linha a pedido explícito, e *Falar* ninguém toca além dele. Em *Fazer* quem marca `[x]` é ele, e a linha marcada fica onde está até ele a tirar: virar a janela da daily não mexe nela. A nota não carrega explicação nenhuma: ele sabe o que cada seção é. *O que eu fiz* é da janela da daily: ao abrir a janela seguinte, o bloco é arquivado literalmente na nota datada e a seção recomeça.
_Avoid_: painel, dashboard, `daily/hoje.md`, `notas/daily.md`

**Zona de propriedade**:
Divisão do vault em três contratos: as pastas que o agente cria e pode regenerar (`reunioes/`, `transcricoes/`, `diario/`, `daily/`, `respostas/`, `noticias/` — em `reunioes/` e `transcricoes/` nenhum coletor escreve desde que a gravação saiu; o diário, a daily e o `ask` só as leem); a zona do usuário (`notas/`), que o agente nunca toca; e a **Nota viva**, onde os dois escrevem, cada um nas suas seções. `prompts/` é do usuário como `notas/`, com uma exceção: o agente cria um arquivo novo ou troca a linha `favorito:` quando é mandado. `noticias/` é do agente (o **Jornal** e a **Trilha**), com uma exceção: `noticias/fontes.md` é do usuário — o agente o cria uma vez, a partir do modelo, e nunca mais escreve nele. `notas/daily.md` foi aposentado em 2026-09-12 — nunca foi usado; o que era dele vive nas seções do usuário da nota viva.

**Palheta**:
A janela de comandos do Whis, aberta por atalho global de teclado no PC (`ctrl+space`), no estilo Raycast: um campo de texto e uma lista de ações clicáveis, num painel acrílico translúcido; os comandos são em inglês (`daily`, `news`, `note`, `doubt`, `do`, `ask`, `open`, `prompts`, `stash`, `settings`), o rótulo de uma ação digitado inteiro vale como o comando, Tab completa o comando da ação selecionada, e a janela some ao despachar. Todo comando **dispara e some** — menos `prompts`, que troca a lista de comandos pela dos **Prompts** sem fechar a janela — roda em segundo plano, o resultado vira nota no vault e um toast avisa quando fica pronto. Substitui a DM do Slack como o lugar de perguntar e anotar; a bandeja é a casa dela, e o clique no ícone também a abre. Uma resposta de `ask` nasce em `respostas/`, zona do agente.
_Avoid_: launcher, painel com abas, chat

**Jornal**:
A edição diária de notícias do Whis: a nota `noticias/YYYY-MM-DD.md` (o dado) e a página publicada a partir dela como artifact privado da conta do usuário, sempre no mesmo endereço (a renderização, que ele lê no celular). Sai às 08:20 pela tarefa `Whis-Noticias`, ou por `news` na palheta; os feeds, os nomes que ele acompanha e o time vivem em `noticias/fontes.md`, que ele edita no Obsidian. Só existe no jornal o que veio de uma fonte com link; seção sem nada nas últimas 24 h diz isso em uma linha. Não é coletor (não observa o trabalho dele) nem fonte passiva. `[noticias].ativa = false` desliga a tarefa e esconde `news` da palheta.
_Avoid_: report, newsletter, feed

**Trilha**:
`noticias/trilha.md`, zona do agente: o que a formação do **Jornal** (*Aprender hoje* e *Para aprender*) já ensinou, uma linha por assunto por dia. A formação lê a trilha para progredir sem repetir e só acrescenta ao fim; nunca é reescrita.
_Avoid_: histórico, currículo

**Prompt**:
Um texto guardado para colar num chat de IA: um `.md` em `prompts/` no vault. O título é o nome do arquivo, e `tags` e `favorito` são propriedades do Obsidian. `stash <título> #tag` guarda o que está no clipboard; `prompts` abre a lista na palheta, onde o Enter cola o prompt na janela em que o usuário estava. Referência: o Prompt Stash do Raycast.
_Avoid_: snippet, template

**Vigia**:
Uma tarefa agendada fora do Whis (`Whis-Vigia`, um script PowerShell autossuficiente) que consulta o Agendador e a lista de processos e dispara um toast quando uma peça não subiu — a daily ou o jornal não nasceu, a bandeja não está no ar. Existe porque quem avisa que o Whis caiu não pode ser o Whis.
_Avoid_: watchdog, healthcheck

**Tracer bullet**:
A primeira fatia construível de ponta a ponta: "aperto um botão durante a reunião → nota transcrita/resumida aparece no vault". Histórico: a gravação saiu do Whis em 2026-09-30 (ADR 0002).
_Avoid_: MVP, PoC

**Whis**:
Este projeto. Nasceu chamado *Second Brain* e foi rebatizado em 2026-09-09, herdando o nome do agente anterior do usuário, que morreu de vez. Os documentos de entregas fechadas em `.scratch/` guardam o nome antigo: são registro do que aconteceu, não foram reescritos.
_Avoid_: Second Brain, second-brain, SB

**Whis da EC2**:
O agente pessoal anterior do usuário — chat por mensageiro, hospedado numa EC2 —, aposentado e desligado. Doador de ideias para o Whis atual, nunca dependência. O qualificador existe para o nome não ficar ambíguo nos documentos antigos.
_Avoid_: Whis (sem qualificador, quando se fala do antigo)
