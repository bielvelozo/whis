# 10 — Num canal barulhento, só o que me cita

**What to build:** `[slack].so_com_mencao` — uma lista de conversas em que só entra a mensagem
que cita o usuário (ou que ele mesmo escreveu). Pedido em 2026-09-04, depois de a primeira daily
com Slack encher as listas cruas de mensagens de bot sobre PRs de outras pessoas.

**Blocked by:** 05, 08 (fechadas)

**Status:** resolved

## O caso real

O `#dev-codereview` recebe uma mensagem do Zeno por rodada de review de **todo mundo**. Na
janela de 2026-09-04 isso deu **121 eventos**, quase todos no formato "@Fulano aprovado · rodada
6" sobre PRs alheias.

As duas réguas que já existiam não serviam:

- **`conversas_excluidas`** é tudo ou nada, e agiria antes da leitura. Bloquear o canal perderia
  junto os reviews que são dele — que é justamente o que ele quer falar na daily.
- **`privacidade.excluir`** exclui o que casa, e aqui é o contrário: ele quer **manter** o que
  casa.

## A régua nova, e por que ela é diferente da blocklist

| | `conversas_excluidas` | `so_com_mencao` |
|---|---|---|
| quando age | **antes** da leitura | **depois** da leitura |
| requisição | nenhuma sai | o canal é lido inteiro |
| para quê | privacidade | ruído |
| granularidade | a conversa | a mensagem |

Isso não é detalhe: quem quer privacidade tem que usar a blocklist, porque `so_com_mencao` **lê
tudo** — não há como saber quem uma mensagem cita sem lê-la. Há teste fixando que o canal
continua sendo consultado, para ninguém confundir as duas.

**Quem sou eu vem do `auth.test`**, que o coletor já fazia para descobrir o endereço do
workspace. Pedir o próprio nome na configuração seria mais um cadastro para o usuário errar, e
a resposta do token é a fonte da verdade sobre quem ele é naquele workspace.

**A mensagem que ele mesmo escreveu sobrevive**, embora ninguém se auto-cite: o que ele escreveu
num canal é trabalho dele, e descartá-la tiraria da daily justamente o que é mais dele. Na
prática isso sai de graça, porque `Evento.pessoas` já junta o autor e os citados.

## Critérios de aceite

- [x] `[slack].so_com_mencao` existe, com o campo achatado e a linha em `MODELO_DE_CONFIGURACAO`
- [x] Lista vazia = comportamento de hoje, e configuração antiga continua carregando
- [x] Numa conversa que casa, sobra só o que cita o usuário ou foi escrito por ele
- [x] Resposta de thread que o cita sobrevive
- [x] As outras conversas não são tocadas
- [x] O canal **continua sendo consultado** — teste explícito, para não virar blocklist na
      cabeça de quem lê
- [x] O log conta quantas mensagens foram descartadas, sem dizer quais
- [x] Casa por pedaço do nome, sem diferenciar maiúsculas, com `#` ignorado; padrão em branco
      não liga a régua
- [x] Suíte verde (**629**), sem editar teste existente

## Comments

**Camada 10 entregue e fechada.** `configuracao.py`, `fonte_slack.py`, `__main__.py` e 15 testes
em `tests/test_slack_so_com_mencao.py`, que reaproveitam o workspace de fixtures de
`test_fonte_slack`. Suíte em **629 verdes**, 7 desselecionados, nenhum teste existente editado.

**Provas executadas:**

- **Contra o canal real**, por `daily --simular` e sem gastar chamada: o `#dev-codereview` caiu
  de **121 para 37 eventos**, com o log registrando "84 mensagem(ns) fora de
  [slack].so_com_mencao descartadas por não citarem você".
- **Nenhum falso positivo**: dos 37 que sobraram, **37** têm o usuário em `Evento.pessoas` —
  citado ou como autor. Nenhum passou sem ele.
- **Nenhuma outra conversa mudou**: as DMs e o `#team-engenharia` seguem com a mesma contagem.
- Nas fixtures: a mensagem do bot de deploy some, a da Ana que o cita fica, a dele fica, e a
  resposta de thread que o cita fica.

**A configuração do usuário foi aplicada** (backup em `config.toml.antes-do-so-com-mencao`), com
`so_com_mencao = ["dev-codereview"]`.

**Não provado:** um canal em que o bot escreva o nome do usuário como **texto literal** em vez de
menção do Slack. A régua olha `Evento.pessoas`, que vem das menções resolvidas (`<@U...>`) e do
autor; um "@Gabriel Velozo" digitado como texto puro não conta como menção e a mensagem seria
descartada. Nas fixtures e no canal real isso não apareceu.
