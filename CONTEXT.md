# Whis

Agente pessoal local que observa o trabalho do usuário no PC e recupera contexto, com um vault Obsidian como memória durável. Reunião não é gravada aqui: desde 2026-09-30 ela é gravada na **Granola**, e o coletor da Granola a traz para o vault (ADR 0002).

## Language

**Coletor**:
Componente que captura um tipo de sinal (as fontes passivas de trabalho, as reuniões da **Granola**) e o transforma em notas no vault.
_Avoid_: watcher, observador, collector

**Granola**:
O app de notas de reunião em que o usuário grava as reuniões, no plano gratuito. O coletor da Granola puxa pelo MCP oficial as reuniões dos últimos 30 dias que ainda não estão em `reunioes/` e escreve cada uma **uma vez só**: o resumo da Granola literal, e o `granola_id` no frontmatter, que é o que diz que ela já chegou. A transcrição não vem: o plano gratuito não dá. Roda pela palheta (`meetings`, que faz o login pelo navegador quando falta) e pela tarefa `Whis-Reunioes`, que nunca abre o navegador. Não é fonte passiva: não entra no diário pela janela do dia, só deixa notas que o diário, a daily e o `ask` já leem.
_Avoid_: gravação, gravador (o Whis não grava reunião)

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
O deck que o usuário apresenta na reunião diária do time, no Claude Slides, sempre no mesmo link. Nasce do que **ele** escreve na **Nota viva** (`daily/atual.md`): um slide por seção com texto em *O que eu fiz*, *O que estou fazendo*, *Dúvidas* e *Pontos*, com as linhas como ele as escreveu. Sai nos horários de `[daily].horarios` pela tarefa `Whis-Daily`, ou por `daily` na palheta; cada geração deixa `daily/YYYY-MM-DD.md`, a cópia do que foi para o deck, com o link no frontmatter (`deck:`) — é dali que a geração seguinte republica no mesmo endereço. Uma edição feita à mão no deck é sobrescrita na geração seguinte: o deck é a renderização da nota. `[daily].ativa = false` desliga a tarefa e esconde `daily` da palheta; `whis daily` no terminal ainda publica. Até 2026-09-30 a daily era um roteiro que o agente escrevia a partir de git, Linear e Slack — aposentado porque ele não usava. *O que terminei*, criada em 2026-09-30, saiu em 2026-10-01: dizia o mesmo que *O que eu fiz*. *Pontos* saiu no mesmo dia: o `note` escrevia ali, que nunca ia para o deck, e a daily saiu sem o que ele anotou para falar; desde então `note` escreve em *Falar*. Em 2026-10-07 ele inverteu: o `note` misturava em *Falar* o que era ponto, e *Pontos* voltou, com o `note` e no deck no lugar de *Falar*, que ficou só como texto dele na nota.
_Avoid_: standup, resumo diário, roteiro

**Nota viva**:
`daily/atual.md` — a nota da daily, escrita por ele no Obsidian, em cinco seções: *O que eu fiz*, *O que estou fazendo*, *Fazer*, *Dúvidas*, *Pontos*. É dele inteira, e quem a limpa depois da reunião é ele. O agente só escreve ali a pedido explícito — `did` (→ *O que eu fiz*), `doing` (→ *O que estou fazendo*), `note` (→ *Pontos*), `doubt` (→ *Dúvidas*) e `do` (→ *Fazer*, com a caixa `- [ ]`) acrescentam uma linha; `done` leva um item de *O que estou fazendo*, com o que está embaixo dele, para *O que eu fiz*, copiando os pais como cabeçalho sem repetir um que já esteja lá — e abre, vazio e no lugar dele, o título de uma seção do deck que falte. Em *Fazer* quem marca `[x]` é ele. A nota não carrega explicação nenhuma: ele sabe o que cada seção é.
_Avoid_: painel, dashboard, `daily/hoje.md`, `notas/daily.md`

**Zona de propriedade**:
Divisão do vault em três contratos: as pastas que o agente cria e pode regenerar (`reunioes/`, `transcricoes/`, `diario/`, `daily/`, `respostas/`, `noticias/`, `cacada/` — em `reunioes/` só o coletor da **Granola** escreve, e em `transcricoes/` ninguém escreve desde que a gravação saiu; o diário e o `ask` as leem); a zona do usuário (`notas/`), que o agente nunca toca; e a **Nota viva**, que é dele e onde o agente só acrescenta e move a pedido. `linkedin/` é do agente (a análise `linkedin/perfil.md`), com uma exceção: os **Rascunhos de post** em `linkedin/posts/` são dele depois de nascer — o agente só troca o frontmatter ao publicar. `cacada/` é do agente (os relatórios, os pacotes e `cacada/perfil.md`), com uma exceção: `cacada/criterios.md` é do usuário — o agente o cria uma vez, a partir do modelo, e nunca mais escreve nele. `prompts/` é do usuário como `notas/`, com uma exceção: o agente cria um arquivo novo ou troca a linha `favorito:` quando é mandado. `noticias/` é do agente (o **Jornal** e a **Trilha**), com uma exceção: `noticias/fontes.md` é do usuário — o agente o cria uma vez, a partir do modelo, e nunca mais escreve nele. `notas/daily.md` foi aposentado em 2026-09-12 — nunca foi usado; o que era dele vive na nota viva.

