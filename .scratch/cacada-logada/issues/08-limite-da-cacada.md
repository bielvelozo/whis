Status: resolved

# Limite da caçada

Hoje vai até acabar o plano (bom para a madrugada de sexta). Limite de tempo e de plano gasto, padrão automático: sem limite quando a virada da semana do plano está a menos de 24 h, com limite nos outros dias (padrão a definir em config); --limite / --sem-limite na linha de comando; o relatório diz que parou pelo limite.

## Answer

- Duas chaves em `[cacada]`: `limite_minutos` (90) e `limite_plano` (15 pontos do plano semanal). 0 desliga cada uma.
- `whis hunt --limite-minutos N`, `--limite-plano N` e `--sem-limite`. Qualquer opção de limite desliga o automático e vale mesmo perto da virada; a que não foi dada vem do config. `--sem-limite` junto com uma das outras é erro de uso (código 2).
- Automático (`cacada.LimiteDaCacada`, `GuardaDoPlano`): sem limite quando a próxima virada está a menos de 24 h do início desta chamada. A virada vem de `virada.json` (com `lembrete.proxima_virada`) ou, sem esse arquivo, do primeiro plano lido. A decisão é tomada uma vez e não muda durante a corrida. Se a virada nunca aparece, os limites valem.
- O tempo conta desde o início desta chamada do `hunt`, e a pausa da janela de 5 h entra na conta. O plano gasto é o semanal atual menos o primeiro lido nesta chamada.
- A guarda confere o limite antes de cada chamada ao Claude, nunca depois: a chamada que já rodou entra no checkpoint e nada novo começa. Ela levanta `LimiteBatido` (uma `Parada`), o relatório é escrito com "A caçada parou no limite desta corrida" e o motivo (qual limite e quanto gastou), e o código de saída é parcial.
- **Fica retomável**, como toda `Parada`: o checkpoint não é fechado e a próxima chamada continua de onde parou, com limite novo. A ideia é fatiar a caçada em pedaços diários de 90 min sem jogar fora o que já foi feito; a retomada continua expirando em 4 dias.
- Modo freelas com limite: não atravessa a virada, o extra roda só até o limite (se ele bate no extra, o extra encerra, a corrida termina inteira e o relatório diz "O extra parou no limite desta corrida") e não emenda a caçada de vagas (`ResultadoDaCacada.com_limite`).
- O relatório mostra "Limite desta corrida: ..." sempre que um limite está valendo.
- Testes em `tests/test_limite_da_cacada.py`.

