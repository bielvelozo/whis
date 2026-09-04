# 09 — A daily como página

**What to build:** A daily também como página HTML ao lado da nota, feita para ser lida em voz
alta um minuto antes de falar. Pedido pelo usuário em 2026-09-04, depois de ler a primeira daily
com Slack: "não queria que a daily fosse em um md, queria que gerasse uma html mais bonito".

**Blocked by:** 07, 08 (fechadas)

**Status:** resolved

## A decisão que o pedido não resolvia

O usuário pediu para a daily **deixar** de ser markdown. Não foi isso que entreguei, e a razão
precisa ficar registrada: a nota em `daily/YYYY-MM-DD.md` é o **registro durável do vault** —
foi a decisão que fez a daily carregar as listas cruas, e é o arquivo que a entrega seguinte
(recuperação de contexto) vai ler, além de ser o que o Obsidian indexa. Trocar markdown por HTML
mataria as três coisas para resolver um problema de leitura.

O que os dois usos querem é o mesmo conteúdo com **pesos invertidos**:

| | nota `.md` | página `.html` |
|---|---|---|
| para quê | memória, busca, o agente relê | falar em voz alta, agora |
| roteiro | no topo, em texto | ocupa a tela, corpo grande |
| listas cruas | abertas, é o conteúdo | recolhidas, é a conferência |
| quem abre | Obsidian, o próximo agente | o navegador, um minuto antes da daily |

Então: as duas nascem juntas, do mesmo dado, na mesma zona.

## Critérios de aceite

- [x] `daily/YYYY-MM-DD.html` nasce ao lado da nota, na mesma execução e na mesma zona
- [x] A extensão não confunde a âncora da janela — `ate_da_daily_anterior` varre `daily/*.md`
- [x] A página é **autossuficiente**: CSS embutido, nada buscado na rede (ela abre como arquivo
      local, às vezes sem internet, na hora de falar)
- [x] Roteiro no topo, na ordem de falar, em corpo grande; batida vazia diz "nada"; seção do
      usuário vazia não aparece
- [x] Listas cruas em `<details>` **recolhidos**, com a contagem no rótulo
- [x] O link do roteiro vira âncora clicável, com `target="_blank"` e `rel="noopener"`
- [x] Todo texto de fora é **escapado antes** de virar markup — uma mensagem de Slack não injeta
      HTML na página
- [x] O rodapé explica quantos eventos ficaram só na nota, senão a fala curta ao lado de uma
      lista longa parece defeito
- [x] Claro e escuro pelo `prefers-color-scheme`
- [x] Simulação não escreve página; todas as fontes falhando não deixa página órfã
- [x] Suíte verde (**614**), sem editar teste existente

## Comments

**Camada 09 entregue e fechada.** `pagina_da_daily.py` (novo), `vault.py`, `daily.py`,
`__main__.py` e 28 testes em `tests/test_pagina_da_daily.py`. Suíte em **614 verdes**, 7
desselecionados, nenhum teste existente editado.

**Uma refatoração, para a página não duplicar regra do contrato.** O agrupamento por referência
saiu de dentro do construtor de markdown e virou `vault.agrupar_por_referencia`, que devolve
dados; `_secao_da_fonte` passou a usá-la e a página usa a mesma. `_fontes_em_ordem` virou
pública pelo mesmo motivo. A suíte inteira continuou verde na refatoração, antes de a página
existir — foi o jeito de saber que ela não mudou comportamento.

**Provas executadas:**

- **Página real gerada com os dados de hoje**, sem pagar outra chamada: o roteiro foi relido da
  nota que a execução paga já tinha escrito e os eventos recoletados (git, Linear e Slack não
  custam). 243 KB, aberta no navegador e conferida.
- **O que o navegador mostrou**: título e linha de cobertura no alto; as seis batidas na ordem
  de falar; `Preciso de` dizendo "nada"; `Meus pontos` trazendo o ponto que o usuário tinha
  anotado; as listas cruas recolhidas com as contagens (Reuniões 2, Git 58, Linear 281, Slack
  338); rodapé com "677 evento(s) de Git, Linear, Slack. Outros 35 ficaram só na nota".
- **Injeção**: um evento com `<script>alert(1)</script>` no título e `<b>` no detalhe sai
  escapado; título com aspas não quebra o atributo `href`.
- **Autossuficiência**: teste varre a página atrás de `<link`, `<script`, `src=`, `@import` e
  `cdn` — nenhum aparece.
- **A âncora sobrevive**: com a página no disco, `ate_da_daily_anterior` continua achando a nota
  do dia anterior, e só um `.html` existe na pasta.

**Não provado:** impressão em papel (há `@media print`, nunca exercitado) e a aparência no modo
escuro, que só foi lida no claro.
