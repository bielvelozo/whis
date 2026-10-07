# Smoke manual: a interface — a palheta, a daily viva e o vigia

Roteiro da prova da entrega 4 **na sua máquina**, no seu PowerShell 5.1. É a
parte que nenhum agente consegue fazer: o `%APPDATA%` que uma sessão de agente
enxerga não é o seu, então atalho, tarefa agendada, toast e `config.toml` só
contam quando **você** os vê. A entrega só está fechada depois do passo 9.

Tempo: ~20 minutos hoje, mais a daily seguinte.

Rode tudo de dentro de `C:\Users\gabri\development\whis`. Nos exemplos,
`python` significa `.venv\Scripts\python.exe`. No PowerShell 5.1 não existe
`&&`: um comando por linha, ou `;` entre eles.

## Passo 0 — Conferir a base

```
python -m pytest
python -m whis perguntar --fakes --sem-fio "teste"
```

**Sucesso:** a suíte verde e o `perguntar --fakes` imprimindo a resposta de
exemplo. Se `import whis` falhar, refaça o editable install:
`.venv\Scripts\python.exe -m pip install -e .`

## Passo 1 — Tirar o nome antigo da máquina

```
python -m whis windows --remover-legado
```

**Sucesso:** duas linhas dizendo que `Second Brain.lnk` saiu da Inicialização e
que a tarefa `SecondBrain-Limpeza` saiu do Agendador. Se alguma diz "Não
havia", tudo bem — ela já não existia. Confira:

```
Get-ScheduledTask | Where-Object { $_.TaskName -like "*Second*" }
Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
```

Nada com "Second" deve sobrar.

## Passo 2 — As chaves novas no config.toml

A entrega acrescentou chaves que o seu arquivo ainda não tem. Sem
`[daily].horarios` o passo 3 recusa agendar a daily.

O jeito da entrega é pelo painel: suba a bandeja num terminal, abra a palheta
pelo atalho e digite `settings`:

```
python -m whis bandeja
```

Aperte **Ctrl+Space**, digite `settings`, Enter (ou clique em **Settings** na
lista). No painel:

- **Horários da daily**: segunda, terça e quinta `13:55`; quarta e sexta
  `10:25`. Dia vazio = sem daily.
- **Obsidian › vault**: `245833c11ad43e6e` (o ID deste vault; ou o nome da
  pasta, `whis-vault`).
- **Daily › referências pessoais**: tire `second-brain`; ponha `whis` se quiser
  que este projeto fique fora do roteiro do time.
- **Privacidade › pastas privadas** (pendência antiga da entrega 3): se quiser
  uma pasta que o agente nunca abre, é aqui — por exemplo `notas/pessoal`.

Salve. O painel faz backup (`config.toml.bak-…`) antes de escrever e recusa
salvar um arquivo inválido. Depois, feche a bandeja (menu › Sair) e volte ao
terminal.

Se preferir editar à mão, as chaves são estas (barras normais nos caminhos):

```toml
[daily]
horarios = { segunda = "13:55", terca = "13:55", quarta = "10:25", quinta = "13:55", sexta = "10:25" }

[obsidian]
vault = "245833c11ad43e6e"

[palheta]
atalho = "ctrl+space"
```

## Passo 3 — Instalar tudo com os nomes novos

```
python -m whis windows --daily --limpeza
```

**Sucesso:** o comando conta o que criou — o atalho de Inicialização, o atalho
do Menu Iniciar com a AUMID `Whis.Agente` (é ele que autoriza o toast), a
tarefa `Whis-Limpeza` (12:00, diária), a tarefa `Whis-Daily` com um gatilho por
dia da tabela, e a tarefa `Whis-Vigia` (dez minutos depois de cada daily e uma
ronda às 09:00). Confira no Agendador:

```
Get-ScheduledTask -TaskName "Whis-*" | Select-Object TaskName, State
(Get-ScheduledTask -TaskName "Whis-Daily").Settings | Select-Object StartWhenAvailable, WakeToRun
(Get-ScheduledTask -TaskName "Whis-Daily").Triggers | Select-Object DaysOfWeek, StartBoundary
```

`StartWhenAvailable` precisa ser `True`: é o que faz a daily nascer mesmo se o
PC estava desligado às 13:55. E no Menu Iniciar deve existir um **Whis**
(digite "Whis" na busca do Windows).

**Falha — `a tarefa 'Whis-Daily' precisa de pelo menos um gatilho`:** a tabela
`horarios` está vazia; volte ao passo 2.

## Passo 4 — A bandeja sobe sozinha

Faça logoff e logon (ou reinicie). **Sucesso:** o ícone cinza do Whis na
bandeja, sem terminal aberto. Se não subir, abra
`%APPDATA%\whis\bandeja.log` — e rode o vigia à mão (passo 7): ele diz "A
bandeja não está no ar".

## Passo 5 — A palheta

Com a bandeja no ar, aperte **Ctrl+Space** (se o seu `config.toml` ainda diz
`ctrl+alt+w`, troque em `settings` e reinicie a bandeja). Um painel quase
preto, de cantos arredondados e borda fina, aparece no alto da tela, no
desenho do Raycast, com o que está atrás dele aparecendo desfocado por
trás: um campo grande com "Type a command…", embaixo a lista de
ações — **Open note** e **Generate daily** primeiro, depois Did, Doing, Mark done, Generate news,
Pull meetings, Search prompts, Stash prompt, Ask, Note, Doubt, To-do, Settings — cada uma com o nome do comando em roxo à direita,
e um rodapé com **Run ↵** e **Complete Tab**. ↑/↓ escolhem uma linha, Enter
executa a escolhida (com o campo vazio), clicar também executa; digitar filtra
a lista pelo comando **e** pelo rótulo
(`generate` acha *Generate daily*); a palavra do comando fica em roxo quando é
um comando, e o rótulo inteiro fica em roxo quando é ele que casa — Enter em
`generate daily` roda `daily`. **Tab** completa o campo com o comando da ação
selecionada (`ask` ganha o espaço para a pergunta); Tab de novo, com o campo já
completo, passa à próxima ação da lista. Esc, ou clicar fora, fecha sem fazer
nada. **Nenhuma janela de terminal deve piscar em nenhum comando** — se
piscar, é falha.

