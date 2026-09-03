# 07 — `second-brain daily`

**What to build:** O roteiro de trinta segundos que sai do diário. O resumo do dia passa
a devolver também as três batidas de uma daily (`entreguei`, `sigo_em`, `preciso_de`), o
diário grava isso numa seção `## Daily`, e um comando novo lê a nota mais recente e
imprime pronto para falar em voz alta.

Escopo acrescentado pelo usuário em 2026-09-03, depois de ler o primeiro diário real e
perguntar se era aquilo que ele levaria para a daily. Não era: 377 linhas, narrativa
escrita na segunda pessoa ("da sua parte"), e sem a metade da frente — o diário é
retrospectivo por construção e uma daily precisa dizer o que vem hoje.

Leia o **adendo (seção 9)** do [contrato](../contrato-fonte-passiva.md): ele fixa o tipo,
o formato na nota e o comportamento do comando.

**Blocked by:** 01, 04

**Status:** ready-for-agent

- [ ] `portas.py` ganha `Daily` (`entreguei`, `sigo_em`, `preciso_de`) e `ResumoDoDia.daily: Daily | None = None`
- [ ] `resumo_dia_claude.py`: o prompt passa a pedir também as três batidas, e `interpretar_resposta` as traduz; ausência de `daily` na resposta **não** é falha (o diário continua nascendo)
- [ ] `vault.montar_diario` escreve a seção `## Daily` depois de `## Pendências` e antes de `## Reuniões`, no formato do adendo; sem `daily`, a seção não aparece
- [ ] `vault.ler_daily(vault, data)` (ou equivalente) lê a seção de uma nota já escrita — é o que o comando usa
- [ ] `vault.ultimo_diario(vault)` devolve a data do diário mais recente em `diario/`, ou `None`
- [ ] Subcomando `second-brain daily [YYYY-MM-DD]`: sem data, o diário mais recente; imprime as três batidas prontas para ler em voz alta, dizendo de que dia elas são
- [ ] Diário sem `## Daily`, `diario/` vazio, ou data sem nota: mensagem em português dizendo o que fazer e com qual comando — nunca traceback
- [ ] Testes de comportamento: a seção nasce na nota; o comando imprime; o comando acha o diário mais recente e **não** o de ontem (prove com uma sexta e uma segunda); nota sem a seção dá mensagem e código de saída ≠ 0; o comando não chama fonte nem Claude nem escreve nada
- [ ] Suíte inteira verde (**465 hoje**, 6 desselecionados), sem editar teste existente

## Notas para o executor

- **`preciso_de` é o que dá valor ao comando.** Só entra o que espera **outra pessoa**:
  review parado, PR sem merge, resposta pendente. Nota para si mesmo ("faltou testar o
  estado expirado") continua em `Pendências` e **não** vai para a daily. O prompt precisa
  ser explícito sobre isso — foi a distinção que o usuário pediu.
- **Sem chamada nova ao Claude.** A daily sai da mesma resposta que já traz narrativa,
  destaques, pendências e temas. Um comando que chamasse o Claude de novo pagaria US$ 0,29
  (medido) para reprocessar um dia já processado.
- **Sem data = diário mais recente**, não "ontem". Numa segunda-feira o último diário é o
  de sexta. O comando diz de que dia está falando, senão o usuário lê sexta achando que é
  quinta.
- Você **pode** editar `portas.py`, `vault.py`, `resumo_dia_claude.py` e `__main__.py` —
  nenhuma outra camada está rodando. Não toque em `fontes.py`, `diario.py`,
  `configuracao.py` nem nos coletores: a daily não muda coleta nem configuração.
- A nota real de 2026-09-03 no vault do usuário foi gerada **antes** desta camada e não
  tem a seção. Ela é o caso de teste do caminho "diário sem `## Daily`" — não a regere.
