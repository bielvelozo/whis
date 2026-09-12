# Smoke manual: a daily, do filtro à nota viva

Roteiro curto de ponta a ponta para `whis daily`: conferir o filtro de
exclusão sem gastar nada, anotar um ponto seu, gerar a daily de verdade, ler a
nota viva no Obsidian, falar, e ver no dia seguinte o que continuou aberto
chegar **com as suas palavras**. É a validação do que fica fora da costura de
teste automatizada: git, Linear e Claude reais, na sua máquina, um minuto antes
de você falar.

Tempo: ~10 minutos, espalhados por **dois dias** — o passo final só acontece na
daily seguinte.

## A nota viva

O que você lê antes da reunião é **`daily/atual.md`**, uma nota só, que o Whis
mantém em vez de reescrever. Quatro seções, nesta ordem:

- `## O que eu fiz` e `## O que estou fazendo` são do Whis: ele **acrescenta** o
  que é novo e **move** um item de uma para a outra quando o sinal é forte (PR
  mergeada, issue em Done), copiando a sua linha byte a byte, com os sub-itens.
  Ele nunca reescreve nem apaga um item: corrija e apague à vontade, o que você
  escrever fica.
- `## Dúvidas` e `## Falar` são só suas. O Whis lê para não repetir, e nunca
  escreve nelas — a única exceção é `--anotar`, que acrescenta uma linha em
  *Falar* a seu pedido.

A cada daily nova, *O que eu fiz* é arquivado na nota do dia e recomeça vazio —
é o que as suas dailies à mão fazem: a de hoje não repete a de ontem.

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

`python -m whis daily --help` mostra a mesma tabela. Toda execução
deixa rastro em `%APPDATA%\whis\bandeja.log`, ao lado do
`config.toml`; a última linha de cada execução diz como ela terminou.

## Passo 1 — Conferir o filtro, sem enviar nem escrever nada

Se você tem padrões em `[privacidade].excluir`, este é o passo que prova que
eles funcionam. Se não tem, ele só mostra o que entraria.

```
python -m whis daily --simular
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
  03/09 14:02  [git] (whis) `62b55ce` Abre a proxima entrega
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

## Passo 1b — Calar os projetos pessoais

Só se você tem projeto pessoal na mesma pasta que o trabalho. Na primeira daily
real, **30 dos 52 commits eram de projeto pessoal** e o roteiro falou deles.

Em `%APPDATA%\whis\config.toml`:

```toml
[daily]
referencias_pessoais = ["whis", "renovo-hub"]
```

Lista-se o que é **pessoal**, não o que é do trabalho: assim um projeto novo do
Linear entra na daily sozinho, sem você precisar cadastrá-lo. Casa por pedaço do
nome, sem diferenciar maiúsculas, contra o repositório, o projeto ou o canal.

```
python -m whis daily --simular
```

**Sucesso:** as linhas dos seus projetos aparecem marcadas com `← só no vault`, e
no fim vem `N evento(s) ficam só no vault, fora do roteiro`. Elas **continuam na
lista**, e é isso que você quer: o roteiro cala, o vault guarda.

```
  03/09 22:20  [git] (renovo-hub) `591d652` Wayfinder: mapa do v1  ← só no vault
  03/09 23:35  [git] (flavianasser-monorepo) `7507ba4` Fecha a validacao
```

**Falha:** se marcar de menos, o pedaço do nome não bate — confira como a
referência aparece na própria linha. Se marcar demais, o padrão é curto demais e
está pegando repositório do trabalho junto.

## Passo 1c — Contar como o seu time funciona

O roteiro deduz do nome do estado quando você não conta. Foi assim que a primeira
daily real afirmou que cinco PRs esperavam "revisão humana", que não existe lá.

```toml
[daily]
contexto_do_time = "A aprovação do Zeno já libera a PR: não há review humano. O merge é meu."
```

Escreva em texto corrido, como explicaria a alguém que entrou no time hoje. Vale
para qualquer coisa que o roteiro não tem como saber: quem aprova, o que trava, o
que um estado significa aí.

**Sucesso:** na daily do passo 3, nenhum item novo diz que algo depende de outra
pessoa só porque o estado se chama "In Review". Se o merge é seu e ninguém está
esperando nada, nenhum item fala em bloqueio — e isso é uma daily melhor do que
um bloqueio inventado.

## Passo 2 — Anotar um ponto seu

```
python -m whis daily --anotar "quero puxar a conversa sobre a retenção de 180 dias"
```

**Sucesso:** o comando diz `Anotado em ...daily\atual.md` e sai **sem coletar
nada**. Abra a nota no Obsidian: a linha está no fim de `## Falar`, como
`- quero puxar ...`. Se a nota já existia, todo byte fora dessa linha continua
onde estava — o agente só acrescenta. Se não existia, ela nasce do modelo, com
um callout no topo explicando quem escreve onde.

