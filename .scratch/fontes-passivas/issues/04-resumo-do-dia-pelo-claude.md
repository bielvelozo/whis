# 04 — Resumo do dia pelo Claude

**What to build:** `resumo_dia_claude.py`: o adaptador real de `PortaResumoDoDia`, falando
com o Claude da conta do usuário pelo Claude Agent SDK (OAuth), como já faz
`resumo_claude.py` para as reuniões. Recebe os eventos do dia e as reuniões, devolve
narrativa, destaques, pendências e temas em português.

**Blocked by:** 01

**Status:** resolved

- [x] `ResumoDoDiaClaude` implementa `PortaResumoDoDia`, com a mesma postura do adaptador de reunião: **recusa** cair para `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`, um turno só, sem ferramenta nenhuma, sem acesso a disco
- [x] Prompt que produz um dia legível: narrativa curta ligando as fontes (não uma lista reescrita), destaques do que importou, pendências abertas e temas para o frontmatter; preserva termos técnicos em inglês; nunca inventa o que não está nos eventos
- [x] Resposta em JSON, interpretada para `ResumoDoDia`; resposta que não vira `ResumoDoDia` levanta `ErroDeResumoDoDia` com trecho de diagnóstico
- [x] Sem credencial, sem CLI, timeout ou dia grande demais também viram `ErroDeResumoDoDia` — o diário nasce sem narrativa e marcado, que é o comportamento que a camada 01 já implementa
- [x] Limite de tamanho declarado, no espírito do `LIMITE_DE_CARACTERES` do adaptador de reunião, e um caminho honesto quando o dia estoura: recusa clara, nunca uma chamada que vai falhar
- [x] `montar_resumo_do_dia` da CLI passa a devolver o adaptador real quando não for `--fakes`
- [x] Testes sem rede: montagem da pergunta, interpretação de resposta boa, de resposta suja (cercas de código, texto em volta) e de resposta inválida; recusa quando há variável de API paga no ambiente
- [x] Um teste `@pytest.mark.rede` que só roda de propósito — ele gasta a assinatura do usuário

## Notas para o executor

- Espelhe `resumo_claude.py`: ele já resolveu OAuth, opções do SDK, timeout, parse tolerante
  e recusa de API paga. Reaproveite o que der; não copie o que não servir — a entrada aqui é
  uma lista de eventos, não uma transcrição.
- O [DEFERRED](../../tracer-bullet/DEFERRED.md) registra que o custo do resumo é descartado
  hoje (`ResultMessage.total_cost_usd`). Com o diário rodando todo dia isso passa a importar:
  **registre o custo no log** desta camada. É barato e fecha um item deferido.
- Dia sem eventos não chega aqui — a camada 01 corta antes.

## Comments

**Camada 04 entregue** — `resumo_dia_claude.py` e `tests/test_resumo_dia_claude.py` (40 testes).
Nenhum arquivo compartilhado tocado: `montar_resumo_do_dia` da CLI ja funcionava assim que o
modulo passou a existir, e o executor conferiu em execucao em vez de editar.

O custo entrou no log (`total_cost_usd`, tokens, duracao), registrado **antes** do teste de erro
— um turno que terminou mal tambem consumiu a assinatura. Isso fecha pela metade o item de custo
do DEFERRED do tracer bullet, ja atualizado la.

Decisao do executor que o contrato nao cobria e que esta certa: **resumo inteiramente vazio e
falha**. Sem isso o diario nasceria com `## Destaques _(nada registrado)_` e nenhum aviso —
exatamente o "diario incompleto que se passa por completo" que a spec proibe.

**Fechada pelo orquestrador.** Provas conferidas, nao so reportadas:

- A invariante do dinheiro, sondada direto: com `ANTHROPIC_API_KEY` ou `ANTHROPIC_AUTH_TOKEN`
  no ambiente o adaptador recusa antes de qualquer chamada, e **nao vaza a chave** na mensagem.
- Mutacao na checagem de API paga: 3 testes caem. Mutacao no resumo vazio: 1 teste cai.
- `isinstance(ResumoDoDiaClaude(), PortaResumoDoDia)` e verdadeiro.
- `pytest` 405 verdes.

**Prova que falta**: o teste de rede nao foi rodado — ele gasta a assinatura do usuario. Fica
disponivel de proposito em `pytest -m rede tests/test_resumo_dia_claude.py`, e a prova real do
resumo cabe na camada 06, junto do primeiro diario de verdade.
