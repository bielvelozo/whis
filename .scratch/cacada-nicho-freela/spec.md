# Caçada de freela com nicho

Origem: `whis-vault/cacada/roadmap-freela-shopify.md`, seção "O que o Whis pode melhorar", itens 1 a 5. Pedido em 2026-10-17 pela sessão que cuida do roadmap.

## O problema

Em 14/10 o diagnóstico mostrou que o modo freelas (`whis hunt --freelas`) chama de chance boa quase tudo (Shopify, landing, bug, API, automação, scraping, LLM): 8 das 9 propostas mandadas não eram de Shopify, o nicho em que ele tem prova real. A caçada roda uma vez por semana e chega quando o projeto já tem 80 ou mais propostas. Ele decidiu: freela só em Shopify; vaga continua full stack generalista. Ele escreve as propostas à mão (`[cacada].pacote_completo = false`).

## O que muda

1. `[cacada].nicho_freela` (ex.: `"shopify"`; vazio = como hoje). No modo freelas, chance boa é só do nicho ou de e-commerce muito perto; o resto vira no máximo tentar a sorte. A regra vai no pedido do modo **e** numa conferência em Python depois da triagem, porque o pedido sozinho é o que falhou. As buscas do modo no Freelancer.com fora do nicho saem (as fontes dele em `criterios.md` ficam: são dele).
2. Perfil por modo: no modo freelas com nicho o perfil abre pelo nicho e vira `cacada/perfil-freelas.md`; o modo vaga continua full stack em `cacada/perfil.md`.
3. Vigia de freelas: `whis vigia-freelas` e a tarefa `Whis-Vigia-Freelas`, várias vezes por dia, leem a primeira página da 99Freelas e a API pública do Freelancer.com, filtram o nicho em Python (sem Claude), guardam o que já avisaram e soltam um toast com o link do projeto novo. Não é o **Vigia** (`Whis-Vigia`), que confere se as tarefas do Whis subiram.
4. Funil: a caçada lê as propostas de freela mandadas (as notas com `status: enviada…`) e, pelo Chrome da caçada, o que os sites mostram delas; o relatório ganha a seção *Funil* com mandadas, respondidas e fechadas por semana.
5. `[cacada].piso_freela` (R$; 0 = sem piso): a caçada nunca sugere preço abaixo dele.

## Costuras testadas

- `criterios_de_freelas(..., nicho=)` → o pedido e as fontes do modo.
- `cacar()` com as portas fake → vereditos, perfil e relatório (é como os testes da caçada já provam tudo).
- `carregar()` → as chaves novas do `config.toml`.
- `vigiar(...)` com leitor, estado e aviso injetados → quem é avisado; `agendar_vigia_de_freelas(..., executar=)` → o comando do Agendador.
- `ler_mandadas(vault)` e `montar_funil(...)` com uma `SessaoLogada` fake sobre as fixtures de `tests/fixtures/cacada_logada/`.

## Pronto quando

`whis hunt --simular --freelas` com `nicho_freela = "shopify"` mostra que só o nicho pode ser chance boa, e `whis vigia-freelas --fakes` roda uma vez e avisa um projeto falso.
