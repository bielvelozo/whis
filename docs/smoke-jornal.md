# Smoke manual: o jornal do Whis

Roteiro da prova do jornal **na sua máquina**, no seu PowerShell 5.1. O
`%APPDATA%` que uma sessão de agente enxerga não é o seu: tarefa agendada,
toast e `config.toml` só contam quando **você** os vê. A entrega só fecha no
passo 7, com a edição das 08:20 lida no celular.

Rode tudo de dentro de `C:\Users\gabri\development\whis`. Nos exemplos,
`python` significa `.venv\Scripts\python.exe`. No PowerShell 5.1 não existe
`&&`: um comando por linha.

## Riscos declarados

- `CLAUDE_CODE_ARTIFACT=1` (liga a ferramenta Artifact no SDK) e o parâmetro
  `files` (as capas) **não são documentados**; o `files` depende de um flag
  remoto. Se sumirem, a publicação falha, a nota continua no vault e o toast
  diz que a página não saiu. Plano B para ler: a nota no Obsidian do PC.
- `unifiedWindows` (o consumo do plano) é interno: se sumir, o cabeçalho diz
  "sem leitura do plano".
- A API de placar da ESPN não é documentada e os termos da Disney proíbem
  acesso automatizado. Uso pessoal, 14 chamadas por dia; se quebrar, a seção
  diz "Placar indisponível hoje" e segue com as manchetes. A alternativa
  legítima (football-data.org) não traz artilheiro.

## Passo 1 — Sem Claude

```
python -m whis news --fakes
```

**Sucesso:** a lista de seções com contagens, "Simulação — nada publicado" e
o caminho de uma `jornal.html` numa pasta temporária. Abra essa página no
navegador: papel claro, seções numeradas, capas.
**Falha:** "O jornal não nasceu" = nenhum feed respondeu (sem rede).

## Passo 2 — Com o Claude, sem publicar

```
python -m whis news --simular
```

**Sucesso:** o mesmo, agora com títulos em português, resumos, *Aprender
hoje* e *Para aprender*, e a linha de custo (≈ US$ 0,60) e do plano.
**Falha:** "Faltou: seleção automática indisponível" = o editor não
respondeu; olhe `bandeja.log`. Credencial vencida: `claude auth login`.

## Passo 3 — A edição de verdade

```
python -m whis news
```

**Sucesso:** "Página: https://claude.ai/artifact/AYhYVZDhevQdWv4YaNuoge" (o
mesmo endereço do protótipo, que já está no seu favorito) e a nota
`noticias/AAAA-MM-DD.md` no Obsidian. Abra o link no celular.
**Falha:** "A página não saiu" — a nota existe; a mensagem diz por quê.

## Passo 4 — O toast

No fim do passo 3 chega o toast *O jornal de hoje está pronto*, com o botão
**Abrir jornal**. Clique.

**Sucesso:** o navegador abre a página do jornal.
**Falha:** botão que não faz nada — o Windows não abriu o `https://` pelo
toast; anote e me diga.

## Passo 5 — A tarefa das 08:20

```
python -m whis windows --news
Get-ScheduledTask -TaskName Whis-Noticias | Get-ScheduledTaskInfo
```

**Sucesso:** `NextRunTime` amanhã às 08:20. No Agendador, a tarefa tem
"Executar a tarefa o mais cedo possível após uma inicialização agendada ter
sido perdida" marcada. Para desligar sem apagar: `[noticias].ativa = false`
no painel (`settings` na palheta).

## Passo 6 — Uma fonte a mais ou a menos

Abra `noticias/fontes.md` no Obsidian. Apague uma linha `- Nome: URL` ou
acrescente uma; troque um nome em `## Nomes`. Rode o passo 2.

**Sucesso:** a fonte some/aparece (ou aparece em "Não responderam" se a URL
estiver errada). O Whis nunca reescreve esse arquivo.

## Passo 7 — A prova de verdade

Amanhã, **sem rodar nada**, abra o favorito no celular depois das 08:20 (ou
depois de ligar o PC, se ele estava desligado).

**Sucesso:** a data de hoje e a hora da edição no topo, as seis seções, o
placar (ou "sem jogo"), e o consumo do plano. Preencha:

### Quanto pesa na assinatura

| Data | Duração | ≈ US$ | Plano 5 h | Plano semana |
|---|---|---|---|---|
| | | | → | → |
| | | | → | → |
| | | | → | → |

Se uma edição passar de 15 min ou de US$ 2, olhe primeiro a formação (buscas)
e o tamanho dos candidatos no `bandeja.log`.

## Dev com IA — o X

A seção lê o X na sua conta, por um Chrome com um perfil só do Whis
(ADR 0003). Ela só aparece depois destes passos; antes deles o jornal sai
como sempre. O Chrome abre **com janela** (sem janela o X recusa).

### Passo X1 — A conta

A sua conta do X, **com o idioma em inglês** (Settings → Accessibility,
display and languages → Languages). Para a aba Seguindo trazer mais dev com
IA, há sugestões de quem seguir em `.scratch/jornal-dev-com-ia/spec.md`.

### Passo X2 — O login

```
python -m whis x-login
```

