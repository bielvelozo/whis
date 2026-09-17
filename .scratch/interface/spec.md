# Spec: a interface do Whis — a palheta e a daily viva

Status: ready-for-agent

Origem: [mapa da interface](map.md), o [handoff da entrega 4](handoff.md) e o *grilling* do
[ticket 05](issues/05-o-dia-do-usuario.md). Escopo fechado com o usuário em 2026-09-11.
Glossário em `CONTEXT.md`; ADR 0001 (projeto separado, fino, 100% local) governa a arquitetura.
Os fatos que sustentam cada decisão estão em [research/](research/), um arquivo por ticket.

> **Cinco decisões anteriores foram revertidas neste escopo, e é de propósito.** (1) O handoff diz
> que o problema é a superfície; o usuário disse que era **principalmente o conteúdo**. (2) *"Toda
> resposta cita"*, escolha dele na entrega 3, sai: a fonte só aparece se ele pedir. (3) *"Sem
> personalidade"*, decidido na reunião de 04/09, passa a valer só para o roteiro que ele lê ao
> time. (4) **A DM do Slack — a entrega 3 inteira — vai dormir.** (5) O diário está **suspenso**.
> Os documentos das entregas fechadas guardam as decisões antigas; são registro do que aconteceu.

> **Revisão pós-prova, 2026-09-16.** O usuário provou a palheta na máquina dele e reprovou oito
> pontos, que **substituem** o que está abaixo onde conflitam: (1) a nota viva sem callout de
> explicação; (2) nenhuma janela de terminal para nenhum comando; (3) `anotar` vai para uma seção
> nova *Pontos*, e *Dúvidas* só a pedido — cinco seções; (4) sem comando `ajuda`; (5) comandos em
> **inglês** (`daily`, `note`, `doubt`, `ask`, `open`, `record`, `settings`) com a palavra do
> comando em cor de destaque; (6) a janela traz as ações *Open note*, *Generate daily* e
> *Start recording* clicáveis; (7) `ask` precisa funcionar sob `pythonw`; (8) visual estilo
> Raycast. Ticket [13](issues/13-acabamento-da-palheta.md).

## Problem Statement

O Whis funciona e **não está sendo usado**. Em 2026-09-11 não havia processo dele no ar: a bandeja
não sobe no logon desde o rename de 09/09 (o atalho chama um módulo que não existe mais), o
atendente nunca teve atalho instalado, e a tarefa de limpeza falha calada todo dia ao meio-dia.
Nada avisou. O usuário não percebeu porque tinha parado de usar antes disso.

Ele parou por dois motivos, e o segundo é o grande: o atrito do terminal, e **a daily não servir**.
Foram duas geradas na vida, e ele explicou o problema com precisão: *"muitas vezes da maneira que
ele descrevia o que eu fiz eu não lembrava exatamente o que era e não sabia explicar"*. O roteiro
era bom, específico, com número de issue e link de PR — e escrito em palavras que não eram as
dele. Um roteiro que ele não sabe explicar é pior que roteiro nenhum, porque ele o lê em voz alta
na frente do time.

As dailies que ele escreve à mão (`notas/Minha Daily.md`, `notas/Daily 2.md`) mostram o que falta:
ele **mantém uma lista viva** — itens sobem de *"O que estou fazendo"* para *"O que eu fiz"*, e o
que continua aberto é carregado **com as mesmas palavras** — enquanto o Whis gera uma narrativa
nova do zero a cada execução. Nas palavras dele: *"a parte do 'estou fazendo' que depois vira 'o
que foi feito' é o core da minha daily"*.

## Solution

Duas frentes, e a do conteúdo vem primeiro.

**A daily vira uma nota viva que o Whis mantém**, `daily/atual.md`, com quatro seções: duas que o
agente cuida (*O que eu fiz*, *O que estou fazendo*) e duas que são só do usuário (*Dúvidas*,
*Falar*). O agente acrescenta o que é novo, **move** um item de *fazendo* para *fiz* quando o sinal
é forte, e **nunca reescreve texto que já está lá**. Ele agrupa por quem pediu e ancora no sintoma,
que é como o usuário escreve. A nota nasce atualizada cinco minutos antes da reunião — 13:55 na
maioria dos dias, 10:25 na quarta e na sexta.

