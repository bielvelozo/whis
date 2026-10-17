# 04 — O check na página e a leitura do banco

Type: task
Status: resolved
Blocked by: 01, 03

Camada 3 da [spec](../spec.md#camada-3--o-check-na-página-e-a-leitura-do-banco-pagina_do_jornalpy-marcacoes_claudepy-novo-jornalpy).

- Os dois pedidos de publicação passam a declarar `capabilities` como a sonda provou.
- Página: botão "Li esta aula" por aula, `window.claude?.use("db")`; `null`, ausência ou rejeição
  apagam o botão com a frase; escrita em `leituras/<id>`; erro volta o botão. Conteúdo inteiro sem
  script.
- `PortaMarcacoes` + `MarcacoesClaude` (Haiku, `ArtifactData`, CLI de `caminho_do_cli`): as duas
  coleções inteiras, seguindo o cursor; o Python lê o resultado no formato das fixtures do ticket
  01; página não lida ou ilegível → `ErroDeMarcacoes`; coleção nunca escrita e banco ainda não
  declarado (primeiro dia) contam como vazios.
- `--simular` lê e usa na memória, sem escrever.
- Sincronização pendente → lida (não em `--simular`); falha vira aviso e nada avança.
- `MarcacoesFake` para `--fakes`.

## Comments

- 2026-10-06 — Resolvido. Tarefas 6–8. Pedidos de publicação com `capabilities exatamente {"db": {}}`, botão "Li esta aula" e o script da página, `marcacoes_claude.py` lendo o texto do resultado da `ArtifactData` com `query` filtrada e cursor, sincronização pendente → lida. Testes: `test_marcacoes_claude` (fixtures reais da sonda) e os de marcações em `test_jornal`. A gravação pela página no claude.ai fica para o ticket 08.
- 2026-10-06 — Sonda complementar: `query` sem resultado e em coleção nunca escrita devolvem o mesmo vazio do `list` (fixtures novas, teste em `test_marcacoes_claude`); filtro só com a data funciona.
- 2026-10-08 — A edição das 08:20 não leu as marcas dele ("Não consegui ler o que você marcou"): leitura gravada pela página vem com `<artifact-content-authored-by-others/>` e um aviso antes da contagem, e o leitor exigia a contagem no começo. Corrigido em `marcacoes_claude.py` (cabeçalho procurado por linha); fixture real `leituras-gravadas-pela-pagina.txt` e teste de regressão. Laço real contra a página dele: as três aulas de 07/10 lidas.
