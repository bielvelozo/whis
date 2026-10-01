# Smoke manual: as reuniões da Granola

Roteiro da prova do coletor de reuniões **na sua máquina**, no seu PowerShell 5.1. O `%APPDATA%` que uma sessão de agente enxerga não é o seu: o login guardado (`granola.json`), a tarefa agendada e o toast só contam quando **você** os vê. A entrega só fecha no passo 5, com a puxada da tarefa no dia seguinte.

Rode tudo de dentro de `C:\Users\gabri\development\whis`. Nos exemplos, `python` significa `.venv\Scripts\python.exe`. No PowerShell 5.1 não existe `&&`: um comando por linha.

## Riscos declarados

- O texto que o MCP da Granola devolve não é contrato documentado. Se o formato mudar, a puxada falha de forma visível ("formato inesperado", ou "declarou N e só M deu para ler"), com código 1 e toast. Não vira "nada novo" calado.
- Não está documentado quanto tempo o login guardado vale parado. Se vencer, a tarefa das 19:00 avisa "A Granola pediu login" e você entra de novo pela palheta (`meetings`).
- No plano grátis não há transcrição: `transcricoes/` continua vazia.

## Passo 1 — Sem Granola

```
python -m whis meetings --fakes
```

**Sucesso:** "Vault temporário: …" e `nova: reunioes/AAAA-MM-DD-1400-daily-do-time-exemplo.md`. O seu vault de verdade não ganha nada.
**Falha:** um traceback indica que falta dependência na venv. Rode `python -m pip install -e .` e repita.

## Passo 2 — O login e a primeira puxada, pela palheta

Abra a palheta (Ctrl+Space) e rode `meetings` (ou clique em **Pull meetings**).

**Sucesso:**
1. A Granola abre no navegador. Entre com a sua conta e autorize o acesso para **Whis**.
2. A aba mostra "Whis: login na Granola recebido. Pode fechar esta aba."
3. Segundos depois, chega o toast *Reuniões no vault*, que lista as reuniões novas e traz o botão que abre a mais recente.

**Falha:**
- *A Granola pediu login*, ou "Ninguém entrou na Granola em 5 minutos": rode `meetings` de novo e termine o login.
- "A porta 33418 … está ocupada": outro programa usa a porta. Feche o programa e tente de novo.
- O rastro fica em `%APPDATA%\whis\bandeja.log` (procure `whis.granola` e `whis.reunioes`).

**Prazo:** no plano grátis, a Granola só mostra os últimos 30 dias. As reuniões de 31/08 saem da janela em 01/10, e a de 01/09 em 02/10.

## Passo 3 — As notas

No Obsidian, abra `reunioes/`.

**Sucesso:**
- Uma nota por reunião, com o nome na hora local (`2026-09-01-1400-daily-engenharia.md`).
- O frontmatter traz `tipo: reuniao`, `participantes` (sem você), `granola` (o link) e `granola_id`, e **não** traz `data`.
- Embaixo do título vêm a data por extenso e o resumo da Granola, como ela mandou (pode estar em inglês).

Rode `meetings` de novo: o toast diz *Nada novo na Granola*, e nenhuma nota é duplicada nem reescrita.

Depois pergunte na palheta `ask o que ficou decidido na daily de 01/09?`. A resposta deve citar a nota de `reunioes/`.

## Passo 4 — A tarefa diária

```
python -m whis windows --meetings
```

**Sucesso:**
- O comando diz "Reuniões agendadas como 'Whis-Reunioes': todo dia às 19:00…". Para mudar a hora, edite `[granola].horario` no Settings da palheta e rode o comando de novo.
- Se o vigia estiver agendado, ele é reagendado com `Whis-Reunioes` na lista.

Confira no Agendador de Tarefas: `Whis-Reunioes` roda `pythonw.exe -m whis meetings --agendada --config "…\config.toml"`.

## Passo 5 — A prova de verdade

No dia seguinte, depois das 19:00 (ou quando o PC ligar, se ele estava desligado na hora), tenha feito pelo menos uma reunião na Granola durante o dia.

**Sucesso:** sem você abrir a palheta, chega o toast *Reuniões no vault* com a reunião do dia, e a nota está em `reunioes/`. Num dia sem reunião nova, a tarefa não mostra toast nenhum.
**Falha:** o toast *A Granola pediu login* quer dizer que o login guardado venceu: rode `meetings` na palheta. Qualquer outra falha aparece no `bandeja.log` e na ronda das 09:00 do vigia.