**Caçada**:
A corrida longa de vagas e freelas: `hunt` na palheta ou `whis hunt` no terminal, só quando ele chama, na véspera da virada semanal do plano do Claude, gastando o que sobrou da semana. Corre num processo próprio por horas, com o PC acordado: monta o perfil, lê as fontes de `cacada/criterios.md`, faz a triagem de cada **oportunidade** e prepara as **chances boas**. Pausa quando a janela de 5 h do plano bate e para quando o plano semanal chega ao teto (`[cacada].teto_semanal`, 100% por padrão; 70% fora da véspera) e 5 min antes da virada; chamada de novo, retoma de onde parou. Deixa o relatório `cacada/AAAA-MM-DD-HHMM.md` e um **pacote** por chance boa. A chance boa nunca sai sozinha; com `[cacada].enviar_sozinho` (entrega 2, desligado por padrão), as de **tentar a sorte** de vaga em Gupy e ATS saem pelo agente do navegador, pela regra de `politica.py`, e vão para o **Registro de ações**. Freela e LinkedIn, nunca. `whis hunt --freelas` é a caçada de **freelas rápidos**: só freela pequeno de preço fechado que paga logo e casa com ele; das fontes dele ficam só as de freela, entram as do modo (`freelas_rapidos.py`: mais buscas no Freelancer.com e a web vasculhada a fundo por plataformas, Shopify, bounties e posts de quem contrata), e o pedido do modo vai na frente de *O que eu procuro*. Uma caçada inacabada de outro modo não é retomada: começa outra. Nesse modo ela não para na virada da semana do plano: se o principal (achar, triar e resumir) não acabou, espera a semana virar e continua, uma vez só; se acabou antes, gasta o que sobra do plano até a virada: rodadas na web (no mínimo três, e enquanto trouxerem freela novo), o pacote completo (proposta e, no freela web, a amostra) de cada chance boa e, depois, das de tentar a sorte. Se mesmo assim o trabalho acabar com plano sobrando, `whis hunt --freelas` emenda uma caçada normal de vagas.
_Avoid_: busca de vagas, scraper, job search

**Oportunidade**:
Uma vaga de emprego ou um freela achado numa fonte da caçada, sempre com o link de onde veio. A triagem a classifica em **chance boa** (casa e ele tem chance: vai para ele mastigada, num pacote), **tentar a sorte** (vale tentar com pouca chance ou pouco ganho, como games e software de áudio: vai com uma mensagem curta pronta) ou **descartada** (com o motivo; golpe é sempre descartada). O que já apareceu numa caçada não volta.
_Avoid_: lead, job, anúncio

**Pacote**:
O que uma chance boa ganha, em `cacada/<corrida>/`. Por padrão é só o resumo curto — o que pedem, por que casa, o ponto fraco numa frase e o salário (faixa da vaga e pretensão) —, porque ele prefere escrever a proposta à mão. Com `[cacada].pacote_completo = true` volta o pacote inteiro, e as tentar a sorte ganham de novo a mensagem pronta: o que pedem (com o regime e a carga horária), por que casa, o que estica, alertas, preço ou pretensão (o número pronto para o campo, na moeda e unidade da vaga), prazo, a proposta pronta, as respostas de formulário, o plano, perguntas ao cliente, como enviar (com qual currículo anexar) e, no freela de página web, a **amostra** — uma página de conceito sem nome nem contato dele, com print para anexar e, se configurado, um link no Cloudflare Pages que sai do ar em 30 dias. Ele lê, ajusta e envia.
_Avoid_: dossiê, kit

**Candidaturas**:
`cacada/candidaturas.md`, regenerada no fim de cada **Caçada** (ou por `whis candidaturas`): as chances boas pelo `status:` do **Pacote** — `preparada`, `enviada`, `entrevista`, `proposta`, `recusada`, `fechado`, que só ele muda, no Obsidian —, as que o Whis enviou sozinho (do **Registro de ações**) e os e-mails do Gmail dedicado que parecem resposta da empresa.
_Avoid_: pipeline, CRM, funil

**Registro de ações**:
`%LOCALAPPDATA%\whis\cacada\acoes.jsonl`: tudo o que o Whis fez fora do PC em nome dele — conta criada, e-mail confirmado, perfil completado, candidatura enviada. Só acrescenta; cada ação nasce como intenção, gravada antes de agir, e ganha o desfecho depois. Intenção sem desfecho nunca é refeita sozinha, e nada é feito duas vezes (ADR 0004).
_Avoid_: log de ações, histórico

