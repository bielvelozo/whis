# 08 — O que o roteiro sabe do mundo

**What to build:** Os três ajustes que a **primeira daily real** cobrou, todos da mesma família:
o roteiro precisa de fatos que os dados não carregam. Quais referências são do trabalho, como o
processo do time funciona, e o link junto do que a daily cobra.

O contrato desta camada está fixado na **[seção 10 do contrato](../contrato-fonte-passiva.md)**.
Leia-a inteira antes de começar: ela libera as duas chaves de configuração, diz onde cada
mecanismo age e lista o que não pode mudar.

**Blocked by:** 01, 04, 07 (todas fechadas)

**Status:** ready-for-agent

## O que aconteceu

A daily de 2026-09-04 foi gerada com git e Linear reais e lida pelo usuário. Três coisas
apareceram, nenhuma delas um bug de código:

1. **`Sigo em` falou de dois projetos pessoais** (`second-brain`, `renovo-hub`). Naquela janela,
   **30 dos 52 commits eram pessoais** contra 22 do trabalho. O Claude não errou: aquilo é
   trabalho do usuário, e nada nos dados diz o que é do emprego.
2. **`Preciso de` inventou uma revisão humana**: "as PRs #1636, #1639, #1650, #1657 e #1660 estão
   aguardando revisão humana e merge". No time dele **a aprovação do Zeno basta**, e **o merge é
   dele mesmo** — logo aquelas PRs **não deviam estar em `preciso_de`**, que é só para o que
   depende de outra pessoa. A inferência veio do nome do estado `In Review`, do Linear.
3. **O roteiro citou só o número da PR.** A URL completa **já chegava ao Claude** dentro do
   `detalhe` do comentário; o modelo a descartou. O usuário não decora número de PR.

## Critérios de aceite

- [ ] `[daily].referencias_do_trabalho` e `[daily].contexto_do_time` existem, validadas, com os
      campos achatados do contrato e a seção nova em `MODELO_DE_CONFIGURACAO`. Configuração
      antiga continua carregando
- [ ] **Lista vazia = tudo é trabalho**: sem configurar nada, a daily se comporta exatamente como
      hoje (é o que protege quem não vai mexer no arquivo)
- [ ] Com referências configuradas, evento de referência que **não** é do trabalho **não chega à
      porta da daily** — provado pelo que o `DailyFake` guardou, como o teste do filtro de
      exclusão já faz
- [ ] **As listas cruas da nota continuam com tudo**, inclusive o que foi calado no roteiro. Um
      teste tem que morder isso: é a decisão que faz a daily ser o registro durável
- [ ] `contexto_do_time` aparece no prompt como bloco rotulado; vazio, nenhum bloco aparece
- [ ] O prompt deixa de afirmar de quem é o merge, e passa a mandar **trazer o link em markdown
      com rótulo curto** (`[#1636](url)`) quando a URL estiver no material — nunca URL crua, que
      não se lê em voz alta
- [ ] **O diário não muda**: `gerar_diario` continua levando tudo ao Claude. Os testes de
      `test_diario.py` seguem verdes sem edição
- [ ] Suíte inteira verde (**557 hoje**, 7 desselecionados). O único teste existente que pode ser
      editado é o de prompt que cita a frase antiga do merge, em `tests/test_roteiro_da_daily.py`
- [ ] `docs/smoke-daily.md` ganha o passo de configurar as referências do trabalho e conferir,
      pelo `--simular`, que o pessoal continua nas listas cruas

## Notas para o executor

- **A ordem dos mecanismos não é gosto.** Silenciar o pessoal é **filtro**, porque o que se fala
  na frente do time não pode depender de o modelo obedecer; o processo do time é **texto no
  prompt**, porque errar ali dá uma frase imprecisa e não um vazamento. Não troque um pelo outro.
- **Não filtre as listas cruas.** A memória é do usuário; o time só ouve o roteiro.
- **Não mande `evento.url` ao Claude.** Reconsiderado e mantido deferido no contrato: ~260
  eventos por dia de URL para beneficiar duas linhas não se paga. Use o que já está no `detalhe`.
- A porta `PortaDaily` **não muda de assinatura**. O corte acontece na costura, e o adaptador
  continua sem conhecer o conceito de trabalho.
- Uma prova de rede opcional (`@pytest.mark.rede`) do prompt novo é bem-vinda, mas **gasta a
  assinatura do usuário** — não rode sem pedir.
- A prova final é humana, como na camada 06: a daily do dia seguinte, lida por ele, sem projeto
  pessoal na fala e com os links clicáveis no Obsidian.
