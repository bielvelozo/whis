Status: resolved

# Agências Shopify do Brasil, uma vez por mês

`whis agencias` pede ao Claude (busca e leitura na web, nada mais) agências e estúdios Shopify brasileiros que ainda não estão em `cacada/agencias-shopify.md` nem em `cacada/agencias-shopify-novas.md`, com site, prova (lojas feitas) e contato público da empresa (nunca e-mail com nome de pessoa). Acrescenta uma seção do mês em `cacada/agencias-shopify-novas.md`. Só uma vez por mês (estado em `%LOCALAPPDATA%\whis\cacada\agencias.json`), a não ser com `--forcar`; `--fakes` não usa o Claude. A caçada de freelas, terminada inteira, roda a do mês se ainda não rodou. Nunca contata ninguém.

## Comments

Feito em 2026-10-17 (test_agencias.py), sem rodar o Claude de verdade (a caçada usava o plano). `whis agencias --fakes` só mostra o caminho. A primeira busca real acontece no fim da próxima caçada de freelas inteira, ou com `whis agencias`.
