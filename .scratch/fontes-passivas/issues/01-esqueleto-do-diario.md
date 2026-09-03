# 01 — Esqueleto do diário com fontes fake

**What to build:** A costura desta entrega inteira: `gerar_diario(data) → nota em diario/`,
com as fontes atrás de `PortaFonte` e o resumo atrás de `PortaResumoDoDia`, exercitada por
fakes. Um comando `second-brain diario` que, com `--fakes`, produz um diário de verdade no
vault sem tocar em rede nenhuma. Este ticket estabelece tudo que as camadas seguintes vão
consumir — tipos, filtro, janela, formato da nota, chaves de configuração e o ponto de
entrada de cada fonte na CLI — e por isso é o único que pode mexer nesses arquivos.

Leia o [contrato](../contrato-fonte-passiva.md) inteiro antes de começar: ele fixa as
assinaturas, o formato da nota e todas as chaves de configuração das três fontes. Escreva
as chaves das três de uma vez, mesmo sem os coletores existirem — é o que permite construir
02, 03 e 05 em paralelo sem ninguém disputar `configuracao.py`.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] `fontes.py` com `Janela`, `Evento`, `PortaFonte`, `ErroDeFonte`, `janela_do_dia`, `data_do_diario` e `filtrar`, exatamente como o contrato descreve
- [ ] `portas.py` ganha `ResumoDoDia`, `PortaResumoDoDia` e `ErroDeResumoDoDia` ao lado das portas que já existem
- [ ] `fakes.py` ganha `FonteFake` (com eventos configuráveis e modo de falha) e `ResumoDoDiaFake` — e o fake de resumo **guarda o que recebeu**, para o teste do filtro poder provar que o conteúdo excluído não chegou nele
- [ ] `diario.py` com `gerar_diario` na ordem de operações do contrato: coleta, filtro, reuniões da janela, as três saídas antecipadas (todas falharam / dia vazio / simulação), resumo, escrita
- [ ] `vault.py`: `escrever` passa a receber as zonas permitidas, `ZONAS_DO_DIARIO`, `montar_diario` e `reunioes_na_janela` — **sem alterar nenhum teste existente de zona de propriedade**
- [ ] `configuracao.py` com as chaves de `[diario]`, `[privacidade]`, `[git]`, `[linear]` e `[slack]`, validando `inicio_do_dia` e `hora_da_tarefa`; `MODELO_DE_CONFIGURACAO` do `init` atualizado
- [ ] Subcomando `second-brain diario [YYYY-MM-DD] [--fakes] [--simular]` e `montar_fontes` com os três ramos condicionados à chave, como no contrato
- [ ] Testes de comportamento contra a costura: caminho feliz, uma fonte falhando (nota marcada), todas falhando (`TodasAsFontesFalharam`, nada escrito), dia vazio (nenhuma nota), resumo falhando (nota com listas cruas), idempotência (gerar duas vezes deixa um arquivo e reflete a mudança), janela de madrugada com `04:00` e com `00:00`, filtro (não aparece no vault **e** não chegou ao resumo), e o diário escrevendo só em `diario/`
- [ ] Suíte inteira verde, incluindo os 230 testes que já existem, sem editar nenhum deles

## Notas para o executor

- A mudança de zona é a parte delicada. `tests/test_zona_de_propriedade.py` hoje **prova que
  `diario/` é recusado** — esse teste deve continuar passando sem edição, porque continua
  verdade para o pipeline de reunião. Se você se pegar editando aquele arquivo, parou no
  caminho errado: releia a seção 4 do contrato.
- `second-brain diario` sem `--fakes` vai levantar `ImportError` até a camada 04 entregar
  `resumo_dia_claude`. Isso é esperado e não deve ser escondido com um `try` que engula o
  erro — a camada 01 entrega o caminho com fakes.
- Comentário só quando explica o **porquê** não óbvio. O motivo de o filtro agir num ponto
  só, e o motivo de a falha do resumo não abortar o diário, merecem uma linha cada.
