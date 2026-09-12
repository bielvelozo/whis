# 06 — Decisão e spec da entrega 4

Type: task
Status: resolved
Blocked by: 05

## Answer

Spec publicada em [../spec.md](../spec.md), `ready-for-agent`, com escopo confirmado pelo usuário
em 2026-09-11. **A entrega 4 é a casca mais o conserto da daily** — nenhum dos seis comandos
futuros entra nela.

O que a spec fixa, em uma linha cada: `daily/atual.md` como nota viva de quatro seções, com uma
**terceira zona de propriedade** declarada no glossário e a regra dura de **carregar o texto sem
reescrever**; a palheta de comandos com atalho global (sem dependência nova) e contrato de
*dispara e some*; o painel de configuração com escritor de TOML próprio; o vigia que avisa por
toast sem depender de nada do Whis; e a camada zero que arruma a casa, sem a qual nada sobe.

Cinco decisões anteriores foram revertidas de propósito, e estão nomeadas no topo da spec.

## What to build

A **spec construível** da entrega 4, com user stories tiradas **do dia dele**, não das
superfícies. O destino do mapa.

- A decisão de superfície (provavelmente uma combinação: nenhuma candidata exclui as outras).
- User stories no padrão da casa, no formato das specs anteriores
  (`.scratch/recuperacao-contexto/spec.md` é o modelo mais recente, com contrato fixado).
- O que dos seis achados do DEFERRED vira user story e o que morre com a decisão.
- O que fica de fora, dito com todas as letras.

Só depois da spec aprovada por ele é que alguém escreve código de interface. A construção é
outra sessão, com contrato.

## Notas para o executor

- **Não decida pela arquitetura.** Está escrito três vezes no handoff de propósito.
- Custo por gesto (medido) entra na spec: pergunta na DM ≈ US$ 0,56 e 60 s; daily de um dia ≈
  US$ 0,70; daily de segunda-feira US$ 1,74 e 36 s. Botão de "gerar de novo" tem preço.
- A nota da daily **é** o registro durável; o roteiro impresso no terminal é descartável. Uma
  interface pode ler a nota em vez de reexecutar.
