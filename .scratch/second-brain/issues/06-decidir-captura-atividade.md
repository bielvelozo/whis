# Decidir a abordagem de captura de atividade

Type: grilling
Status: resolved
Blocked by: 05

## Question

Como o observador de atividade do PC funciona — o que captura, com que ferramenta, e como vira contexto no vault?

Decidir, com os fatos da [pesquisa de captura de atividade](05-pesquisa-captura-atividade.md) em mãos:

- Abordagem (ActivityWatch, screenshots + visão, hooks de janela, combinação).
- Política de privacidade: o que nunca sai da máquina em bruto; o que é resumido antes de persistir.
- Granularidade e formato do resumo diário/por sessão de trabalho no vault.
- Como o liga/desliga sob demanda funciona.

## Answer

**Não haverá monitoramento de atividade do PC** — decisão do usuário em 2026-08-14, redesenhando o escopo no meio do grilling: "só transcrever as reuniões, analisar meu histórico, Linear e Slack já é o suficiente, não precisa de um monitoramento full".

- Todo o ramo de observação ativa — ActivityWatch, screenshots + visão, hooks de janela, e a evolução "sempre-ligado" — vai para **Out of scope** no mapa.
- O contexto de trabalho passa a vir de **fontes passivas**: histórico do **git** local (a fonte que o usuário citou primeiro), **Linear** e **Slack** do trabalho (o usuário confirma que consegue criar tokens/apps), e histórico do **navegador** se se provar relevante.
- O que se lê de cada fonte e como isso vira nota no vault fica para [Decidir as integrações de fontes passivas](13-decidir-fontes-passivas.md), alimentado pela [pesquisa de acesso às fontes](12-pesquisa-fontes-passivas.md).
- A [pesquisa de captura de atividade](05-pesquisa-captura-atividade.md) não foi desperdiçada: documenta por que o caminho foi descartado e serve se a decisão for revisitada em outro esforço.