`## Dúvidas` e o resto de `## Falar` se editam direto no Obsidian, na mesma
nota. É onde você sabe mais que o Claude: um bloqueio combinado numa conversa
não deixa rastro em commit nem em issue, então só existe na daily se você
escrever. Ele lê essas duas seções para não repetir, e nunca escreve nelas.

## Passo 3 — Gerar a daily de verdade

Um minuto antes de falar:

```
python -m whis daily
```

Este passo **chama o Claude** pela sua assinatura, mantém `daily/atual.md` e
escreve `daily/YYYY-MM-DD.md`. Não há cobrança por token; o que ele consome é
cota de uso do plano. O terminal imprime as quatro seções da nota viva como
ficaram, prontas para ler em voz alta, e os caminhos das duas notas.

**Sucesso:**

- as quatro seções aparecem, na ordem de falar: `O que eu fiz`, `O que estou
  fazendo`, `Dúvidas`, `Falar`;
- `Falar` traz o que você anotou no passo 2, **com as suas palavras**;
- os itens novos de `O que eu fiz` e `O que estou fazendo` são **o seu
  trabalho** — os commits são seus por construção, mas o Linear traz o time
  inteiro, e a movimentação dos outros não pode aparecer como se fosse sua;
- os itens novos seguem a régua das suas dailies à mão: agrupados por quem
  pediu ("Correções que o Ribeiro apontou" como item, achados como sub-itens),
  ancorados no sintoma, com o id da issue inline (`FN-1784`);
- o que a daily cobra vem **com link clicável** quando o material tinha um: a PR
  aparece como `[#1636](https://github.com/...)`, que você lê em voz alta como
  "#1636" e clica depois;
- **nada de assunto pessoal das suas DMs** aparece na nota. Trabalho e vida
  moram na mesma thread, e a blocklist não separa isso: quem separa é o prompt,
  com ordem de calar na dúvida. Se algo pessoal escapar, ponha a DM inteira em
  `[slack].conversas_excluidas` ou o assunto em `[privacidade].excluir`;
- o código de saída é `0`.

**Falha — o Claude não respondeu:** a nota do dia nasce mesmo assim, com o
aviso `A nota viva ficou como estava: ...` no topo e as listas cruas embaixo, e
o código é `3`. `daily/atual.md` não é tocada. Rode de novo quando o Claude
voltar: a nota do dia é regenerada, mantendo o mesmo `desde`, e a nota viva é
atualizada enfim.

**Rodar de novo no mesmo dia** mantém o início da janela e estende o fim até
agora, reescrevendo a nota do dia. A nota viva só ganha o que ainda não estava
nela: o que já está em *O que eu fiz* ou *O que estou fazendo* não volta. Nada
cai no vão entre a geração e a fala.

## Passo 4 — Ver a degradação graciosa acontecer

Só se o Slack **não** está configurado. Deixe assim: o objetivo é ver uma
fonte ausente não custar a daily. Se estiver, force uma falha sem rede
apontando `[git].raiz` para uma pasta que não existe e volte depois.

**Sucesso:** a nota nasce com `fontes_com_falha: [git]` no frontmatter, um
aviso `> Git não entrou nesta daily: Raiz de desenvolvimento não encontrada...`
abaixo do título, e o código de saída é `3`. O mesmo motivo, palavra por
palavra, está em `bandeja.log`.

## Passo 5 — Ler no Obsidian

Abra `daily/atual.md` no vault — é o que você lê em voz alta.

