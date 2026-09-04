# Smoke manual: a daily, do filtro ao checkbox

Roteiro curto de ponta a ponta para `second-brain daily`: conferir o filtro de
exclusão sem gastar nada, anotar um ponto seu, gerar a daily de verdade, ler no
Obsidian, falar, marcar o checkbox e ver o ponto sumir da daily seguinte. É a
validação do que fica fora da costura de teste automatizada: git, Linear e
Claude reais, na sua máquina, um minuto antes de você falar.

Tempo: ~10 minutos, espalhados por **dois dias** — o passo final só acontece na
daily seguinte.

Rode tudo de dentro do repositório, com o interpretador do ambiente virtual. Nos
exemplos abaixo, `python` significa `.venv\Scripts\python.exe`.

Pré-requisitos: `[git].raiz` preenchida e, se você usa o Linear, o
[smoke do Linear](smoke-linear.md) já passou. O Slack é opcional — a daily nasce
sem ele, **marcada** com o motivo (é o caso do passo 4).

## O que a daily cobre

**Da última daily até agora** — não um dia civil. Na segunda-feira ela cobre o
fim de semana inteiro. A âncora é o campo `ate` do frontmatter da daily
anterior; sem nenhuma anterior, as últimas 24 horas, e a nota diz que foi a
primeira. Nada é agendado: você roda na hora.

## Como o comando termina

O código de saída diz **se a nota nasceu, e inteira** — é o que distingue "a
daily nasceu sem o Slack" de "a daily não nasceu" quando você só olha o
terminal fechando:

| código | significado |
|---|---|
| `0` | nasceu inteira |
| `3` | nasceu **parcial**: uma fonte ou o Claude falhou, e a nota diz qual |
| `1` | **não nasceu**: todas as fontes falharam, nenhuma está configurada, ou não havia nada no período |
| `2` | erro de uso (argumento inválido) |

`python -m second_brain daily --help` mostra a mesma tabela. Toda execução
deixa rastro em `%APPDATA%\second-brain\bandeja.log`, ao lado do
`config.toml`; a última linha de cada execução diz como ela terminou.

## Passo 1 — Conferir o filtro, sem enviar nem escrever nada

Se você tem padrões em `[privacidade].excluir`, este é o passo que prova que
eles funcionam. Se não tem, ele só mostra o que entraria.

```
python -m second_brain daily --simular
```

`--simular` coleta, aplica o filtro e **imprime**: não chama o Claude e não
escreve nada no vault.

**Sucesso:** a linha `Cobre de ...` diz de quando a daily fala; abaixo, uma
linha por evento, com `[git]` e `[linear]` entre elas, e as reuniões da janela
no fim:

```
Daily — 2026-09-04
Cobre de quinta, 03/09 09:12, até agora.

Simulação — o Claude não foi chamado e nada foi escrito.
  03/09 14:02  [git] (second-brain) `62b55ce` Abre a proxima entrega
  03/09 15:12  [linear] (Plataforma) FN-124 Escrever o roteiro de smoke — criada
  reunião: reunioes/2026-09-03-1430-daily-do-time.md
O filtro de exclusão removeu 2 evento(s).
```

Confira, nesta ordem:

1. **Nenhuma linha contém um padrão do filtro.** O que casa com
   `[privacidade].excluir` não aparece — nem ao Claude nem ao vault iria. A
   linha `O filtro de exclusão removeu N evento(s)` diz quantos saíram; por
   decisão de privacidade, não diz quais.
2. **O período faz sentido.** Numa segunda, `Cobre de sexta, ...`. Se disser
   `as últimas 24 horas, porque esta é a primeira daily`, é a primeira mesmo.
3. **O código de saída é `0`** — ou `3` com uma linha
   `Fonte 'slack' não entrou: ...` se o Slack está desligado por falha, não
   por chave vazia.

**Falha — nada aparece e o código é `1`:** ou nenhuma fonte está ligada (a
mensagem diz qual chave preencher), ou todas falharam (a mensagem traz o
motivo de cada uma), ou não houve nada no período. Nos dois primeiros casos,
`bandeja.log` tem o mesmo motivo.

## Passo 2 — Anotar um ponto seu

```
python -m second_brain daily --anotar "quero puxar a conversa sobre a retenção de 180 dias"
```

**Sucesso:** o comando diz `Anotado em ...notas/daily.md` e sai **sem coletar
nada**. Abra o arquivo no Obsidian: o ponto está em `## Pontos` como
`- [ ] ...`, desmarcado. Se o arquivo já existia, tudo que estava nele
continua onde estava — o agente só acrescenta.

`## Dúvidas` e `## Off-topic` se editam direto no Obsidian, no mesmo arquivo.

