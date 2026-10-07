# 02 — Imagem nas aulas: foto da fonte ou esquema do Claude

Type: task
Status: resolved
Blocked by: 01

Camada 1 da [spec](../spec.md#camada-1--imagem-nas-aulas-jornal_claudepy-jornalpy-pagina_do_jornalpy-vaultpy).

- `_AULA` com `visual`, `foto_de`, `esquema`; regra no `SISTEMA_FORMACAO`.
- `Aula` com `visual`, `foto_de`, `esquema`, `foto`, `imagem`.
- Foto pelo `og:image`/`twitter:image` de `foto_de` (só se estiver em `fontes`), baixada pela
  `_baixar_imagem` para `img/aula-<id>.jpg` e posta no mapa `files`.
- Esquema SVG sanitizado por lista fechada (elementos, atributos, 30 KB), inline na página.
- Página: figura no topo do cartão; nota: `![](<URL>)` para foto.
- Testes da seção *Testing Decisions* que tocam imagem. Uma `--simular` medindo o custo a mais.

## Comments

- 2026-10-06 — Resolvido. Tarefas 1–3. `esquema.py` (lista fechada, 30 KB), `fotos_das_aulas.py` (`og:image`/`twitter:image`), `_figura` em `jornal_claude.py`, `achar_fotos`/`baixar_fotos_das_aulas` com `UA_WIKIPEDIA` para a Wikipédia, figura na página e na nota. Testes: `test_esquema`, `test_fotos_das_aulas`, figura em `test_jornal_claude` e `test_jornal`. `news --simular` real (2026-10-06 22:00): 3 aulas, 2 esquemas aceitos e 1 foto (Honda N-Box para a aula de kei car); formação US$ 0,40 contra US$ 0,30 sem figura.
- 2026-10-06 — Depois da simulação ele pediu: carro sempre com foto (o esquema de downforce desenhava um carro com linhas). `_figura_de_carro` força `visual: foto` com a página da Wikipédia das fontes; prompt diz "Nunca desenhe carro"; esquema só em negócios. Testes em `test_jornal_claude`.
