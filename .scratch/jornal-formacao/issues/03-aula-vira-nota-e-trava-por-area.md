# 03 — A aula vira nota e a área só avança lida

Type: task
Status: resolved
Blocked by: 02

Camada 2 da [spec](../spec.md#camada-2--a-aula-vira-nota-e-a-área-só-avança-lida-aulaspy-jornalpy-jornal_claudepy).

- `aulas.py`: escreve e lê `noticias/aulas/<id>.md` (+ `<id>.svg`), ida e volta testadas.
- Vagas descontam as pendentes de dias anteriores; se já nasceu aula hoje, nenhuma vaga.
  `ensinar(data, trilha, vagas)`; sem vaga, a formação não é chamada.
- Ordem: pendentes antigas, as de hoje, as novas; "Pendente desde dd/mm" na página e na nota.
- Rodar de novo no mesmo dia: sem aula a mais, sem id repetido, sem trilha duplicada.
- Aula que volta: foto baixada de novo da `imagem:`, esquema relido do `.svg`.
- `--simular` não escreve nota de aula.
- Nesta camada, marcar é só pelo Obsidian (`status: lida`).

## Comments

- 2026-10-06 — Resolvido. Tarefas 4–5. `aulas.py` (executor, revisado) e a costura em `jornal.py`: vagas por área, formação não chamada sem vaga, uma vez por dia, pendentes antigas primeiro com "Pendente desde", trilha só com as novas. Testes: `test_aulas` e os de trava em `test_jornal`.
