# 01 — O tipo Slides publica headless? (sonda da camada 0)

Rodado em 2026-09-30/10-01 nesta máquina, pela sessão do agente, com `sonda.py` ao lado e o
`_AdaptadorDoJornal` (Haiku, CLI do npm, `CLAUDE_CODE_ARTIFACT=1`, `dontAsk`, ferramentas
`Artifact` e `Read`). Saídas cruas em `sonda-*.txt` (fora do git).

## Veredito: A

O Haiku headless cria um deck pelo `type_url` do Slides, preenche com vários arquivos de uma vez
(`root` + `file_path` + `files`) e republica de uma sessão nova, removendo um slide com `null` e
trocando o `createdOnFiles.at`, sem `force`. O plano B não é necessário.

Deck da sonda: `https://claude.ai/artifact/WiNjbNuZQJHgJ9vhHxUMBK`. Ele vira o endereço fixo na
Tarefa 5, que o republica com a nota de verdade e remove os slides da sonda.

## Passo a passo

| Passo | Ferramentas | Tempo | Custo (tabela da API) | Resultado |
|---|---|---|---|---|
| criar | `Artifact` | 12,6 s | US$ 0,069 | deck criado, versão 1 |
| preencher v1 (3 slides) | `Artifact` ×3, `Read` ×4 | 32,7 s | US$ 0,048 | versão 2, os três slides e o índice |
| preencher v2 (sessão nova, tira `irmao`, troca o `at`) | `Artifact` ×3, `Read` ×3 | 24,7 s | US$ 0,043 | versão 3; `irmao.html` sumiu da listagem |

Uma daily custa então cerca de **US$ 0,05 e 25–35 s**, mais US$ 0,07 e 13 s só na primeira vez,
quando o deck é criado.

## As frases exatas da ferramenta

- Criação: `Created a new Artifact at https://claude.ai/artifact/<id> (version …) from the
  Artifact type https://claude.ai/artifact/8jTsAFQMFDb2oA8MsPJ2eL (release …)`.
  **A URL do tipo vem depois da do deck no mesmo texto**: `jornal_claude.extrair_url` pega a
  última URL e devolveria a do tipo. O extrator da criação precisa casar a frase.
- Publicação num deck: `Updated the Artifact at https://claude.ai/artifact/<id> (Version N) with
  <file_path> (and any files listed); …`. **Não é `Published … at`** (essa é a frase do artifact
  comum do jornal). O padrão da daily aceita as duas.
- Listagem: `Published files of https://claude.ai/artifact/<id> (version …)`. Não pode contar como
  publicação; os dois padrões acima não casam com ela.

## O formato do slide (`artifact-type/reference/format.md`, release 1790810190-bbd5)

- **Lista aninhada não existe**: "`<ul>`/`<ol>` of plain `<li>` (one level)" e "Not in this
  subset: … nested lists". O sub-item é um `<ul>` irmão mais recuado.
- **`padding-left` não está no subconjunto**: só `padding: LEN ×1–4` (em `section`, `div`, texto
  e tabela). O recuo vai como `padding:0 0 0 Npx`. Com `padding-left` o recuo some em silêncio,
  porque o que está fora do subconjunto é descartado na leitura.
- **`<span>` só com cor**: "no sizes or fonts on spans". Código vira `<span style="color:…">`.
- Inline aceito: `<b>`, `<i>`, `<u>`, `<a href="https://…">`, `<span style="color:…">`.
- Caixas pinadas ficam "normalmente" dentro das margens de 128 px (`top+height ≤ 952`), com uma
  exceção já usada pelo SKILL: o rodapé de 24 px em `bottom:64px`. Uma faixa decorativa no topo
  vai em fluxo, num `div` de cabeçalho com o título, e não pinada em `top:88px`.
- `line-height: N`, `gap`, `display:flex`, `flex-direction`, `background`, `width` e `height`
  são aceitos onde o plano os usa.
- O índice do deck criado por nós leva `createdOnFiles` e `lists`; reescrever o índice inteiro
  a cada publicação, com `at` novo, foi aceito.

## O que não deu para ver

O painel do navegador desta sessão não está logado no claude.ai, então ninguém **olhou** o deck
renderizado. O formato acima é o do próprio tipo; o olhar dele fica para o deck de exemplo
(Tarefa 5).

## Ajustes que isto obrigou no plano

1. Tarefa 2: `padding:0 0 0 Npx` no lugar de `padding-left`. A faixa de acento entra em fluxo,
   num cabeçalho com o título (`gap:24px`), e `ALTURA_DA_LISTA` cai de 665 para 633.
2. Tarefa 3: o padrão de publicação aceita `Updated the Artifact at` e `Published … at`. A
   criação casa `Created a new Artifact at` e, como reserva, a primeira URL de artifact que não
   seja a do tipo.
