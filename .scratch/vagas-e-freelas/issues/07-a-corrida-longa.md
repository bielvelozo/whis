# 07 — A corrida longa

Type: research
Status: resolved

## Question

A busca roda por horas, chamada à mão, gastando o que sobrou da assinatura na véspera da
renovação. O contrato de comando de hoje (*dispara e some*) foi desenhado para minutos, e a
interface já previu este dia (Q35): *"quando ela chegar, o contrato de comando provavelmente será
reescrito"*. Levantar:

- **Os limites da assinatura.** Janela de 5 horas e limite semanal: o que o Agent SDK/`claude -p`
  devolve quando o limite bate (evento, código de saída), e se dá para saber o que sobra antes de
  começar. A corrida pausa até a janela abrir de novo, ou termina com o que tem?
- **Suspensão, logoff, reboot.** Manter o PC acordado enquanto roda (`SetThreadExecutionState`), e
  retomar de onde parou se cair: o estado da corrida precisa estar em disco.
- **Não comer a cota do trabalho.** Se ele chamar fora da véspera, o Whis avisa? Para num teto?
- **Ver que está viva.** Uma corrida de horas precisa de algo que diga em que site está e quanto já
  achou, sem ele ter que olhar log.

Achados em `../research/07-a-corrida-longa.md`.

## Answer

[Research 07](../research/07-a-corrida-longa.md).

- **A véspera é a da virada do limite semanal**, que tem hora fixa por conta, não a da cobrança. O
  `RateLimitEvent` traz `seven_day.resetsAt`.
- **O limite é um evento**: `status == "rejected"` com `resets_at`, `AssistantMessage.error ==
  "rate_limit"`, `ResultMessage` com `api_error_status == 429` e, no SDK ≥ 0.2.140, `ResultError`.
  O SDK e o `-p` não esperam sozinhos: a espera é do Python.
- **Estratégia adotada**: pausa na janela de 5 h; para no teto semanal e 30 min antes da virada;
  teto menor fora da véspera.
- **Muitas chamadas curtas conduzidas pelo Python**, com quem lê separado de quem age; estado em
  disco por etapa e por item; o PC acordado com `SetThreadExecutionState`.
- Simplificação do agente: a pausa dorme no próprio processo (com o PC acordado) em vez de
  registrar uma tarefa `-WakeToRun`; reboot e logoff viram "rode `hunt` de novo", que retoma.
