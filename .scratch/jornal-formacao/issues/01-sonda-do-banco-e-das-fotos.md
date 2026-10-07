# 01 — Sonda: o banco do artifact em headless e as fotos das fontes

Type: research
Status: resolved
Blocked by: —

## Question

Camada 0 da [spec](../spec.md#camada-0--sonda-portão-das-demais). Tudo num **artifact de
rascunho novo**, nunca no do jornal, na montagem exata dos adaptadores do jornal (`.venv` do repo,
`dontAsk`, **o CLI que `caminho_do_cli` escolhe**, hoje o do npm, `CLAUDE_CODE_ARTIFACT=1`,
`haiku`). Anotar a versão do CLI e o `init.tools` de cada sessão.

1. Rascunho nasce sem `capabilities` e é republicado com `{"db": {}}`: passa em `dontAsk`?
   Precisa de `user: {}`? Republicar sem e com a declaração mantém o banco declarado?
2. Sessão com `tools=["ArtifactData"]`: `set` e `list` em `leituras` e `respostas`. Formato exato
   do resultado (texto da ferramenta ou JSON em disco), documentos por página e o cursor. Fixtures:
   coleção que nunca recebeu escrita, coleção com uma linha, resultado com cursor.
3. As linhas sobrevivem a um republish com HTML novo?
4. Uma página com `claude.use("db")` grava e a sessão headless lê. Quando aparece o pedido de
   permissão, e como chega a negação (`null` ou rejeição)? Pelo navegador embutido se o claude.ai
   estiver logado nele; senão, anotar como primeiro passo do gate (ticket 08).
5. Custo e tempo de uma leitura das duas coleções, frio e quente.
6. Fotos: 12 URLs reais de fonte das notas e da trilha (Wikipédia e outras). Quantas têm
   `og:image`/`twitter:image` que a `_baixar_imagem` atual baixa? A da Wikipédia é a do assunto?
7. SVG inline aparece no app do celular sem CSP?

Achados em `research/00-banco-e-fotos.md`; scripts descartáveis em `research/00-banco-e-fotos/`.
Se 2 ou 4 falharem, parar e voltar para ele com a alternativa B (página que se republica com o
estado embutido).

## Answer

Resolvido em 2026-10-06. Achados em [research/00-banco-e-fotos.md](../research/00-banco-e-fotos.md);
saídas brutas em `research/00-banco-e-fotos/saida/`; fixtures reais em
`tests/fixtures/jornal/marcacoes/`. Rascunho: `https://claude.ai/artifact/4v1HQhbRMFyfUAetDk7PvT`.

- **1:** `{"db": {}}` por republish passa em `dontAsk`, sem `user`; republicar sem ou com a
  declaração mantém o banco.
- **2 (portão): passou.** Leitura headless funciona com `tools=["Artifact", "ArtifactData"]` (só
  `ArtifactData` nasce sem ferramenta). `out_dir` e qualquer escrita são negados em `dontAsk`: o
  Python lê o texto do resultado (linhas JSON entre marcadores, `next_cursor` numa linha). `query`
  com `where` funciona.
- **3:** as linhas sobrevivem ao republish.
- **4 (portão): não falhou, ficou sem prova.** O navegador embutido não está logado no claude.ai;
  a gravação pela página vira o passo 1 do ticket 08, como a spec previa.
- **5:** leitura US$ 0,010–0,014, 7–10 s (quente); US$ 0,038 frio.
- **6:** Wikipédia exige o `UA_WIKIPEDIA` (403 com o UA de navegador); com ele, 6 de 6 deram a foto
  do assunto. Fora da Wikipédia, `og:image` às vezes é só logo.
- **7:** SVG inline aceito no publish e renderizado na página local; no celular, ticket 08.

## Comments

- 2026-10-06 — Spec (camada 3, *Leitura*) e plano (tarefa 7) revistos com os achados.
