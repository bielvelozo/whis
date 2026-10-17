Status: resolved
Blocked by: 01

# Vigia de freelas

`whis vigia-freelas` lê a primeira página da 99Freelas (web, mobile e software) e a API pública do Freelancer.com com a busca do nicho, sem Claude e sem Chrome. Fica o que cita o nicho, foi publicado nas últimas horas e ainda não foi avisado. Cada um vira um toast com o título, o orçamento, quantas propostas já tem e o botão que abre o link; o exclusivo da 99Freelas diz quando abre para ele. O que já foi avisado fica em `%LOCALAPPDATA%\whis\cacada\vigia-de-freelas.json`.

- A primeira rodada só guarda o que já está lá, sem avisar (senão chegam dezenas de toasts).
- No máximo uns poucos toasts por rodada; o resto vira um toast "e mais N".
- Sem `[cacada].nicho_freela`, não roda e diz por quê.
- `--fakes`: um projeto falso, estado temporário, toast de verdade.
- `whis automacao --vigia-freelas` registra `Whis-Vigia-Freelas` com um gatilho diário em cada hora de `[cacada].horarios_da_vigia` (padrão a cada 3 h de 08:00 a 23:00); `--remover --vigia-freelas` tira.

Não é o **Vigia** (`Whis-Vigia`): nome, script e tarefa separados.

## Comments

Feito em 2026-10-17 (test_vigia_de_freelas.py). `whis vigia-freelas --fakes` mostrou o toast do projeto falso; a leitura ao vivo trouxe 58 projetos, 38 do nicho, e a primeira rodada só guardou. Visto na leitura: no Freelancer.com um projeto Shopify chega a 52 propostas em 1 h, então lá a vigia de 3 em 3 h ainda chega tarde; na 99Freelas, os mais novos são exclusivos de assinante nas primeiras 24 h (o toast diz quando abre). Não entrou no `tarefas_vigiadas` do Vigia (mudaria os testes dele); fica para depois.