## Passo 3 — Gerar a daily de verdade

Um minuto antes de falar:

```
python -m second_brain daily
```

Este passo **chama o Claude** (a conta da sua assinatura, ~US$ 0,42 num dia
cheio) e **escreve** `daily/YYYY-MM-DD.md`. O terminal imprime o roteiro
pronto para ler em voz alta.

**Sucesso:**

- as quatro batidas do Claude aparecem, na ordem de falar: `Entreguei`,
  `Sigo em`, `Preciso de`, `Dúvidas`;
- `Meus pontos` traz o que você anotou no passo 2;
- `Entreguei` e `Sigo em` são **o seu trabalho** — os commits são seus por
  construção, mas o Linear traz o time inteiro, e a movimentação dos outros
  não pode aparecer como se fosse sua;
- `Preciso de` só tem o que **espera outra pessoa** (review parado, PR sem
  merge). Nota para si mesmo não é daily. Lista vazia é resposta válida;
- o código de saída é `0`.

**Falha — o Claude não respondeu:** a daily nasce mesmo assim, com o aviso
`Esta daily não tem roteiro: ...` no topo e as listas cruas embaixo, e o
código é `3`. Rode de novo quando o Claude voltar: a nota do dia é
regenerada, mantendo o mesmo `desde`.

**Rodar de novo no mesmo dia** mantém o início da janela e estende o fim até
agora, reescrevendo a nota. Nada cai no vão entre a geração e a fala.

## Passo 4 — Ver a degradação graciosa acontecer

Só se o Slack **não** está configurado. Deixe assim: o objetivo é ver uma
fonte ausente não custar a daily. Se estiver, force uma falha sem rede
apontando `[git].raiz` para uma pasta que não existe e volte depois.

**Sucesso:** a nota nasce com `fontes_com_falha: [git]` no frontmatter, um
aviso `> Git não entrou nesta daily: Raiz de desenvolvimento não encontrada...`
abaixo do título, e o código de saída é `3`. O mesmo motivo, palavra por
palavra, está em `bandeja.log`.

## Passo 5 — Ler no Obsidian

Abra `daily/YYYY-MM-DD.md` no vault.

**Sucesso:**

- o frontmatter tem `desde`, `ate`, `fontes`, `fontes_com_falha`, `temas` e
  `reunioes`;
- a linha `Cobre de ...` bate com a do terminal;
- o roteiro está em cima e, da `## Reuniões` para baixo, as listas cruas por
  fonte, agrupadas por repositório ou projeto — é isso que faz da daily o
  registro durável do seu período;
- os wikilinks de `## Reuniões` abrem as notas de reunião;
- `notas/daily.md` continua exatamente como você deixou: o checkbox do seu
  ponto **segue desmarcado**. O agente nunca marca nada.

## Passo 6 — Falar, marcar, e conferir na daily seguinte

Depois de falar, abra `notas/daily.md` no Obsidian e marque o ponto:
`- [x] quero puxar a conversa sobre a retenção de 180 dias`.

No dia seguinte, um minuto antes da próxima daily:

```
python -m second_brain daily
```

**Sucesso, e este é o critério que fecha o smoke:**

- `Meus pontos` **não** traz mais o ponto marcado — e a seção some inteira se
  não sobrou nenhum desmarcado;
- a linha `Cobre de ...` começa exatamente onde a daily de ontem terminou (o
  `ate` do frontmatter dela): nada do fim do dia anterior ficou no vão;
- `daily/` tem uma nota por dia, e a de ontem não foi tocada.

**Falha:** se o ponto marcado reaparecer, confira se a linha ficou
`- [x]` com o `x` minúsculo dentro dos colchetes e a seção sob um título que
o agente reconhece (`## Pontos`, `## Dúvidas`, `## Off-topic`).

## Se a daily não nasceu e você não viu o terminal

Abra `%APPDATA%\second-brain\bandeja.log`. Procure a última linha
`Daily de YYYY-MM-DD:` — ela diz se a nota nasceu inteira, parcial ou não
nasceu, e as linhas acima dela dizem qual fonte falhou e por quê, com o mesmo
texto que iria para o aviso da nota.

## Custo

Uma chamada ao Claude por daily, pela assinatura — **US$ 0,4235 medidos** em
2026-09-04, num período de 262 eventos (52 commits em 29 repositórios + 210 do
Linear), 69 mil caracteres de pergunta e 38 segundos. `--simular` e `--anotar`
custam zero.

A linha de custo no log traz `total_cost_usd`, que é o número confiável; os
tokens de entrada que ela mostra vêm subnotificados (o volume real cai em
`cache_creation_input_tokens`, que a linha não lê).
