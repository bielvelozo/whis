# Trabalho deferido — fontes passivas

Achados fora do escopo do ticket em que apareceram. Uma linha por achado:
o quê, onde, por que ficou de fora, de qual camada veio.

- **`--simular` não mostra o que o filtro removeu, só quantos** — `__main__._relatar_diario`. Mostrar os títulos excluídos ajudaria a depurar um padrão que casa demais, mas imprimir o que o filtro prometeu esconder é decisão de privacidade, não de código. Camada 01.
- **O diário não é linkado de volta pela nota de reunião** — `vault.montar_nota`. O diário linka a reunião, mas não o contrário; fechar o ciclo mexeria na nota de reunião, que é do pipeline do tracer bullet. Camada 01.
- **`reunioes_na_janela` relê a pasta inteira a cada execução** — `vault.reunioes_na_janela`. Irrelevante hoje (dezenas de arquivos), viraria varredura cara num vault de anos. Camada 01.
- **Nada distingue "fonte lida com zero eventos" de "fonte lida com tudo filtrado"** — `diario.gerar_diario`. Um dia inteiro removido pelo filtro aparece na nota como `_(nada registrado)_`, igual a um dia sem trabalho; `excluidos` existe no resultado mas não vai à nota. Decidir se vai é decisão de privacidade. Camada 01.
- **A nota de reunião e o diário duplicam a montagem de frontmatter e listas** — `vault.py`. Hoje são três funções `montar_*` compartilhando `_frontmatter`/`_lista`; um formatador comum só se paga se aparecer um quarto tipo de nota. Camada 01.