**O acionamento vira uma palheta de comandos**, aberta por atalho global de teclado no PC: um campo
de texto, o comando, e a janela some. Comando longo roda em segundo plano, o resultado vira nota no
vault, e um *toast* avisa quando fica pronto. A mesma janela abre o painel de configuração das 24
chaves. A bandeja continua sendo o gesto de gravar reunião e ganha o item que abre a janela.

E **um vigia bobo**, fora do Whis: uma tarefa agendada que só consulta o Agendador e dispara um
toast quando alguma peça não subiu. Não depende de rede, do Slack, nem de nada nosso estar vivo —
que é precisamente o motivo de ele existir.

## User Stories

1. Como quem entra na daily às 13:55, quero o roteiro pronto cinco minutos antes, para não digitar nada com a reunião começando.
2. Como quem vai falar em voz alta, quero ler **o texto que eu escrevi**, e não uma reescrita dele, para eu saber explicar o que estou lendo.
3. Como quem carrega trabalho de um dia para o outro, quero que o item que continua aberto continue **com as mesmas palavras**, para eu reconhecê-lo.
4. Como quem termina uma coisa, quero que ela suba sozinha de *estou fazendo* para *o que eu fiz* quando a PR for mergeada, para a lista se manter sem eu mexer.
5. Como quem organiza o trabalho por quem pediu, quero ver *"as correções que o Ribeiro apontou"* como uma unidade, porque é assim que está na minha cabeça.
6. Como dono das minhas dúvidas, quero uma seção que o agente **lê e nunca escreve**, porque é muito difícil ele entender em que eu tenho dúvida.
7. Como quem lembra de algo no meio do trabalho, quero anotar em dois segundos sem trocar de janela, para o ponto não se perder.
8. Como quem pergunta ao vault, quero um atalho de teclado, e não um terminal, para perguntar sem sair do que estou fazendo.
9. Como quem faz uma pergunta que demora um minuto, quero que a janela suma e me avise quando ficar pronto, para eu não ficar olhando para uma barra.
10. Como quem lê no Obsidian, quero que o aviso abra a nota certa com um clique.
11. Como quem precisa mexer em configuração, quero uma tela, porque eu não acho o arquivo quando preciso.
12. Como quem já perdeu três automações em silêncio, quero ser avisado quando o Whis parar de funcionar, para não descobrir na reunião.
13. Como quem grava reunião, quero que o gesto da bandeja continue exatamente igual, porque é o único que sempre funcionou.

## Implementation Decisions

### Camada zero — arrumar a casa

- **É pré-requisito, não higiene.** A entrega inteira depende de um processo residente que hoje não
  sobe. Renomear a pasta do repositório para `whis`, refazer `pip install -e .` (o editable install
  gravou o caminho absoluto antigo em `__editable__.whis-0.1.0.pth`), remover `Second Brain.lnk` e
  a tarefa `SecondBrain-Limpeza`, e recriar tudo com os nomes novos.
- **O passo de renomear a pasta é humano**: o Windows não renomeia o *cwd* de um processo vivo, e a
  sessão do agente precisa estar fechada.
- **Os atalhos precisam de AUMID.** Um app não empacotado só consegue disparar toast se tiver
  atalho no Menu Iniciar com AUMID (research 02). O atalho de hoje não tem; `automacao.py` passa a
  criá-lo com um.

### A daily viva

- **Terceira zona de propriedade, declarada no `CONTEXT.md`.** `daily/atual.md` não é zona do agente
  nem do usuário: o agente **acrescenta e move**, **nunca reescreve texto existente**, e **nunca
  encosta** em *Dúvidas* e *Falar*. Uma regra que não está no glossário é uma regra que o próximo
  agente quebra.
- **Uma nota só.** As `daily/YYYY-MM-DD.md` continuam nascendo ao lado com as listas cruas do dia,
  que é o registro de conferência; o que se lê antes da reunião é `daily/atual.md`.
- **Mover, não redigir.** O agente move um item de *fazendo* para *fiz* quando o sinal é forte — PR
  mergeada, issue em Done — transportando a linha **literalmente**. Se ele mover e re-descrever,
  volta-se ao problema original com um passo a mais.
- **A régua do texto novo** vem das dailies à mão dele: agrupar por quem pediu; ancorar no sintoma
  (*"Antes: esse toast aparecia quando você só reordenava as fotos"*), não no commit; e carregar o
  identificador da issue inline.