Abre um Chrome comum, sem automação, na tela de login do X. Entre na sua
conta (pelo Google funciona: o Google só recusa Chrome com automação) e,
quando a home aparecer, **feche a janela**. O Whis abre o leitor por alguns
segundos para conferir.

**Sucesso:** "Sessão do X salva".
**Falha:** "Login não concluído" — a home não abriu logada nesse perfil, ou
passaram 10 minutos com a janela aberta.

### Passo X3 — O bloco em `fontes.md`

Cole no **topo** de `noticias/fontes.md`, logo depois de `# Fontes do
jornal` (a ordem do arquivo é a ordem do jornal):

```
## Dev com IA (ia) · 4 a 6 itens
- X · Seguindo: x:seguindo
- X · Para você: x:para-voce
- X · Claude Code: x:busca "claude code" min_faves:100
- X · Outros harness: x:busca (codex OR cursor OR "gemini cli" OR opencode) (agent OR cli) min_faves:50
- X · Skills e hooks: x:busca (claude OR codex) (skills OR hooks OR subagents OR "slash commands" OR MCP) min_faves:50
- X · Contexto: x:busca ("context engineering" OR CLAUDE.md OR AGENTS.md OR "plan mode") min_faves:30
- X · Tokens e custo: x:busca ("prompt caching" OR "token usage" OR "context window" OR compact) (claude OR codex OR cursor) min_faves:10
- X · Fluxo de trabalho: x:busca ("agentic coding" OR "spec-driven" OR "parallel agents" OR worktrees) min_faves:30
```

### Passo X4 — Uma edição com a seção

```
python -m whis news --simular
```

**Sucesso:** na lista de seções, `Dev com IA` com 4 a 6 itens; na página da
pasta temporária, a seção 02 com a *Dica do dia* e os posts com "Ver no X".
**Falha:** "X indisponível hoje: …" — o motivo diz o que faltou (Chrome,
perfil em uso, página mudou). "O login do X venceu" — volte ao passo X2.

### Passo X5 — O login vencido

Feche o Chrome, apague a pasta `%LOCALAPPDATA%\whis\navegador-x` e rode o
passo X4 de novo.

**Sucesso:** a seção diz "O login do X venceu: rode python -m whis x-login" e
o resto do jornal sai. Refaça o passo X2 para voltar.


## A formação — figura, check e quiz

Desde 2026-10-06 (ADR 0005): toda aula tem uma figura (foto da fonte ou esquema), cada aula na
página tem o botão **Li esta aula**, a área só ganha aula nova depois que a anterior foi marcada,
e no sábado vem o **Quiz da semana** no lugar das aulas novas. As aulas viram notas em
`noticias/aulas/`, os quizzes em `noticias/quiz/`.

### Passo F1 — A edição simulada

```powershell
.\.venv\Scripts\python.exe -m whis news --simular
```

Abra o `jornal.html` que ele imprime. **Sucesso:** cada aula abre com uma foto ou um esquema, e o
botão "Li esta aula" aparece apagado com *"Para marcar, abra logado no claude.ai."* (fora do
claude.ai é assim mesmo). Nada novo em `noticias/aulas/`.

### Passo F2 — O check no celular (a prova que só você faz)

Na edição das 08:20, abra o favorito no celular, logado no claude.ai. Toque **Li esta aula** na
aula de negócios e em **uma** das de carro. Se o claude.ai pedir permissão para a página guardar
dados, aceite.

**Sucesso:** o botão vira **Lida ✓** e continua assim ao recarregar a página. **Falha:** o botão
continua apagado logado no claude.ai, ou some o ✓ ao recarregar — anote o que a página mostrou.

### Passo F3 — A edição seguinte

No dia seguinte, abra a página de novo.

**Sucesso:** *Aprender hoje* traz uma aula **nova** de negócios; em *Para aprender*, a aula de carro
que você não marcou volta com **"Pendente desde dd/mm"** e vem uma nova. No vault, as duas notas
que você marcou em `noticias/aulas/` estão com `status: lida`.

### Passo F4 — Marcar pelo Obsidian

Abra uma nota pendente em `noticias/aulas/` e troque `status: pendente` por `status: lida`.

**Sucesso:** na edição seguinte a área dela avança, como se você tivesse tocado no botão.

### Passo F5 — O sábado sem esperar o sábado

```powershell
.\.venv\Scripts\python.exe -m whis news --simular --sabado
```

**Sucesso:** a página abre com o **Quiz da semana**: uma pergunta por aula que você marcou desde o
último quiz, mais as que você errou antes. Tocar numa alternativa pinta de verde ou vermelho e
abre a explicação. Sem nada lido, uma linha diz que o quiz volta no próximo sábado.
`--sabado` sozinho (sem `--simular`) é recusado.

### Passo F6 — O sábado de verdade

No sábado, responda o quiz no celular e **erre uma de propósito**.

**Sucesso:** no domingo, `noticias/quiz/AAAA-MM-DD.md` mostra `Resultado: certa`, `errada` ou
`sem resposta` em cada pergunta; no sábado seguinte, a que você errou volta no quiz.

### Quanto pesa a mais

A leitura das marcações é um Haiku de uns 10 s e US$ 0,01 a 0,04 por manhã, e só roda quando há
aula esperando marca. O esquema da aula soma uns US$ 0,10 a 0,15 por edição. No sábado a formação
não roda; o quiz costuma custar menos.
