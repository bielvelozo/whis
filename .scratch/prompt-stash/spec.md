---
status: ready-for-agent
---

# Prompt stash na palheta

Pedido do usuário em 2026-09-24, com o [Prompt Stash do Raycast](https://www.raycast.com/renzo/prompt-stash) como referência: guardar prompts e colá-los de volta sem sair do que está fazendo.

## Decisões (perguntadas e respondidas)

- **Onde moram:** `prompts/` no vault, um `.md` por prompt. O título é o nome do arquivo e o corpo é o prompt. `tags` e `favorito` ficam no frontmatter, como propriedades do Obsidian. Subpastas valem, e o que o usuário cria à mão no Obsidian aparece na lista.
- **Salvar:** do clipboard. `stash <título> #tag #tag *` na palheta (o `*` isolado marca como favorito). Sem título, o título é a primeira linha do prompt. Um título que já existe é recusado com o botão que abre a nota existente: nada é sobrescrito.
- **Usar:** o Enter copia o prompt e cola na janela onde o usuário estava antes de abrir a palheta.
- **Escopo:** o pacote completo do Raycast: buscar, filtrar por tag e por favorito, favoritar, editar, criar de dentro da lista e ver o prompt inteiro antes de usar.

## Zona de propriedade

`prompts/` é do usuário. O agente escreve lá só quando é mandado: um arquivo novo pelo `stash`/Ctrl+N, ou a linha `favorito:` do frontmatter pelo Ctrl+F. O corpo de um prompt que já existe nunca é reescrito.

## A lista na palheta

`prompts` (ou "Search prompts" na lista) troca a palheta para o modo lista, sem fechar a janela. `prompts <busca>` já abre filtrando.

- Digitar filtra: cada palavra precisa aparecer no título, no corpo ou nas tags. `#tag` filtra por tag (pelo começo dela) e `*` mostra só os favoritos.
- A ordem é favoritos primeiro, depois quem casa no título e depois o resto, cada grupo em ordem alfabética.
- Cada linha tem ★ para favorito e ❝ para os outros, o título, a primeira linha do corpo e as tags à direita. Embaixo da lista fica o painel de detalhe com o prompt selecionado.

| Tecla | Faz |
|---|---|
| ↵ / clique | copia e cola na janela anterior; a palheta some |
| Ctrl ↵ | só copia; a palheta some |
| Ctrl F | liga e desliga o favorito; a palheta fica |
| Ctrl E | abre a nota no Obsidian; a palheta some |
| Ctrl N | salva o clipboard com o texto do campo como título; a palheta fica |
| Esc, ou Backspace com o campo vazio | volta para os comandos |

A primeira versão não tem apagar: o usuário apaga pelo Obsidian (Ctrl E).

## Janela anterior e colar

A janela anterior é guardada quando a palheta abre (`GetForegroundWindow`). Colar é devolver o foco a essa janela e mandar Ctrl+V. Clipboard e teclado vão por `pywin32`, que já é dependência.

A suíte roda na máquina do usuário e **nunca** toca o clipboard nem o teclado de verdade: o `conftest` troca o módulo por um que estoura.
