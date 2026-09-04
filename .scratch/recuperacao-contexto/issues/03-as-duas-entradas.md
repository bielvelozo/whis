# 03 — As duas entradas

**What to build:** `second-brain perguntar "..."` e `second-brain chat`, sobre a mesma costura.
As duas na mesma camada, escolha do usuário em 2026-09-04.

Contrato: **[contrato-busca.md](../contrato-busca.md)**, seção 5.

**Blocked by:** 01

**Status:** blocked

- [ ] `perguntar "TEXTO"`: responde, imprime as citações e sai
- [ ] `chat`: conversa no terminal, mantendo o fio entre perguntas, com saída limpa (`sair`,
      Ctrl+C e EOF), sem deixar o terminal quebrado
- [ ] `--fakes` nas duas, como todo comando deste repo
- [ ] As citações aparecem de um jeito que dá para abrir o arquivo: caminho relativo ao vault
- [ ] Escrita em `notas/` **só sob pedido explícito** na conversa, por `vault.escrever` com
      `zonas=(PASTA_NOTAS,)`; nunca por iniciativa própria
- [ ] Testes pela costura da CLI (`main([...])`), lendo o que sai no terminal
- [ ] O chat é testado sem terminal de verdade — a entrada é injetada
- [ ] Suíte verde, sem editar teste existente

## Notas para o executor

- `forcar_utf8_na_saida()` vale aqui também: acento em pipe no Windows derruba comando.
- O chat guarda o fio **em memória**, não em arquivo: sessão que acaba não deixa estado escondido,
  no mesmo espírito da âncora da daily morar no frontmatter.
- Não invente formatação rica no terminal. O que importa é a resposta e o caminho do arquivo.
