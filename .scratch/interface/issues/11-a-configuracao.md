# 11 — Camada 4: o painel de configuração

Type: task
Status: claimed
Blocked by: 10

**What to build:** uma tela com todas as chaves do `config.toml`, segredos inclusive, e um escritor
de TOML nosso que regenera o arquivo a partir do `MODELO_DE_CONFIGURACAO`, com backup.

Spec: [../spec.md](../spec.md), *A configuração*. Fatos: [research/05](../research/05-janela-local-e-launcher.md) §2.1 e §4.

- [ ] `configuracao.escrever(configuracao, destino)`: gera o texto a partir do modelo (que já
      carrega o comentário de cada chave), escapando strings e caminhos; **backup**
      `config.toml.bak-YYYYMMDD-HHMMSS` antes de cada escrita; UTF-8 sem BOM.
- [ ] Ida e volta provada: escreve → `tomllib` relê → `carregar` devolve a mesma `Configuracao`;
      mais um caso com valor que precisa de escape (aspas, barra invertida, acento).
- [ ] Painel Tk aberto por `configurar` na palheta: uma linha por chave, `Entry(show="•")` para
      os cinco segredos, seletor de pasta para `vault`, `gravacoes`, `[git].raiz`, listas como
      texto multilinha, validação com as mesmas mensagens de `configuracao`. O valor vai do
      teclado ao arquivo sem passar por modelo nenhum.
- [ ] Salvar recarrega a configuração dos processos residentes onde for barato; onde não for, a
      tela diz que precisa reiniciar a bandeja.
- [ ] Suíte inteira verde; o painel testado por porta injetada.

## Notas para o executor

- Nenhuma dependência nova (`tomli_w`, `tomlkit`, `toml` estão fora). Preço aceito: comentário
  escrito à mão no arquivo se perde — o backup guarda.
- As chaves são as do `MODELO_DE_CONFIGURACAO` no momento desta camada (com a tabela de
  horários da camada 2).
