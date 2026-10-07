# 06 — `--sabado` para testar o quiz em qualquer dia

Type: task
Status: resolved
Blocked by: 05

Camada 5 da [spec](../spec.md#camada-5--testar-o-sábado-sem-esperar-o-sábado-__main__py).

- `whis news --simular --sabado` e `--fakes --sabado` fazem a edição de sábado.
- `--sabado` sozinho é erro de uso (código 2).
- Uma `--simular --sabado` real ao fim, com a página aberta para conferir o quiz.

## Comments

- 2026-10-06 — Resolvido. Tarefa 12. `news --sabado` (só com `--simular`/`--fakes`, senão código 2), portas novas no `__main__` e na palheta. `news --simular --sabado` real (2026-10-06 22:06): quiz como primeira seção dizendo que volta no próximo sábado (o vault ainda não tem aula lida), nenhuma aula nova, US$ 0,59.
