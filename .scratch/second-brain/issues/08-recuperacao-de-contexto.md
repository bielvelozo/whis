# Como o agente recupera contexto

Type: grilling
Status: resolved
Blocked by: 07

## Question

Como o agente "lembra" — dado o vault estruturado, como uma pergunta do usuário vira busca e resposta com contexto?

Decidir, sabendo a [estrutura do vault](07-estrutura-vault-obsidian.md):

- Busca simples (grep/links/tags do Obsidian) vs. índice semântico/RAG — o que o tamanho real do vault justifica no início.
- Se RAG: embeddings de quê, reindexação quando, onde roda (sem GPU dedicada).
- Não faz parte do tracer bullet — mas a decisão fecha antes do handoff da spec, para a estrutura do vault não inviabilizar a recuperação depois.

## Answer

Decidido pelo usuário em 2026-08-14:

- **Mecanismo: busca agêntica pura na v1** — o agente (Claude Agent SDK) com `cwd` no vault, recuperando via grep/listagem/leitura guiadas pela estrutura já decidida (nomes datados, pastas por fonte, frontmatter, wikilinks). Zero infraestrutura de índice. A conta que sustenta: ~20 reuniões + ~20 diários/mês ≈ 500 notas/ano — trivial para busca agêntica.
- **Gatilho de reavaliação registrado**: índice semântico/RAG volta à mesa se o vault passar de ~2.000 notas ou se buscas conceituais falharem recorrentemente na prática. Se voltar: embeddings locais em CPU (ex.: sqlite-vec) — sem GPU dedicada, nada de modelos pesados locais.
- **Entrada: chat + one-shot** — sessão de conversa no terminal e comando único (`brain "o que ficou decidido com fulano?"`), mesmo código, dois pontos de entrada.
- **Escrita durante conversa**: o agente lê tudo; escreve livremente nas zonas dele (`reunioes/`, `transcricoes/`, `diario/`) e **pode escrever em `notas/` apenas sob pedido explícito do usuário** — refinamento da zona de propriedade de [Estrutura do vault Obsidian](07-estrutura-vault-obsidian.md): a proibição é de edição *por iniciativa própria*, não de edição sob comando.