**Sucesso:**

- o frontmatter tem só `tipo: daily-atual` (sem `data`: a Daily notes do
  Obsidian transformaria o campo em link para uma nota que não existe);
- as quatro seções estão na ordem, e `Dúvidas` e `Falar` estão **exatamente**
  como você as deixou;
- o que o Whis acrescentou está no fim de cada lista, como `- item`; o que ele
  aninhou está indentado sob o item que você (ou ele) já tinha.

Abra também `daily/YYYY-MM-DD.md`, a nota do dia.

**Sucesso:**

- o frontmatter tem `desde`, `ate`, `fontes`, `fontes_com_falha`, `temas` e
  `reunioes`;
- a linha `Cobre de ...` bate com a do terminal;
- `## Mudanças na nota viva` diz o que esta execução acrescentou e moveu, com
  as linhas literais — ou `_(nada)_`;
- da `## Reuniões` para baixo, as listas cruas por fonte, agrupadas por
  repositório ou projeto — é isso que faz da nota do dia o registro durável do
  seu período e o lugar de conferir de onde veio cada item;
- os wikilinks de `## Reuniões` abrem as notas de reunião.

## Passo 6 — Falar, editar, e conferir na daily seguinte

Depois de falar, edite `daily/atual.md` à vontade no Obsidian: reescreva um
item do Whis com as suas palavras, apague o que não vale, tire da seção `Falar`
o que já falou. Deixe **um item aberto** em `O que estou fazendo` — com
sub-itens, se quiser, e um espaço no fim da linha para a prova ficar visível.

No dia seguinte, um minuto antes da próxima daily:

```
python -m whis daily
```

**Sucesso, e este é o critério que fecha o smoke:**

- o item que continuou aberto está em `O que estou fazendo` **byte a byte**
  igual ao que você deixou — mesmas palavras, mesmos sub-itens, mesmo espaço no
  fim;
- se algo que você tinha em aberto foi mergeado ou foi para Done, a linha
  **inteira** subiu para `O que eu fiz` como você a escreveu; se o Whis errou
  a mão, mova de volta — ele não repete o movimento;
- `O que eu fiz` de ontem não está mais em `atual.md`: está na nota de hoje,
  em `## O que eu fiz na daily anterior`, literal;
- `Dúvidas` e `Falar` continuam como você deixou;
- a linha `Cobre de ...` começa exatamente onde a daily de ontem terminou (o
  `ate` do frontmatter dela): nada do fim do dia anterior ficou no vão;
- `daily/` tem uma nota datada por dia, e a de ontem não foi tocada.

**Falha:** se um item seu apareceu com outras palavras, ou uma das seções suas
mudou sem você mexer, isto é o bug que a entrega existe para não ter — abra
`bandeja.log`, copie a resposta do Claude registrada ali e abra uma issue.

## Se a daily não nasceu e você não viu o terminal

Abra `%APPDATA%\whis\bandeja.log`. Procure a última linha
`Daily de YYYY-MM-DD:` — ela diz se a nota nasceu inteira, parcial ou não
nasceu, e as linhas acima dela dizem qual fonte falhou e por quê, com o mesmo
texto que iria para o aviso da nota.

## Quanto pesa na assinatura

Uma chamada ao Claude por daily. **Nada é cobrado por token**: o adaptador usa
a sua conta por OAuth e recusa qualquer API key paga que esteja no ambiente. O
que a daily consome é **cota de uso do plano**.

O valor em dólar no log é o que a mesma chamada custaria **na API paga**, não
uma fatura. Serve como medida relativa, e é o jeito de saber se o hábito ficou
pesado. Duas execuções reais medidas:

| quando | eventos | pergunta | equivalente |
|---|---|---|---|
| 2026-09-04, sem Slack | 262 | 69 mil caracteres | US$ 0,42 |
| 2026-09-04, com Slack | 603 | 143 mil caracteres | US$ 0,84 |

Ligar o Slack dobrou o peso. `--simular` e `--anotar` não chamam o Claude e
pesam zero.

Os tokens de entrada que a linha mostra vêm subnotificados: o volume real cai
em `cache_creation_input_tokens`, que ela não lê. O equivalente em dólar está
certo.
