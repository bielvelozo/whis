# 18 — A suíte de testes não pode mostrar toast de verdade

Type: bug
Status: resolved
Blocked by: —

**O que ele viu** (2026-09-17, 20:20, com print): o toast *"A daily está pronta — 4 itens novos."*
aparecendo *"toda hora"* enquanto ele trabalhava.

**A causa:** dezenas de testes chamam `main(["daily", "--fakes"])`, que termina em
`_avisar_que_a_daily_nasceu` → `palheta.avisar_resultado` → `avisos.avisar` **com o executor
padrão** — o PowerShell de verdade, que deixa uma notificação real na central do Windows. Cada
execução da suíte inteira punha ~14 notificações lá, e elas ficam três dias. Quem roda a suíte na
máquina dele é o agente: as rajadas do banco do Windows (`wpndatabase.db`, AUMID `Whis.Agente`)
casam com os horários das sessões de hoje — 11:06, 12:17, 13:14, 13:49, 19:50–19:53, 20:12–20:17.
A daily de verdade saiu **uma vez**, às 13:56.

- [x] Fixture `toasts` **autouse** no `conftest.py` troca `avisos.avisar` por um registrador; nenhum
      teste alcança o PowerShell. Uma chamada com `executar=` injetado **passa direto** para o
      `avisar` de verdade — é assim que os quatro testes de montagem do comando continuam valendo.
- [x] `AVISAR_DE_VERDADE` guardado no `conftest` antes da troca, para o teste que prova que o
      PowerShell do toast nasce sem console (`test_sem_console.py`) chamar a função real.
- [x] `test_a_suite_nunca_mostra_um_toast_de_verdade` fixa a regra.
- [x] Suíte verde e **provado na máquina**: duas execuções completas depois do conserto não
      acrescentaram nenhuma linha em `wpndatabase.db` (a última continua sendo 20:17:40).

## Notas

- Limpar a central de avisos daqui não dá: `ToastNotificationManager.History` só enxerga o
  histórico da sessão interativa (`GetHistory` devolve 0 pela tarefa agendada, e com a AUMID
  assumida levanta `0x80070490`). O usuário limpa com um clique em *Limpar tudo*; as antigas
  expiram sozinhas em três dias.
- **Deferred:** o toast não leva `Tag`/`Group`, então duas dailies no mesmo dia empilham dois
  avisos em vez de um substituir o outro. Não foi pedido; é uma linha em `avisar.ps1`.

## Comments

**Fechado em 2026-09-17**, no mesmo dia em que ele reportou. Commit da correção junto deste ticket;
suíte em **1078 verdes / 8 desselecionados**.
