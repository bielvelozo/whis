# 06 — Acabamento e uso real

**What to build:** O que falta para a daily e o diário serem confiáveis em uso de verdade:
rastro em log, códigos de saída que distinguem os modos de falha, e o roteiro de smoke que
prova a entrega numa máquina real. É também a camada que fecha a degradação graciosa como
comportamento observado, não como teste.

> **Este ticket foi reescrito em 2026-09-03.** A versão original pedia `second-brain windows
> --diario` para agendar o diário. **Isso foi cancelado**: o usuário decidiu que nada é
> agendado — nem o diário nem a daily. Ele roda `second-brain daily` na hora, um minuto antes
> de falar. Não construa agendamento; se algo aqui parecer pedir isso, é resíduo e vale
> confirmar antes.

**Blocked by:** 01, 02, 03, 04, 07

**Status:** ready-for-agent

- [ ] `second-brain daily` e `second-brain diario` escrevem no arquivo de log (`registro.acrescentar_arquivo`), como `limpar` já faz — sem isso uma execução que falhou não deixa rastro nenhum
- [ ] Códigos de saída que distinguem os casos, documentados no `--help`: sucesso completo; **nasceu parcial** (fonte falhou ou resumo falhou); **não nasceu** (todas as fontes falharam, nenhuma fonte configurada, dia vazio)
- [ ] Fonte que falha aparece no log com o motivo, e o motivo é o mesmo texto que vai para o aviso da nota
- [ ] `docs/smoke-daily.md`: roteiro curto de ponta a ponta — conferir o filtro com `--simular`, anotar um ponto com `--anotar`, gerar a daily, ler no Obsidian, marcar o checkbox e conferir que ele sumiu na seguinte
- [ ] Testes de comportamento para os códigos de saída e para o rastro em log, pela costura da CLI (`main([...])`)
- [ ] Suíte inteira verde (**538 hoje**, 7 desselecionados), sem editar teste existente

## Notas para o executor

- **Não crie tarefa agendada e não toque em `automacao.py`.** A limpeza diária do áudio bruto
  (`SecondBrain-Limpeza`) continua agendada — ela é do tracer bullet e não muda.
- O rastro em log importa porque `pythonw.exe` não tem console: é a armadilha registrada no
  handoff da entrega anterior. Hoje o `daily` e o `diario` rodam de terminal, mas o log é o que
  permite diagnosticar uma execução que ninguém viu.
- Os códigos de saída são o que distingue "sua daily nasceu sem o Slack" de "sua daily não
  nasceu". Hoje ambos podem sair 1; ver `ResultadoDaDaily.fontes_com_falha` e
  `falha_do_roteiro`.
- A prova final desta camada é humana: uma daily de verdade, gerada na máquina do usuário com
  git e Linear reais, lida por ele antes de uma daily real. Isso gasta a assinatura Claude
  (~US$ 0,29 medidos) — peça antes de rodar.
