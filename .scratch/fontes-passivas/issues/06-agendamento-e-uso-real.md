# 06 — Agendamento diário e uso real

**What to build:** O que falta para o diário existir sem ninguém digitar nada: a tarefa
agendada do Windows, o rastro em log de uma execução sem console, e o roteiro de smoke que
prova a entrega numa máquina de verdade. É também a camada que fecha a degradação graciosa
como comportamento observado, não como teste.

**Blocked by:** 01, 02, 03, 04

**Status:** ready-for-agent

- [ ] `second-brain windows --diario` registra a tarefa diária `SecondBrain-Diario` no Agendador, na hora de `[diario].hora_da_tarefa`, pelo mesmo mecanismo de `agendar_limpeza`; `--remover --diario` desfaz
- [ ] A execução agendada escreve no log (`registro.acrescentar_arquivo`), como a limpeza já faz — sem isso, um diário que não nasceu não deixa rastro nenhum, porque `pythonw.exe` não tem console
- [ ] Fonte que falha aparece no log com o motivo, e o comando termina com código de saída que distingue "diário nasceu parcial" de "nenhuma fonte respondeu"
- [ ] Testes com o executor injetado (mesmo padrão de `automacao.py`), provando o comando montado sem mexer no Agendador da máquina de teste
- [ ] `docs/smoke-diario.md`: roteiro curto de ponta a ponta — configurar as fontes, rodar `--simular` para conferir o filtro, gerar o diário do dia, abrir no Obsidian, e agendar
- [ ] Um diário de verdade gerado na máquina do usuário, com as fontes reais, e conferido por ele

## Notas para o executor

- `automacao.py` já tem tudo: `agendar_limpeza`, `desagendar_limpeza`, `Executor` injetável,
  `interpretador_sem_console()`. Siga o mesmo formato; não invente um mecanismo novo.
- O `--hora` que já existe é o da limpeza. O horário do diário vem de
  `[diario].hora_da_tarefa` — dois horários no mesmo flag confundiria (contrato, seção 7).
- A tarefa precisa da máquina ligada. O padrão de 19:00 assume fim de expediente com o PC
  aceso; se o usuário preferir outro horário, é uma linha na configuração.
