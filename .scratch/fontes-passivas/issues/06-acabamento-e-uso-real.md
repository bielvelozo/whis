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

**Status:** resolved

- [x] `second-brain daily` e `second-brain diario` escrevem no arquivo de log (`registro.acrescentar_arquivo`), como `limpar` já faz — sem isso uma execução que falhou não deixa rastro nenhum
- [x] Códigos de saída que distinguem os casos, documentados no `--help`: sucesso completo; **nasceu parcial** (fonte falhou ou resumo falhou); **não nasceu** (todas as fontes falharam, nenhuma fonte configurada, dia vazio)
- [x] Fonte que falha aparece no log com o motivo, e o motivo é o mesmo texto que vai para o aviso da nota
- [x] `docs/smoke-daily.md`: roteiro curto de ponta a ponta — conferir o filtro com `--simular`, anotar um ponto com `--anotar`, gerar a daily, ler no Obsidian, marcar o checkbox e conferir que ele sumiu na seguinte
- [x] Testes de comportamento para os códigos de saída e para o rastro em log, pela costura da CLI (`main([...])`)
- [x] Suíte inteira verde (**538 hoje**, 7 desselecionados), sem editar teste existente

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

## Comments

**Camada 06 entregue** — `__main__.py` (códigos de saída, `--help`, rastro no log),
`docs/smoke-daily.md` e 19 testes novos em `tests/test_comando_codigos_de_saida.py`. Suíte em
**557 verdes**, 7 desselecionados, **nenhum teste existente editado**. `automacao.py` não foi
tocado e nada é agendado.

O que já estava lá ao abrir: `daily` e `diario` **já chamavam** `registro.acrescentar_arquivo`
(camadas 01 e 07), com teste de rastro em cada um. O item 1 foi conferido, não construído.

**Códigos de saída** (`SAIDA_COMPLETA = 0`, `SAIDA_PARCIAL = 3`, `SAIDA_NAO_NASCEU = 1`), num
ponto só, `_codigo_de_saida`, usado pelos dois comandos. `2` ficou de fora de propósito: é o
que o argparse devolve para erro de uso, e `1` já era o "não nasceu" dos testes existentes
(`NenhumaFonteConfigurada`). **Dia vazio passou a sair `1`** — era `0`; é o que o ticket pede,
e nenhum teste existente dependia do contrário. A simulação com fonte falhando também sai `3`:
o que ela mostrou é incompleto. A mesma função escreve no log como a execução terminou
(`Daily de 2026-09-03: a nota nasceu inteira (saída 0)`), que é a linha que sobra de uma
execução que ninguém viu.

**Provas executadas, não reportadas:**

- **`--help` real** dos dois comandos mostra a tabela dos códigos e onde fica o log.
- **`daily --simular` na máquina do usuário**, com git e Linear reais e sem Claude: 50 commits
  + 210 eventos do Linear + 2 reuniões, 260 linhas, saída `0`. `bandeja.log` ganhou a linha
  `Daily de 2026-09-03: a nota nasceu inteira (saída 0)` no fim.
- **Todas as fontes falhando, sem fake nem monkeypatch**: configuração só com `[git].raiz`
  apontando para uma pasta inexistente — a `FonteGit` de verdade falha sem rede, o comando sai
  `1`, nada é escrito, e `bandeja.log` tem "Raiz de desenvolvimento não encontrada" e "Nenhuma
  fonte respondeu".
- **Motivo igual no log e na nota**: `Fonte 'slack' não pôde ser lida: token do Slack ausente em
  [slack].user_token` no log e `> Slack não entrou nesta daily: token do Slack ausente em
  [slack].user_token` na nota — a mesma string, vinda de `FalhaDeFonte.motivo`.
- **Parcial por fonte e parcial por Claude**, nos dois comandos: nota existe, frontmatter marca a
  fonte, listas cruas ficam, saída `3`. As fontes/roteiro que falham entram trocando as fábricas
  de `__main__` (`montar_fontes_da_daily`, `montar_roteiro_da_daily` e as do diário) — é o ponto
  de injeção da CLI, não detalhe interno.
- **Mutações**: fazer `_codigo_de_saida` devolver sempre `0` derruba 9 testes; tirar o `epilog`
  derruba 2.

Achado de passagem: o DEFERRED dizia que o teste de rede do prompt da daily **não existia**; ele
existe (`test_roteiro_real_separa_o_trabalho_dele_do_contexto_do_time`), só nunca foi rodado.
Corrigido no DEFERRED junto com a mensagem de `montar_fontes`, que falava só em "diário".

**Não provado: a prova humana.** Uma daily real com Claude gasta a assinatura (~US$ 0,30) e o
ticket manda pedir antes. O que pode ser rodado sem custo foi rodado; a daily de verdade e o
teste de rede do prompt esperam o sim do usuário.
