# 04 — Resumo do dia pelo Claude

**What to build:** `resumo_dia_claude.py`: o adaptador real de `PortaResumoDoDia`, falando
com o Claude da conta do usuário pelo Claude Agent SDK (OAuth), como já faz
`resumo_claude.py` para as reuniões. Recebe os eventos do dia e as reuniões, devolve
narrativa, destaques, pendências e temas em português.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] `ResumoDoDiaClaude` implementa `PortaResumoDoDia`, com a mesma postura do adaptador de reunião: **recusa** cair para `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`, um turno só, sem ferramenta nenhuma, sem acesso a disco
- [ ] Prompt que produz um dia legível: narrativa curta ligando as fontes (não uma lista reescrita), destaques do que importou, pendências abertas e temas para o frontmatter; preserva termos técnicos em inglês; nunca inventa o que não está nos eventos
- [ ] Resposta em JSON, interpretada para `ResumoDoDia`; resposta que não vira `ResumoDoDia` levanta `ErroDeResumoDoDia` com trecho de diagnóstico
- [ ] Sem credencial, sem CLI, timeout ou dia grande demais também viram `ErroDeResumoDoDia` — o diário nasce sem narrativa e marcado, que é o comportamento que a camada 01 já implementa
- [ ] Limite de tamanho declarado, no espírito do `LIMITE_DE_CARACTERES` do adaptador de reunião, e um caminho honesto quando o dia estoura: recusa clara, nunca uma chamada que vai falhar
- [ ] `montar_resumo_do_dia` da CLI passa a devolver o adaptador real quando não for `--fakes`
- [ ] Testes sem rede: montagem da pergunta, interpretação de resposta boa, de resposta suja (cercas de código, texto em volta) e de resposta inválida; recusa quando há variável de API paga no ambiente
- [ ] Um teste `@pytest.mark.rede` que só roda de propósito — ele gasta a assinatura do usuário

## Notas para o executor

- Espelhe `resumo_claude.py`: ele já resolveu OAuth, opções do SDK, timeout, parse tolerante
  e recusa de API paga. Reaproveite o que der; não copie o que não servir — a entrada aqui é
  uma lista de eventos, não uma transcrição.
- O [DEFERRED](../../tracer-bullet/DEFERRED.md) registra que o custo do resumo é descartado
  hoje (`ResultMessage.total_cost_usd`). Com o diário rodando todo dia isso passa a importar:
  **registre o custo no log** desta camada. É barato e fecha um item deferido.
- Dia sem eventos não chega aqui — a camada 01 corta antes.
