# Smoke manual: fonte passiva do Linear

Roteiro curto para ligar o Linear no diário. É a validação do que fica fora da
costura de teste automatizada: a chave de verdade, contra a API de verdade.

Tempo: ~10 minutos, quase tudo no painel do Linear.

Rode tudo de dentro do repositório, com o interpretador do ambiente virtual. Nos
exemplos abaixo, `python` significa `.venv\Scripts\python.exe`.

## O que este coletor lê

Tudo que a chave enxergar, dentro da janela do dia: **issues que andaram**,
**comentários escritos** e **mudanças de estado** — do time inteiro, não só o
que é seu. Quem limita o alcance é a própria chave, no passo 1.

Ele **só lê**. Nada é criado, editado ou comentado no Linear pelo Whis.

## Passo 1 — Criar a Personal API Key read-only

No Linear, abra **Settings → Account → Security & Access** e crie uma nova
*Personal API key*.

1. Dê um nome que você reconheça depois: `whis (diário, read-only)`.
2. Em permissões, marque **apenas `Read`**. Deixe `Write`, `Admin`,
   `Create issues` e `Create comments` **desmarcados** — o diário nunca escreve
   no Linear, e uma chave que só lê não tem como estragar nada se vazar.
3. Se aparecer a opção de limitar por time, marque **só os times cujo trabalho
   você quer no diário**. É aqui que se decide o alcance: o coletor não filtra
   time nenhum, ele lê o que a chave alcança.
4. Expiração é opcional. Sem expiração, a chave vale até você revogá-la na
   mesma tela.

**Sucesso:** o Linear mostra a chave **uma única vez**, começando com
`lin_api_`. Copie agora; ela não aparece de novo.

**Falha:** se o botão de criar chave não existir, o admin do workspace bloqueou
a criação de chaves pessoais — peça a liberação antes de continuar.

## Passo 2 — Colar a chave na configuração local

Abra `%APPDATA%\whis\config.toml` e preencha a seção `[linear]`:

```toml
[linear]
api_key = "lin_api_...cole aqui a chave inteira..."
```

O arquivo está no `.gitignore` e é o único lugar onde a chave mora. Nunca a
coloque em variável de ambiente, em teste, em fixture nem em issue.

**Sucesso:** o arquivo continua carregando:

```
python -m whis diario --simular
```

**Falha:** se aparecer `Configuração inválida`, confira aspas e barras — use
barras normais (`/`) em qualquer caminho.

## Passo 3 — Ver o que seria coletado, sem escrever nada

```
python -m whis diario --simular
```

`--simular` coleta, aplica o filtro de exclusão e **imprime**: não chama o
Claude e não escreve nada no vault.

**Sucesso:** aparece a janela do dia e uma linha por evento, com as marcadas
`[linear]` entre elas:

```
Simulação do diário de 2026-09-03 — nada foi escrito.
Janela: 2026-09-03T04:00:00-03:00 → 2026-09-04T04:00:00-03:00
  11:20  [linear] (Frete v2) FN-123 Corrigir o cálculo de frete — movida de In Progress para Done
  12:02  [linear] (Frete v2) FN-123 Corrigir o cálculo de frete — comentário de Ana Prado
  15:12  [linear] (Plataforma) FN-124 Escrever o roteiro de smoke do Linear — criada
```

Confira, nesta ordem:

1. **O identificador e o título aparecem juntos** (`FN-123 Corrigir o cálculo de
   frete`) — é assim que a linha fica legível sozinha na nota.
2. **O horário bate com o seu relógio**, não com UTC. Uma issue que você mexeu
   às 11:20 tem que aparecer como `11:20`.
3. **A movimentação dos outros aparece**, não só a sua — é a decisão desta
   fonte.
4. **Um dia sem nada é normal:** se você não tocou no Linear naquele dia, não
   sai linha `[linear]` nenhuma, e isso não é falha.

**Falha — chave recusada:**

```
Fonte 'linear' não entrou: Linear respondeu HTTP 401: Chave do Linear inválida ou revogada...
```

Volte ao passo 1 e gere outra chave. O diário nasce mesmo assim, marcado — mas
sem o Linear.

**Falha — a chave não alcança o time:** a coleta funciona e volta vazia num dia
em que você sabe que houve movimento. Volte ao passo 1 e confira quais times
estão marcados na chave.

## Passo 4 — Gerar o diário de um dia movimentado

Escolha um dia em que você sabe que mexeu no Linear (pode ser uma data passada):

```
python -m whis diario 2026-09-03
```

Este passo **chama o Claude** para o resumo e **escreve no vault**.

**Sucesso:** o comando imprime o caminho da nota, e a nota tem a seção
`## Linear`, com um `### <projeto ou time>` por agrupamento e uma linha
`- HH:MM <identificador> <título> — <o que mudou>` por evento. Comentário entra
com o texto em blockquote na linha seguinte.

**Sucesso do critério de privacidade:** se você tem padrões em
`[privacidade].excluir`, rode o passo 3 antes e confira que nenhuma linha
excluída aparece — o que casa com o filtro não vai ao Claude nem ao vault.

## Passo 5 — Rodar o teste de rede de propósito

```
python -m pytest -m rede tests/test_fonte_linear.py
```

**Sucesso:** o teste passa lendo a janela de ontem contra a API de verdade.
Sem `[linear].api_key` preenchida ele **pula limpo**, e isso também é um
resultado válido — é o estado esperado numa máquina sem a chave.

## Se precisar revogar

**Settings → Account → Security & Access**, revogue a chave e apague o valor de
`[linear].api_key`. O diário volta a nascer só com as outras fontes, marcado
com o motivo. Nada no vault precisa ser mexido.

## Custo e limites

Zero: a API GraphQL do Linear é gratuita em qualquer plano. O teto é de 2.500
requisições por hora e 3.000.000 de pontos de complexidade por hora; um diário
gasta duas ou três requisições. Se o dia for grande o bastante para paginar, são
mais algumas — segue irrelevante perto do teto.
