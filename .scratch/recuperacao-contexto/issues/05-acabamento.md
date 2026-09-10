# 05 — Acabamento e uso real

**What to build:** o que falta para o agente ser confiável no dia a dia: subir com o logon,
deixar rastro, mostrar o custo, e o roteiro que prova tudo na máquina do usuário — incluindo o
pedido ao admin.

**Blocked by:** 01, 02, 03, 04

**Status:** ready-for-human

- [x] `second-brain windows` passa a poder instalar o atendente no logon, ao lado da bandeja
- [x] `atender` e `perguntar` escrevem no arquivo de log, como `daily` e `diario` já fazem
- [x] O custo de cada resposta vai para o log, com o aviso de que a assinatura não cobra por token
- [x] Códigos de saída de `perguntar` documentados no `--help`, no padrão da entrega anterior:
      `0` respondeu, `3` respondeu sem achar, `1` não conseguiu, `2` erro de uso
- [x] `docs/smoke-atendente.md`: criar o bot na app que já existe, os scopes, o Socket Mode, o
      app-level token, **o texto do pedido ao admin já pronto para colar**, e o teste de ponta a
      ponta pela DM
- [x] O roteiro cobre a pasta privada: configurar, perguntar sobre algo que só existe lá, e
      confirmar que o agente diz que não achou
- [x] Suíte inteira verde (**859**, eram 849), sem editar teste existente

## Notas para o executor

- O `docs/smoke-slack.md` atual diz ao admin que a app **não** pede bot token. Atualize-o, ou o
  usuário chega na conversa com o admin contradizendo o que prometeu antes.
- A prova final é humana: a demo-mestra da seção 7 do contrato, pelo celular. **Gasta a
  assinatura — peça antes.**

## Comments

**Camada 05 construída** (2026-09-04); `ready-for-human` porque o roteiro e a demo-mestra
são a prova, e ela é do usuário.

Entregue: `second-brain windows --atendente` (atalho separado `Second Brain Atendente.lnk`,
por `automacao.instalar_atendente`, com `_criar_atalho` compartilhado com o da bandeja),
`CODIGOS_DA_PERGUNTA` no `--help` de `perguntar`, `docs/smoke-atendente.md` (bot, scopes,
Socket Mode, app-level token, **o texto do pedido ao admin pronto**, ensaio com `--fakes`,
demo-mestra, pasta privada, `anotar`, logon), `docs/smoke-slack.md` corrigido nos três
pontos em que prometia que a app não pediria bot token, e 10 testes novos em
`test_acabamento_atendente.py`. Suíte em **859 verdes**, 8 desselecionados, nenhum teste
existente editado. Log e custo por resposta já tinham entrado nas camadas 02 e 04.

**Provas executadas:** mutação em 6 linhas — atalho do atendente aponta para a bandeja → 1;
os dois atalhos no mesmo arquivo → 2; erro do Windows engolido → 2; remover o atendente não
remove → 1; `windows` ignora `--atendente` → 3; `--help` sem os códigos → 1. Nenhuma
sobreviveu. O atalho não foi criado na máquina real: é decisão do usuário, pelo comando.

**Não provado, e é o que fecha a entrega inteira**: a demo-mestra do passo 8 do roteiro, pelo
celular, e antes dela o passo humano do bot. Nenhuma pergunta real ao Claude foi feita em
nenhuma camada — **peça antes**, gasta a assinatura.

### Parcial — 2026-09-10

O roteiro `docs/smoke-atendente.md` foi seguido do passo 1 ao 8 com o usuario, e passou. O que
ele provou esta no comentario de entrega do ticket 04. O roteiro ganhou o custo real medido na
secao "Quanto pesa na assinatura", como ele mesmo pedia.

Correcoes que o uso real exigiu no proprio roteiro: os scopes de bot vem **antes** do App Home
(o Slack so libera as abas depois do primeiro scope), e a Messages Tab tem **duas** marcacoes —
ligar a aba faz a DM aparecer, mas *Allow users to send Slash commands and messages* e um
checkbox separado, e sem ele o Slack mostra "Sending messages to this app has been turned off".

**Continua `ready-for-human`**, e por dois passos que so o usuario fecha:

- **Passo 9, a pasta privada.** `[privacidade].pastas_privadas` continua vazia desde 04/09 — o
  agente enxerga o vault inteiro. Falta ele escolher a pasta e plantar o fato de teste. E a
  unica garantia de privacidade da entrega, e a unica nao exercitada na maquina dele.
- **Passo 11, subir no logon.** `windows --atendente` ainda nao rodou. Esperando o rename da
  pasta do repositorio, porque o atalho grava o caminho absoluto do venv.

O passo 5 (pedido ao admin) nao foi enviado: a reinstalacao passou sem aprovacao, entao nao ha
portao tecnico. Fica como aviso pendente, porque o texto anterior afirmava ao admin que a app
nao teria scope de escrita, e agora tem quatro de bot. Decisao do usuario.