Teste, um por vez:

| digite | o que deve acontecer |
|---|---|
| `doing testando o fazendo` | toast "Anotado em O que estou fazendo"; a linha entra no fim de *O que estou fazendo* |
| `did testando o fiz` | toast "Anotado em O que eu fiz"; a linha entra no fim de *O que eu fiz* |
| `done` (ou **Mark done**) | a janela fica e mostra os itens de *O que estou fazendo*, um sub-item com `em: <pai>`; digitar filtra (sem acento nem maiúscula). Enter leva o selecionado, com o que está embaixo dele, para o fim de *O que eu fiz* (confira no Obsidian); o rodapé diz *Moved: …* e a lista segue aberta sem ele. Mova um sub-item e veja o pai copiado em *O que eu fiz*; depois mova o pai e veja que ele não se repete. **Um clique numa linha também move, sem desfazer.** Esc volta aos comandos |
| `note testando a palheta` | toast "Anotado em Pontos"; `daily/atual.md` ganha `- testando a palheta` no fim de *Pontos*, que vai para o deck da daily; *Falar* não muda |
| `doubt o pix expira sozinho?` | toast "Anotado em Dúvidas"; a linha entra em *Dúvidas* |
| `do responder o ribeiro` | toast "Anotado em Fazer"; `daily/atual.md` ganha `- [ ] responder o ribeiro` no fim de *Fazer* (a seção nasce entre *O que estou fazendo* e *Dúvidas*). Marque o `[x]` no Obsidian: ninguém mexe nessa linha depois |
| `open` (ou clique em **Open note**) | o Obsidian abre `daily/atual.md`. Teste **com o Obsidian fechado** também: o Windows deve lançá-lo e cair na nota |
| `ask qual foi a decisão sobre retenção?` | a janela some; ~60 s depois um toast com o começo da resposta e o botão **Abrir no Obsidian**, que abre a nota nova em `respostas/`. Custa uma pergunta na sua conta (≈ US$ 0,56 equivalente) |
| `daily` (ou **Generate daily**) | ~40 s depois, toast "A daily está pronta" com o botão; `daily/atual.md` atualizada |
| `settings` | o painel de configuração abre |
| Enter com o campo vazio e nada selecionado, `vagas` | a janela só some; `vagas` dá o toast "Não entendi" com a lista dos comandos |

O clique esquerdo no ícone da bandeja e o item **Abrir a palheta** do menu fazem o mesmo que o atalho. Se o
atalho não responder, veja no `bandeja.log` se o registro do hotkey foi
recusado (outro programa já usa a combinação): troque `[palheta].atalho` no
painel e reinicie a bandeja.

## Passo 6 — O toast com botão

Rode a daily pelo terminal, para ver o toast nascer de um processo sem janela:

```
python -m whis daily
```

**Sucesso:** o toast "A daily está pronta" com **Abrir no Obsidian**; o clique
abre `daily/atual.md`. Se o toast não aparecer, o atalho do Menu Iniciar com a
AUMID não existe (passo 3) — é a única razão comum.

## Passo 7 — O vigia

Rode à mão para ver o que ele enxerga agora:

```
powershell -NoProfile -ExecutionPolicy Bypass -File src\whis\vigia.ps1 -Aumid Whis.Agente -Tarefas "Whis-Daily,Whis-Limpeza"
```

**Sucesso:** `Tudo de pé: ...`. Se ele imprimir problemas, ele também dispara um
toast "O Whis precisa de você" — é exatamente o que vai acontecer sozinho dez
minutos depois de uma daily que não nasceu, ou às 09:00 se a bandeja não
subiu. `Whis-Daily` ainda sem nenhuma execução não conta como falha.

## Passo 8 — A armadilha da Daily notes do Obsidian

O plugin de núcleo **Daily notes** está ligado no seu vault e transforma o campo
`data:` de toda nota do Whis num link para uma nota que não existe na raiz;
clicar cria lixo. Em *Configurações › Plugins principais*, desligue **Daily
notes** — ou, se usa o plugin, aponte a pasta dele para `daily` e o formato
para `YYYY-MM-DD`, que é o nome das notas datadas do Whis.

## Passo 9 — A prova de verdade: a daily seguinte

Desde 2026-09-30 a daily é um deck montado do que você escreve em
`daily/atual.md`; a prova dela está em `docs/smoke-daily.md`. Se algo não
bater, o rastro está em `%APPDATA%\whis\bandeja.log`.

## O que dorme e o que ficou de fora

- **O Slack dorme.** Nada do atendente é instalado; `Whis Atendente.lnk` nunca
  existiu na sua Inicialização, então não há o que remover. Os scopes concedidos
  à app continuam lá: avisar ou revogar é decisão sua.
- **O diário está suspenso.** Nada o agenda.
- Os seis comandos futuros (vagas, notícias, weekly, slides, reminders) entram
  um por vez, como comando novo da palheta, em entregas seguintes.

## Para desfazer

```
python -m whis windows --daily --limpeza --remover
```

Tira os atalhos e as três tarefas. O vault e o `config.toml` ficam.