- **Quatro seções**, e `anotar X` passa a escrever em *Falar*. `notas/daily.md` é **aposentado** —
  nunca foi usado, e o `--anotar` apontava para ele.
- **Horário por dia da semana** em `[daily]`, não hora única. Não é Google Calendar: a tabela cobre
  a realidade descrita e não inventa um modo novo de falhar em silêncio.
- **Roteiro seco.** A personalidade não entra aqui — é texto que ele lê para outras pessoas.

### A palheta

- **Atalho global + janela, sem dependência nova.** Conferido na venv: `win32gui.RegisterHotKey`
  existe (`pywin32` já instalado) e `tkinter` 8.6 importa. O conflito de main loop com a bandeja
  tem saída no próprio `pystray`, cujo `_run_detached` é uma thread — Tk no principal, bandeja na
  secundária. Atenção registrada na research 05: o `_mainloop` do pystray consome as mensagens do
  thread, então a `WM_HOTKEY` precisa de janela ou thread próprio.
- **Plugin de launcher está fora.** O Flow Launcher aceita plugin em Python, mas abre um processo
  novo por consulta e o mata pelo cancellation token — uma resposta de 60 s não tem onde aparecer.
  PowerToys Run é só C#.
- **Contrato de comando: dispara e some.** A janela fecha, o comando roda em segundo plano, o
  resultado vira nota no vault e um toast avisa. Nenhum comando cabe numa janela que se fica
  olhando: a pergunta leva 60 s e a daily 40.
- **A palheta é extensível por construção** — os seis comandos futuros que o usuário listou (vagas,
  notícias, weekly, slides, reminders) encaixam como comando novo, não como tela nova. Nenhum deles
  é construído aqui.
- **A personalidade do Whis** (o de Dragon Ball: sereno, econômico, sem firula, mais solto só se o
  usuário brincar) vale nas respostas da palheta.
- **A fonte só aparece se pedida.** A resposta padrão não traz bloco de fontes; perguntar
  *"de onde?"* na mesma conversa traz, e o fio de 24 h já sustenta isso.
- **Encurtar a resposta é estrutural, não adjetivo.** `PROMPT_DA_BUSCA` já pede *"curta e direta"*
  duas vezes e saíram 3.933 tokens (research 03).

### A configuração

- **Painel com as 24 chaves, segredos inclusive.** Não fere a regra da entrega 3: o valor vai do
  teclado do usuário para o arquivo, sem passar por modelo nenhum.
- **Escritor de TOML nosso.** `tomllib` só lê, e `tomli_w`/`toml`/`tomlkit` não estão instalados
  (conferido). O painel regenera o arquivo a partir do `MODELO_DE_CONFIGURACAO`, que já carrega o
  comentário explicativo de cada chave, **com backup antes de cada escrita**. Preço aceito:
  comentário escrito à mão no arquivo se perde.

### Os avisos

- **Toast quando a daily nasce**, com botão que abre a nota. O botão usa
  `<action activationType="protocol">` com `obsidian://open?vault=245833c11ad43e6e&file=...` — o
  protocolo está registrado na máquina e não exige o Obsidian aberto.
- **`os.startfile` sai de `bandeja.abrir_no_windows`.** `.md` não tem programa associado nesta
  máquina, então *"Abrir a última nota"* nunca abriu o Obsidian. Vira URI.
- **O vigia é uma tarefa agendada separada** que consulta `Get-ScheduledTaskInfo` e dispara toast.
  Ele não pode depender de nada do Whis, porque o que ele vigia é o Whis morrendo.
- **As tarefas agendadas passam a ser criadas pelo módulo PowerShell `ScheduledTasks`**, não por
  `schtasks`: só ele liga `-StartWhenAvailable`, sem o qual uma daily agendada **não acontece** se
  o PC estiver desligado no horário (research 02). O módulo já vem no Windows.

### O que dorme

- **O Slack dorme, não morre.** Código (`atendente.py`, `dm_slack.py`) e tokens ficam; o atalho de
  logon não é instalado. Reavaliar em seis meses. Não se joga fora uma rodada de aprovação de admin
  antes de o substituto provar, e o único uso real que o Whis já teve foi ali.
- **O diário fica suspenso** — gerado uma vez em 03/09, nunca lido. Não agendar. Agendar o que
  ninguém lê é fabricar custo e mais um jeito de falhar calado.
