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

**Status:** resolved

- [x] `fontes.py` com `Janela`, `Evento`, `PortaFonte`, `ErroDeFonte`, `janela_do_dia`, `data_do_diario` e `filtrar`, exatamente como o contrato descreve
- [x] `portas.py` ganha `ResumoDoDia`, `PortaResumoDoDia` e `ErroDeResumoDoDia` ao lado das portas que já existem
- [x] `fakes.py` ganha `FonteFake` (com eventos configuráveis e modo de falha) e `ResumoDoDiaFake` — e o fake de resumo **guarda o que recebeu**, para o teste do filtro poder provar que o conteúdo excluído não chegou nele
- [x] `diario.py` com `gerar_diario` na ordem de operações do contrato: coleta, filtro, reuniões da janela, as três saídas antecipadas (todas falharam / dia vazio / simulação), resumo, escrita
- [x] `vault.py`: `escrever` passa a receber as zonas permitidas, `ZONAS_DO_DIARIO`, `montar_diario` e `reunioes_na_janela` — **sem alterar nenhum teste existente de zona de propriedade**
- [x] `configuracao.py` com as chaves de `[diario]`, `[privacidade]`, `[git]`, `[linear]` e `[slack]`, validando `inicio_do_dia` e `hora_da_tarefa`; `MODELO_DE_CONFIGURACAO` do `init` atualizado
- [x] Subcomando `second-brain diario [YYYY-MM-DD] [--fakes] [--simular]` e `montar_fontes` com os três ramos condicionados à chave, como no contrato
- [x] Testes de comportamento contra a costura: caminho feliz, uma fonte falhando (nota marcada), todas falhando (`TodasAsFontesFalharam`, nada escrito), dia vazio (nenhuma nota), resumo falhando (nota com listas cruas), idempotência (gerar duas vezes deixa um arquivo e reflete a mudança), janela de madrugada com `04:00` e com `00:00`, filtro (não aparece no vault **e** não chegou ao resumo), e o diário escrevendo só em `diario/`
- [x] Suíte inteira verde, incluindo os 230 testes que já existem, sem editar nenhum deles

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

## Comments

**Camada 01 entregue** — `fontes.py`, `diario.py`, a ampliacao de `portas.py`, `fakes.py`,
`vault.py`, `configuracao.py` e `__main__.py`, com 60 testes novos de comportamento contra a
costura `gerar_diario(data) → nota em diario/`. A zona de propriedade virou parametro por
coletor, como o contrato pedia: `tests/test_zona_de_propriedade.py` nao foi tocado e continua
provando que o pipeline de reuniao **nao** escreve em `diario/`.

Cinco achados fora do escopo foram para `DEFERRED.md` (o que `--simular` mostra do filtro, o
link de volta da reuniao para o diario, a releitura da pasta de reunioes, a indistincao entre
"zero eventos" e "tudo filtrado", e a duplicacao de montagem de markdown).

**Fechada pelo orquestrador.** A revisao encontrou um furo de cobertura: o fim da janela ser
**exclusivo** nao era testado — mutar `Janela.contem` de `<` para `<=` passava nos 290 testes.
Sem isso, um evento exatamente na virada (04:00) apareceria em **dois** diarios. Acrescentado
`test_evento_na_virada_pertence_so_ao_diario_seguinte`, que prova que a nota do dia nao nasce e
o evento aparece so no diario seguinte; confirmado que ele falha com a mutacao e passa sem ela.

Provas conferidas pelo orquestrador, nao so reportadas:

- `pytest` 291 verdes, 3 desselecionados; `git status` confirma nenhum teste existente editado.
- Zona de propriedade sondada direto: 6 fugas do diario recusadas (`reunioes/`, `transcricoes/`,
  `notas/`, e tres travessias com `..`), 3 fugas do pipeline de reuniao recusadas, `notas/ideias.md`
  intacta, nada escrito fora do vault.
- Mutacao em `filtrar` (nao filtrar nada) → 3 testes falham; mutacao em `gerar_diario`
  (todas-as-fontes-falharam vira parcial silencioso) → 1 teste falha. Os testes mordem.
- Execucao real de `second-brain diario --fakes`: nota lida no disco, com frontmatter, resumo,
  reuniao linkada e as listas cruas agrupadas por repositorio/projeto.
- Caso de degradacao gerado pelo orquestrador: Slack falhando + Claude falhando → aviso no topo,
  `fontes_com_falha: [slack]`, secao do Slack com o motivo, Linear vazio como `_(nada registrado)_`
  (distinto de falha), listas cruas do git intactas e nenhuma secao de Destaques/Pendencias.
- Frontmatter validado como **YAML de verdade** por um parser externo: os sete campos leem como
  o contrato manda, incluindo o wikilink entre aspas e `temas: []`.
- Idempotencia: segunda execucao deixa um arquivo so. `--simular` nao escreve nada.
- O `config.toml` real do usuario em `%APPDATA%` continua carregando, com as chaves novas nos padroes.

Desvio do contrato aceito: `ResultadoDoDiario.falha_do_resumo`, campo novo. O contrato mandava
registrar a falha do resumo mas nao dizia onde; enfia-la em `fontes_com_falha` sujaria o
frontmatter (o Claude nao e uma fonte). O campo separado esta certo.
