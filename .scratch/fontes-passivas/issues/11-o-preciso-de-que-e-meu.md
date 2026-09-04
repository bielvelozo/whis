# 11 — O "preciso de" que é meu

**What to build:** `notas/daily.md` ganha a seção `## Preciso de`, e o que o usuário escrever
nela entra na batida `Preciso de` da daily, junto com o que o Claude achou. Pedido em
2026-09-04.

**Blocked by:** 07 (fechada)

**Status:** resolved

## Por que essa seção faltava

O arquivo dos pontos já tinha `Dúvidas`, `Off-topic` e `Pontos`, e as dúvidas dele já se juntavam
às do Claude. `Preciso de` era a única batida do roteiro em que ele **não podia** escrever — e é
justamente onde ele sabe mais que o modelo.

O motivo é estrutural: um bloqueio combinado numa conversa de corredor, numa ligação ou numa
reunião não gravada **não deixa rastro em fonte nenhuma**. O Claude só enxerga commit, issue e
mensagem; se ninguém escreveu em lugar nenhum que o acesso está pendente, para ele aquilo não
existe. A daily real de 2026-09-04 mostrou o outro lado disso: `preciso_de` voltou vazio, e
estava certo — mas se houvesse um bloqueio combinado no boca a boca, teria voltado vazio do
mesmo jeito.

## As decisões

- **Junta, não duplica.** `Preciso de` é uma batida só, falada uma vez. O que ele escreveu entra
  na mesma seção do que o Claude achou, como já era com `Dúvidas`. Duas seções parecidas fariam
  ele falar a mesma coisa duas vezes.
- **Continua fora do Claude.** O arquivo é da zona dele e nunca vai a serviço externo — nem
  agora, nem antes. Há teste mordendo isso.
- **A seção nova entra no modelo**, antes de `Dúvidas`, na ordem de falar.
- **Um item só nela já faz a daily existir**, como já valia para as outras: é a única coisa da
  daily que não se recupera de lugar nenhum depois.

## Critérios de aceite

- [x] `## Preciso de` é reconhecida em `notas/daily.md` (com e sem acento no `_`)
- [x] O item desmarcado entra na batida `Preciso de`, junto com o do Claude, numa seção só
- [x] Item marcado não volta
- [x] Só um item dela já impede a daily de ser considerada vazia
- [x] O que ele escreve ali não chega ao Claude
- [x] `MODELO_DOS_PONTOS` traz a seção, antes de `Dúvidas`
- [x] Suíte verde (**607**), sem editar teste existente

## Comments

**Camada 11 entregue e fechada.** `vault.py` e 7 testes novos em
`tests/test_daily_do_trabalho.py`. Suíte em **607 verdes**, 7 desselecionados.

Um detalhe de comportamento mudou junto: `Preciso de` deixou de depender só do roteiro para
aparecer. Antes, sem roteiro (Claude falhou), a seção sumia; agora, se o usuário escreveu algo
nela, ela aparece mesmo assim — do mesmo jeito que `Dúvidas` já fazia.

**Provas executadas:**

- **Mutação**: fazer a batida ignorar o que o usuário escreveu derruba 4 testes.
- **O arquivo real do usuário** ganhou a seção sem perder nenhuma linha: cada linha anterior foi
  conferida no arquivo depois, e o ponto que ele já tinha continua onde estava.
- **`pontos_da_daily` lido do disco real** devolve a estrutura nova, com `preciso_de` vazio e o
  ponto antigo intacto.
- O teste de que o conteúdo dele **não** chega ao `DailyFake` continua sendo a prova de que a
  nota é local.

**Não provado com dado real:** um `preciso de` escrito por ele aparecendo numa daily gerada com
o Claude de verdade. A próxima execução paga fecha isso.