- **`whis perguntar` continua** como comando de diagnóstico, que é o que ele já é.

## Testing Decisions

- **A regra "carrega sem reescrever" é o teste que mais importa.** Sondada nos dois sentidos: um
  item que continua aberto sai do arquivo **byte a byte igual** ao que entrou, e um item movido
  entre seções também. É o conserto do motivo pelo qual o usuário parou de usar.
- **As seções do usuário são fronteira**, testadas como a zona de propriedade já é: o agente lê
  *Dúvidas* e *Falar*, e nenhuma escrita dele as alcança — nem por caminho indireto.
- **O Windows é testado sem Windows**: criação de tarefa e disparo de toast saem por `executar`, o
  callable injetável que `automacao.py` já usa. Nenhum teste novo mexe no Agendador da máquina.
- **A palheta é testada sem janela**: o registro de comandos, o despacho e o contrato de resultado
  são costura pura; Tk entra por porta injetada, como `pystray` já entra na bandeja.
- **O escritor de TOML é provado por ida e volta**: escreve, relê com `tomllib` e compara a
  configuração carregada — mais um caso com valor que precisa de escape.
- Prior art: as três entregas anteriores. Costura única, fakes nas portas, zero mock de detalhe
  interno, nenhum teste existente editado.

## Out of Scope

- **Os seis comandos futuros** — vagas e freelas, notícias de IA, weekly/planning, slides, reminders.
  Encaixam em slot pronto, um por vez, em entregas seguintes. O usuário recusou explicitamente
  incluir um deles como prova nesta.
- **Pesquisa noturna** (comando que roda por horas) — ver o risco assumido abaixo.
- **Áudio e imagem na DM.** O scope `files:read`, que o usuário já pediu ao admin, fica sem uso
  enquanto o Slack dormir.
- **Google Calendar** como fonte da hora. A conta é Workspace, o que tornaria viável uma app
  *Internal* sem a armadilha do refresh token de 7 dias — mas a tabela por dia da semana cobre.
- **Plugin do Obsidian** e nota-painel adicional: um segundo artefato com o mesmo dado é o crime
  pelo qual a página HTML da daily foi revertida.
- **Backup/versionamento do vault** — segue no mapa como não especificado.

## Further Notes

- **Risco assumido pelo usuário (Q35):** o contrato de comando é desenhado para comandos de
  minutos. Quando a pesquisa noturna chegar — *"a ideia é ele passar a noite inteira pesquisando"* —
  ela atravessa suspensão, logoff e reboot, e este desenho provavelmente será reescrito. Ele
  preferiu não projetar para o que ainda não existe, que é defensável: foi projetando para o
  imaginado que a entrega 3 nasceu errada.
- **Risco assumido pelo usuário (Q11):** sem bloco de fontes por padrão, some a rede que o deixou
  pegar o agente inventando em 10/09. Mitigado por a fonte continuar existindo sob pedido.
- **O `%APPDATA%` de uma sessão de agente pode não ser o do usuário** (research 01, §5, com prova).
  Nada sobre o conteúdo de `config.toml`, nem sobre atalho na pasta de Inicialização, pode ser
  afirmado por leitura do agente. Quem confere é ele, no terminal dele — e o terminal dele é
  **PowerShell 5.1**, onde `&&` não existe e caminho é `C:\assim`.
- **Dois testes de uma tarde faltam antes de fechar o desenho da palheta** (research 05):
  `RegisterHotKey` sob `pythonw.exe`, e `pystray.run_detached` convivendo com o `mainloop` do Tk.
- **Armadilha viva no vault, achada no ticket 04**: a Daily notes do núcleo do Obsidian está ligada
  e transforma o campo `data:` de toda nota do Whis em link para uma daily note inexistente na
  raiz; clicar cria lixo. Vale resolver junto, e é barato.
- **Camadas sugeridas** para o handoff do executor, na ordem em que se resolvem: **0** arrumar a
  casa; **1** a nota viva e a regra de carregar sem reescrever; **2** o agendamento confiável e o
  vigia; **3** a palheta e o contrato de comando; **4** o painel de configuração e o escritor de
  TOML; **5** o toast com botão e a troca do `os.startfile`.
- O vocabulário segue o glossário: **Vault**, **Zona de propriedade** (que ganha um terceiro
  contrato), **Daily**, **Diário**, **Sob demanda**.
