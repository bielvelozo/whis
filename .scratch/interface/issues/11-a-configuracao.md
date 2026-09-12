# 11 — Camada 4: o painel de configuração

Type: task
Status: resolved
Blocked by: 10

**What to build:** uma tela com todas as chaves do `config.toml`, segredos inclusive, e um escritor
de TOML nosso que regenera o arquivo a partir do `MODELO_DE_CONFIGURACAO`, com backup.

Spec: [../spec.md](../spec.md), *A configuração*. Fatos: [research/05](../research/05-janela-local-e-launcher.md) §2.1 e §4.

- [x] `configuracao.escrever(configuracao, destino)`: gera o texto a partir do modelo (que já
      carrega o comentário de cada chave), escapando strings e caminhos; **backup**
      `config.toml.bak-YYYYMMDD-HHMMSS` antes de cada escrita; UTF-8 sem BOM.
- [x] Ida e volta provada: escreve → `tomllib` relê → `carregar` devolve a mesma `Configuracao`;
      mais um caso com valor que precisa de escape (aspas, barra invertida, acento).
- [x] Painel Tk aberto por `configurar` na palheta: uma linha por chave, `Entry(show="•")` para
      os cinco segredos, seletor de pasta para `vault`, `gravacoes`, `[git].raiz`, listas como
      texto multilinha, validação com as mesmas mensagens de `configuracao`. O valor vai do
      teclado ao arquivo sem passar por modelo nenhum.
- [x] Salvar recarrega a configuração dos processos residentes onde for barato; onde não for, a
      tela diz que precisa reiniciar a bandeja.
- [x] Suíte inteira verde; o painel testado por porta injetada.

## Notas para o executor

- Nenhuma dependência nova (`tomli_w`, `tomlkit`, `toml` estão fora). Preço aceito: comentário
  escrito à mão no arquivo se perde — o backup guarda.
- As chaves são as do `MODELO_DE_CONFIGURACAO` no momento desta camada (com a tabela de
  horários da camada 2).

## Comments

**Camada 4 entregue e fechada** (2026-09-12; executor `palheta`, revisão e gate na sessão principal).

- `configuracao.py`: `MODELO_DE_CONFIGURACAO` mudou-se para cá (reexportado em `__main__`), `CHAVES`
  (27 chaves: o contrato entre modelo, escritor e painel), `gerar_toml` regenerando do modelo linha a
  linha com o comentário preservado, `escrever` com `.tmp` → `carregar` → backup
  `config.toml.bak-YYYYMMDD-HHMMSS` → `os.replace`; UTF-8 sem BOM; nenhum valor logado.
- `painel.py`: `CAMPOS` derivado do modelo, `Painel` com porta `PortaFormulario`, `FormularioTk`
  (segredos com `show="•"` e botão Mostrar, seletor de pasta, listas multilinha, sete campos de
  horário); salvar recarrega a configuração da palheta e avisa que a bandeja precisa reiniciar para
  áudio, atalho e caminhos. Abre por `configurar` e pelo menu da bandeja.
- Executor provou o `FormularioTk` de verdade: máscara, pasta, erro de `retencao_dias = "sete"` mostrado
  sem escrever, backup criado ao salvar.
- Suíte: **1048 verdes** (eram 1021), 8 desselecionados; nenhum teste existente editado.
- Fica para o usuário (roteiro `docs/smoke-interface.md`, passo 2): preencher `horarios`, o ID do
  vault, tirar `second-brain` de `referencias_pessoais` e, se quiser, a pasta privada.
