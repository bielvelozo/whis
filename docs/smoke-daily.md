# Prova da daily em slides

`python` significa `.venv\Scripts\python.exe`, rodado da pasta do repositório. No PowerShell 5.1
não existe `&&`: um comando por linha.

## Passo 1 — Escrever a nota

Abra a palheta (`ctrl+space`), rode `open` e escreva em `daily/atual.md`, no Obsidian:

- em *O que eu fiz* e *O que estou fazendo*, uma linha por coisa, com sub-itens por tab
  quando quiser;
- em *Dúvidas* e *Pontos*, o que for levar à reunião.

Sem abrir o Obsidian, a palheta faz o mesmo: `doing <texto>`, `did <texto>`, `doubt <texto>` e
`note <texto>` (este em *Pontos*) acrescentam uma linha, e `done` leva um item de *O que estou
fazendo* para *O que eu fiz*.

Se a nota ainda não tem um desses títulos, o Whis o abre vazio na primeira geração. O texto
que você escreveu ele nunca mexe, a não ser quando você pede, pela palheta.

## Passo 2 — Conferir sem publicar

```powershell
python -m whis daily --simular
```

O terminal mostra os slides que sairiam, um bloco por seção, com o seu texto. Nada é publicado
nem gravado.

## Passo 3 — Publicar

```powershell
python -m whis daily
```

Em cerca de um minuto chega o toast **A daily está pronta**, com o botão **Abrir slides**. O
deck abre no link de sempre: um slide por seção com texto, na ordem da nota, com a data e a
página no rodapé. *Fazer* e *Falar* não aparecem.

## Passo 4 — A cópia

Abra `daily/` no Obsidian. A nota de hoje (`AAAA-MM-DD.md`) tem `deck:` no frontmatter, o link
**Abrir os slides** e as seções que foram para o deck, com as suas linhas.

## Passo 5 — Gerar de novo

Mude uma linha, apague tudo de *Dúvidas* e rode `daily` na palheta. O link é o mesmo, a linha
mudou, e o slide de *Dúvidas* sumiu.

## Passo 6 — A tarefa agendada

```powershell
Start-ScheduledTask -TaskName Whis-Daily
```

Espere o toast e depois:

```powershell
(Get-ScheduledTaskInfo -TaskName Whis-Daily).LastTaskResult
```

O esperado é `0`. Com `3` os slides não saíram: o toast diz o motivo e o rastro fica em
`%APPDATA%\whis\bandeja.log`.

## Passo 7 — A prova de verdade

Na próxima daily do time, apresente pelo deck que a tarefa publicou alguns minutos antes. Conte
no chat o que faltou ou sobrou: é a confirmação que fecha a entrega.