**Rascunho de post**:
Um post do LinkedIn escrito pelo Whis em `linkedin/posts/AAAA-MM-DD-<slug>.md`, com `status: rascunho`. O corpo da nota é o post, e ele edita no Obsidian. Só sai pelo gesto dele — Enter na lista `posts` da palheta, ou `whis linkedin-publicar` respondendo `s` —, pela API oficial do LinkedIn; publicado, ganha `status: publicado` e o link. No LinkedIn nada é automático: os colegas dele o seguem.
_Avoid_: post agendado, publicação automática

**Palheta**:
A janela de comandos do Whis, aberta por atalho global de teclado no PC (`ctrl+space`), no estilo Raycast: um campo de texto e uma lista de ações clicáveis, num painel acrílico translúcido; os comandos são em inglês (`daily`, `did`, `doing`, `done`, `news`, `meetings`, `hunt`, `accounts`, `linkedin`, `posts`, `note`, `doubt`, `do`, `ask`, `open`, `prompts`, `stash`, `settings`), o rótulo de uma ação digitado inteiro vale como o comando, Tab completa o comando da ação selecionada, e a janela some ao despachar. Todo comando **dispara e some** — menos `prompts`, `done` e `posts`, que trocam a lista de comandos pela dos **Prompts**, pela dos itens de *O que estou fazendo* e pela dos **Rascunhos de post**, sem fechar a janela — roda em segundo plano, o resultado vira nota no vault e um toast avisa quando fica pronto. Substitui a DM do Slack como o lugar de perguntar e anotar; a bandeja é a casa dela, e o clique no ícone também a abre. Uma resposta de `ask` nasce em `respostas/`, zona do agente. `hunt` não roda no thread da palheta: solta a **Caçada** num processo próprio, porque ela leva horas, e `hunt` de novo diz em que etapa ela está.
_Avoid_: launcher, painel com abas, chat

**Jornal**:
A edição diária de notícias do Whis: a nota `noticias/YYYY-MM-DD.md` (o dado) e a página publicada a partir dela como artifact privado da conta do usuário, sempre no mesmo endereço (a renderização, que ele lê no celular). Sai às 08:20 pela tarefa `Whis-Noticias`, ou por `news` na palheta; os feeds, os nomes que ele acompanha e o time vivem em `noticias/fontes.md`, que ele edita no Obsidian. Só existe no jornal o que veio de uma fonte com link; seção sem nada nas últimas 24 h diz isso em uma linha. Não é coletor (não observa o trabalho dele) nem fonte passiva. `[noticias].ativa = false` desliga a tarefa e esconde `news` da palheta. A página guarda o que ele marca nela (cada **Aula** lida, as respostas do **Quiz da semana**) no banco do artifact, e a edição seguinte copia isso para o vault antes de escrever (ADR 0005).
_Avoid_: report, newsletter, feed

**Aula**:
Um texto da formação do **Jornal**, de negócios (*Aprender hoje*) ou de carros (*Para aprender*), sempre com uma figura: a de carro, a foto da página da Wikipédia do assunto; a de negócios, um esquema que o Claude desenha. Vira a nota `noticias/aulas/<id>.md`, zona do agente, com `status: pendente` até ele marcar **Li esta aula** na página ou trocar para `status: lida` no Obsidian. Aula pendente volta na edição seguinte com "Pendente desde dd/mm", e a área dela não ganha aula nova até ser lida.
_Avoid_: lição, post, conteúdo

**Quiz da semana**:
A primeira seção do **Jornal** no sábado, no lugar das aulas novas: uma pergunta de múltipla escolha por **Aula** lida desde o último quiz, mais as que ele errou ou deixou sem resposta antes, até acertar. Fica em `noticias/quiz/AAAA-MM-DD.md`, com o resultado de cada pergunta escrito de volta.
_Avoid_: prova, teste, revisão

**Trilha**:
`noticias/trilha.md`, zona do agente: o que a formação do **Jornal** (*Aprender hoje* e *Para aprender*) já ensinou, uma linha por assunto por dia. A formação lê a trilha para progredir sem repetir e só acrescenta ao fim; nunca é reescrita. Uma área só ganha linha nova depois de a **Aula** anterior dela ser lida, e a formação roda uma vez por dia.
_Avoid_: histórico, currículo

**Prompt**:
Um texto guardado para colar num chat de IA: um `.md` em `prompts/` no vault. O título é o nome do arquivo, e `tags` e `favorito` são propriedades do Obsidian. `stash <título> #tag` guarda o que está no clipboard; `prompts` abre a lista na palheta, onde o Enter cola o prompt na janela em que o usuário estava. Referência: o Prompt Stash do Raycast.
_Avoid_: snippet, template

**Vigia**:
Uma tarefa agendada fora do Whis (`Whis-Vigia`, um script PowerShell autossuficiente) que consulta o Agendador e a lista de processos e dispara um toast quando uma peça não subiu — a daily ou o jornal não nasceu, a puxada das reuniões da Granola falhou, a bandeja não está no ar. Existe porque quem avisa que o Whis caiu não pode ser o Whis.
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
