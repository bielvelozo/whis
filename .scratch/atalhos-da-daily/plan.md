# Atalhos da daily — plano de implementação

> Para quem executa: siga as tarefas na ordem, com testes primeiro. Os passos usam caixas
> (`- [ ]`) para acompanhar.

**Objetivo:** `did`, `doing` e `done` na palheta, e *O que terminei* fora da nota e do deck
(spec: `.scratch/atalhos-da-daily/spec.md`).

**Arquitetura:** `nota_viva.py` ganha `Item`, `itens` e `concluir` (o mover de `928a7c0` sem os
ids por hash, com a régua de elos da spec); `vault.concluir_item` lê, move e grava literal;
`palheta.py` ganha `ListaDoFazendo` (uma `Lista` com um `Gesto` de Enter que não esconde) e os
três `Comando`s.

**Ferramentas:** Python 3.12, pytest, Tk só no teste da janela de verdade.

**Comandos** (Git Bash, da raiz do repositório):

- um arquivo: `.venv/Scripts/python.exe -m pytest -o addopts="" tests/test_nota_viva.py -q`
- a suíte: `.venv/Scripts/python.exe -m pytest -o addopts="" -m "not rede" -q` (1109 verdes em
  `d43f6b9`; o teste do Tk de verdade pode falhar por foco com a máquina em uso: rode isolado
  antes de culpar o código).

Mensagens de commit sem acento, como as do histórico.

---

### Tarefa 1: *O que terminei* sai

**Arquivos:** `src/whis/nota_viva.py`, `src/whis/deck.py`, `src/whis/palheta.py`,
`tests/test_nota_viva.py`, `tests/test_deck.py`, `tests/test_daily.py`, `tests/fixtures/daily.py`.

- [ ] **Testes primeiro.**
  - `test_nota_viva.py`: tirar `SECAO_TERMINEI` do import. `test_garantir_secao_…` passa a usar
    `SECAO_FAZER` (a `NOTA` não tem *Fazer*):
    ```python
    assert nota.garantir_secao(SECAO_FAZER) is True
    assert nota.garantir_secao(SECAO_FAZER) is False
    texto = nota.texto()
    assert texto.count("## Fazer") == 1
    assert texto.replace("## Fazer\n\n", "", 1) == NOTA
    assert texto.index("## O que estou fazendo") < texto.index("## Fazer") < texto.index("## Dúvidas")
    ```
    O teste do modelo vira `test_o_modelo_tem_as_seis_secoes_…`, com a lista sem
    `SECAO_TERMINEI`. Teste novo:
    ```python
    def test_o_que_terminei_antiga_fica_intocada_e_nao_e_mais_secao():
        antiga = NOTA.replace("## Dúvidas\n", "## O que terminei\n\n- entregue\n\n## Dúvidas\n", 1)
        nota = NotaViva.de_texto(antiga)

        assert nota.texto() == antiga
        assert "O que terminei" not in [secao for secao, _ in nota.secoes()]
    ```
  - `test_deck.py`: na `NOTA`, `"## O que terminei\n\n"` vira
    `"## O que terminei\n\n- entregue na semana passada\n\n"`; `test_nota_sem_o_que_terminei_…`
    vira:
    ```python
    def test_o_que_terminei_antiga_nao_vira_slide():
        textos = [item.texto for slide in montar_deck(NotaViva.de_texto(NOTA)).slides for item in slide.itens]

        assert "entregue na semana passada" not in textos
    ```
  - `test_daily.py`: em `test_a_copia_tem_so_…` a tupla vira `("## Pontos", "## Fazer")`;
    `test_nota_sem_o_que_terminei_ganha_o_titulo_…` vira:
    ```python
    def test_a_nota_com_as_quatro_secoes_do_deck_sai_byte_a_byte_igual(configuracao, caminho_do_vault: Path, tmp_path: Path):
        arquivo = escrever_nota_da_daily(caminho_do_vault)

        gerar(configuracao, PublicacaoDoDeckFake(), tmp_path)
        gerar(configuracao, PublicacaoDoDeckFake(), tmp_path)

        assert arquivo.read_bytes().decode("utf-8") == NOTA_DA_DAILY
    ```
    Em `test_nota_sem_as_secoes_do_deck_…`, a tupla de títulos perde `"O que terminei"`, a ordem
    checada é `## O que eu fiz` < `## O que estou fazendo` < `## Dúvidas`, e entra
    `assert "## O que terminei" not in texto`. Em `test_nota_vazia_…`, a última linha vira
    `assert "## O que estou fazendo" in arquivo.read_text(encoding="utf-8")`.
  - `fixtures/daily.py`: docstring `"""A nota da daily como ele a escreve no Obsidian."""`.
- [ ] **Rodar e ver falhar** (`test_nota_viva`, `test_deck`, `test_daily`).
- [ ] **Código.** `nota_viva.py`: sai `SECAO_TERMINEI`, a entrada em `SECOES` e
  `## O que terminei\n\n` do `MODELO_DA_NOTA_VIVA`. `deck.py`: sai o import e
  `(SECAO_TERMINEI, "terminei")`. `palheta.py`, toast da daily vazia:
  `"Escreva o que fez e está fazendo, e gere de novo."`.
- [ ] **Rodar e ver passar**, e `grep -rn "TERMINEI\|O que terminei" src tests` sem sobra.
- [ ] **Commit:** `Sai O que terminei: redundante com O que eu fiz; a nota volta a seis secoes e o deck a quatro slides`.

### Tarefa 2: anotar em *O que eu fiz* e *O que estou fazendo*

**Arquivos:** `src/whis/nota_viva.py`, `tests/test_nota_viva.py`.

- [ ] **Testes primeiro.** `test_anotar_em_duvidas_so_a_pedido_e_nunca_…` vira:
  ```python
  def test_anotar_em_duvidas_e_nunca_em_falar():
      nota = NotaViva.de_texto(NOTA)

      nota.anotar("o pix expira?", SECAO_DUVIDAS)

      assert "- o pix pendente expira sozinho?\n- o pix expira?\n" in trecho(nota.texto(), SECAO_DUVIDAS)
      with pytest.raises(ValueError):
          nota.anotar("x", SECAO_FALAR)


  def test_anotar_em_fiz_e_fazendo_entra_sem_caixa_no_fim_da_secao():
      nota = NotaViva.de_texto(NOTA)

      assert nota.anotar("subi o pix", SECAO_FIZ) == "- subi o pix"
      assert nota.anotar("revisando o checkout", SECAO_FAZENDO) == "- revisando o checkout"

      texto = nota.texto()
      assert "1. Planejei e ativei o pix transparente da AppMax no checkout\n- subi o pix\n\n## O que estou fazendo\n" in texto
      assert "2. Testando no android  \n- revisando o checkout\n\n\t   \n" in texto
  ```
- [ ] **Rodar e ver falhar** (`ValueError` em *fiz*).
- [ ] **Código.** `SECOES_ANOTAVEIS = (SECAO_FIZ, SECAO_FAZENDO, SECAO_PONTOS, SECAO_DUVIDAS, SECAO_FAZER)`;
  docstring de `anotar`: "`- texto` no fim de uma seção que tem comando (`did`, `doing`, `note`,
  `doubt`, `do`), a pedido dele." (o resto fica).
- [ ] **Rodar e ver passar.**

### Tarefa 3: `NotaViva.itens` e `NotaViva.concluir`

**Arquivos:** `src/whis/nota_viva.py`, `tests/test_nota_viva.py`.

- [ ] **Testes primeiro.** Nova seção `# -- concluir` com a nota:
  ```python
  #: *O que estou fazendo* com sub-item, linha em branco e embed dentro da subárvore,
  #: espaço à direita e o item vazio que o Obsidian deixa.
  FAZENDO = (
      "---\n"
      "tipo: daily-atual\n"
      "---\n"
      "\n"
      "## O que eu fiz\n"
      "\n"
      "- já estava aqui\n"
      "\n"
      "## O que estou fazendo\n"
      "\n"
      "- FN-1786 foto extra \n"
      "\t- revisar o hub\n"
      "\n"
      "\t\t![[print.png]]\n"
      "- Achados do ribeiro\n"
      "\t- Problema A\n"
      "\t- Problema B\n"
      "- \n"
      "\n"
      "## Dúvidas\n"
      "\n"
      "- o pix expira?\n"
  )
  BLOCO_DA_FOTO = "- FN-1786 foto extra \n\t- revisar o hub\n\n\t\t![[print.png]]\n"


  def item(nota: NotaViva, texto: str):
      return next(candidato for candidato in nota.itens(SECAO_FAZENDO) if candidato.texto == texto)


  def concluir(nota: NotaViva, *textos: str) -> None:
      for texto in textos:
          alvo = item(nota, texto)
          assert nota.concluir(alvo.inicio, alvo.linha) is not None
  ```
  e os testes:
  ```python
  def test_itens_trazem_a_subarvore_literal_e_os_pais_sem_o_item_vazio():
      itens = NotaViva.de_texto(FAZENDO).itens(SECAO_FAZENDO)

      assert [i.texto for i in itens] == [
          "FN-1786 foto extra", "revisar o hub", "Achados do ribeiro", "Problema A", "Problema B",
      ]
      foto, hub, achados, problema_a, _ = itens
      assert foto.linhas == ("- FN-1786 foto extra ", "\t- revisar o hub", "", "\t\t![[print.png]]")
      assert foto.ancestrais == () and hub.ancestrais == (foto.inicio,)
      assert problema_a.ancestrais == (achados.inicio,)


  def test_concluir_leva_o_item_e_a_subarvore_para_o_fim_de_fiz_e_o_resto_fica_byte_a_byte():
      nota = NotaViva.de_texto(FAZENDO)
      foto = item(nota, "FN-1786 foto extra")

      assert nota.concluir(foto.inicio, foto.linha) == foto.linhas
      assert nota.texto() == FAZENDO.replace(BLOCO_DA_FOTO, "", 1).replace(
          "- já estava aqui\n", "- já estava aqui\n" + BLOCO_DA_FOTO, 1
      )


  def test_concluir_um_sub_item_copia_o_pai_que_fica_em_fazendo():
      nota = NotaViva.de_texto(FAZENDO)
      problema_a = item(nota, "Problema A")

      assert nota.concluir(problema_a.inicio, problema_a.linha) == ("- Achados do ribeiro", "\t- Problema A")
      texto = nota.texto()
      assert "- já estava aqui\n- Achados do ribeiro\n\t- Problema A\n\n## O que estou fazendo\n" in texto
      assert "- Achados do ribeiro\n\t- Problema B\n- \n" in trecho(texto, SECAO_FAZENDO)


  def test_concluir_dois_irmaos_copia_o_pai_uma_vez_so():
      nota = NotaViva.de_texto(FAZENDO)

      concluir(nota, "Problema A", "Problema B")

      assert trecho(nota.texto(), SECAO_FIZ).endswith(
          "- já estava aqui\n- Achados do ribeiro\n\t- Problema A\n\t- Problema B\n"
      )


  def test_concluir_o_pai_depois_dos_filhos_nao_o_repete():
      nota = NotaViva.de_texto(FAZENDO)

      concluir(nota, "Problema A", "Problema B", "Achados do ribeiro")

      texto = nota.texto()
      assert trecho(texto, SECAO_FIZ).count("- Achados do ribeiro") == 1
      assert "Achados" not in trecho(texto, SECAO_FAZENDO)


  def test_o_pai_nao_casa_com_o_mesmo_texto_em_outra_profundidade_de_fiz():
      nota = NotaViva.de_texto(FAZENDO.replace("- já estava aqui\n", "- já estava aqui\n\t- Achados do ribeiro\n", 1))

      concluir(nota, "Problema A")

      assert "- já estava aqui\n\t- Achados do ribeiro\n- Achados do ribeiro\n\t- Problema A\n" in nota.texto()


  def test_concluir_sem_fiz_abre_a_secao_no_lugar_dela():
      nota = NotaViva.de_texto(FAZENDO.replace("## O que eu fiz\n\n- já estava aqui\n\n", "", 1))

      concluir(nota, "FN-1786 foto extra")

      assert nota.texto().startswith(
          "---\ntipo: daily-atual\n---\n\n## O que eu fiz\n" + BLOCO_DA_FOTO
          + "\n## O que estou fazendo\n\n- Achados do ribeiro\n"
      )


  def test_concluir_preserva_o_crlf():
      nota = NotaViva.de_texto(FAZENDO.replace("\n", "\r\n"))

      concluir(nota, "FN-1786 foto extra")

      texto = nota.texto()
      assert "\n" not in texto.replace("\r\n", "")
      assert "- já estava aqui\r\n- FN-1786 foto extra \r\n" in texto


  def test_com_a_nota_mudada_acha_pela_linha_unica_ou_nao_mexe():
      achados = item(NotaViva.de_texto(FAZENDO), "Achados do ribeiro")
      topo = "## O que estou fazendo\n\n"

      deslocada = NotaViva.de_texto(FAZENDO.replace(topo, topo + "- novo no topo\n", 1))
      assert deslocada.concluir(achados.inicio, achados.linha) is not None
      assert "- Achados do ribeiro" in trecho(deslocada.texto(), SECAO_FIZ)

      renomeada = FAZENDO.replace("- Achados do ribeiro\n", "- Achados do Ribeiro\n", 1)
      sumida = NotaViva.de_texto(renomeada)
      assert sumida.concluir(achados.inicio, achados.linha) is None
      assert sumida.texto() == renomeada

      repetida = FAZENDO.replace("- \n", "- Achados do ribeiro\n", 1).replace(topo, topo + "- novo\n", 1)
      assert NotaViva.de_texto(repetida).concluir(achados.inicio, achados.linha) is None
  ```
- [ ] **Rodar e ver falhar** (`AttributeError: itens`).
- [ ] **Código** em `nota_viva.py`:
  ```python
  @dataclass(frozen=True)
  class Item:
      """Um item de lista de uma seção, com a subárvore que viaja com ele.

      `linhas` são a linha do item e tudo o que está mais indentado embaixo dela,
      literais, sem as linhas em branco do fim. `inicio` é a posição da linha do
      item no corpo da seção (as linhas sem o título); `ancestrais` são os
      `inicio` dos itens que o contêm, de fora para dentro.
      """

      texto: str
      linhas: tuple[str, ...]
      inicio: int
      ancestrais: tuple[int, ...]

      @property
      def linha(self) -> str:
          return self.linhas[0]

      @property
      def fim(self) -> int:
          return self.inicio + len(self.linhas)
  ```
  Em `NotaViva`:
  ```python
      def itens(self, titulo: str) -> tuple[Item, ...]:
          """Os itens de lista de uma seção, os aninhados inclusive, na ordem da nota."""
          bloco = self._bloco(titulo)
          return _itens(_corpo(bloco)) if bloco else ()

      def concluir(self, posicao: int, linha: str) -> tuple[str, ...] | None:
          """Leva um item de *O que estou fazendo* para *O que eu fiz*, a pedido dele (`done`).

          O item é reencontrado pela linha literal na `posicao` do corpo, ou pela
          linha literal se ela for única na seção: ele pode ter mexido na nota
          desde que a lista foi lida. Sem item, `None` e nada muda. A subárvore
          sai inteira e literal; os pais ficam, e entram em *O que eu fiz* como
          cabeçalho, sem repetir um elo que já esteja lá. Devolve as linhas que
          entraram em *O que eu fiz*.
          """
          item = self._reencontrar(SECAO_FAZENDO, posicao, linha)
          if item is None:
              return None
          por_inicio = {candidato.inicio: candidato for candidato in self.itens(SECAO_FAZENDO)}
          cadeia = (*(por_inicio[inicio] for inicio in item.ancestrais), item)
          origem = self._bloco(SECAO_FAZENDO)
          assert origem is not None
          del origem.linhas[1 + item.inicio : 1 + item.fim]

          entraram, elo = self._garantir_cadeia(SECAO_FIZ, cadeia)
          destino = self._bloco(SECAO_FIZ)
          assert destino is not None
          filhos = list(item.linhas[1:])
          destino.linhas[1 + elo.fim : 1 + elo.fim] = filhos
          return (*entraram, *filhos)

      def _reencontrar(self, titulo: str, posicao: int, linha: str) -> Item | None:
          itens = self.itens(titulo)
          no_lugar = next((item for item in itens if item.inicio == posicao and item.linha == linha), None)
          if no_lugar is not None:
              return no_lugar
          iguais = [item for item in itens if item.linha == linha]
          return iguais[0] if len(iguais) == 1 else None

      def _garantir_cadeia(self, titulo: str, cadeia: Sequence[Item]) -> tuple[tuple[str, ...], Item]:
          """Cada elo em `titulo` como filho direto do anterior; o que falta entra com a linha literal.

          Devolve as linhas que entraram e o último elo como está na seção.
          """
          bloco = self._bloco(titulo) or self._abrir_secao(titulo)
          entraram: list[str] = []
          pai: Item | None = None
          for elo in cadeia:
              existente = self._filho(titulo, pai, elo.texto)
              if existente is None:
                  posicao = pai.fim if pai else _fim_do_conteudo(_corpo(bloco))
                  bloco.linhas.insert(1 + posicao, elo.linha)
                  entraram.append(elo.linha)
                  existente = next(item for item in self.itens(titulo) if item.inicio == posicao)
              pai = existente
          assert pai is not None
          return tuple(entraram), pai

      def _filho(self, titulo: str, pai: Item | None, texto: str) -> Item | None:
          """O item de `texto` filho direto de `pai`, ou de nível raiz sem pai."""
          esperado = (pai.inicio,) if pai else ()
          return next(
              (item for item in self.itens(titulo) if item.texto == texto and item.ancestrais[-1:] == esperado),
              None,
          )
  ```
  Funções do módulo:
  ```python
  def _itens(corpo: Sequence[str]) -> tuple[Item, ...]:
      itens: list[Item] = []
      abertos: list[tuple[int, int]] = []
      for indice, linha in enumerate(corpo):
          if not linha.strip():
              continue
          nivel = _nivel(linha)
          while abertos and abertos[-1][0] >= nivel:
              abertos.pop()
          partes = _ITEM.match(linha)
          if partes is None or not partes["texto"].strip():
              continue
          fim = _fim_da_subarvore(corpo, indice, nivel)
          ancestrais = tuple(inicio for _, inicio in abertos)
          itens.append(Item(partes["texto"].strip(), tuple(corpo[indice:fim]), indice, ancestrais))
          abertos.append((nivel, indice))
      return tuple(itens)


  def _fim_da_subarvore(corpo: Sequence[str], inicio: int, nivel: int) -> int:
      """Onde acaba o que pertence ao item: a última linha mais indentada que ele."""
      fim = inicio + 1
      for indice in range(inicio + 1, len(corpo)):
          linha = corpo[indice]
          if not linha.strip():
              continue
          if _nivel(linha) <= nivel:
              break
          fim = indice + 1
      return fim


  def contem(texto: str, busca: str) -> bool:
      """`busca` aparece em `texto`, sem diferenciar maiúscula nem acento."""
      return _chave(busca) in _chave(texto)
  ```
- [ ] **Rodar e ver passar.**

### Tarefa 4: `vault.concluir_item` e `ListaDoFazendo`

**Arquivos:** `src/whis/vault.py`, `src/whis/palheta.py`, `tests/test_palheta.py`.

- [ ] **Testes primeiro**, em `test_palheta.py`, seção `# -- done`. Imports novos:
  `from whis.janela_da_palheta import Efeito, Linha` e `ListaDoFazendo` de `whis.palheta`.
  ```python
  NOTA_DO_DONE = (
      "---\ntipo: daily-atual\n---\n\n"
      "## O que eu fiz\n\n- já estava aqui\n\n"
      "## O que estou fazendo\n\n"
      "- Revisão do checkout\n"
      "\t- botão do pix\n"
      "- Ajustes do flywheel\n"
      "\n## Falar\n\n- sexta saio cedo\n"
  )


  @pytest.fixture
  def lista_do_fazendo(configuracao_do_diario, caminho_do_vault: Path) -> ListaDoFazendo:
      escrever_nota_da_daily(caminho_do_vault, NOTA_DO_DONE)
      return ListaDoFazendo(configuracao_do_diario())


  def nota_viva_de(vault: Path) -> str:
      return (vault / "daily" / "atual.md").read_bytes().decode("utf-8")


  def test_a_lista_do_done_mostra_os_itens_de_fazendo_com_o_caminho_dos_pais(lista_do_fazendo):
      assert lista_do_fazendo.linhas("") == [
          Linha("◔", "Revisão do checkout"),
          Linha("◔", "botão do pix", "em: Revisão do checkout"),
          Linha("◔", "Ajustes do flywheel"),
      ]
      assert lista_do_fazendo.detalhe(0) == "- Revisão do checkout\n\t- botão do pix"
      assert lista_do_fazendo.nome == "Done"
      assert [gesto.tecla for gesto in lista_do_fazendo.gestos] == ["<Return>"]


  def test_a_lista_do_done_filtra_sem_acento_nem_maiuscula(lista_do_fazendo):
      assert [linha.titulo for linha in lista_do_fazendo.linhas("REVISAO")] == ["Revisão do checkout"]
      assert lista_do_fazendo.linhas("vagas") == [] and lista_do_fazendo.vazia == "No item matches"


  def test_enter_move_para_fiz_e_a_lista_fica_aberta_sem_o_item(lista_do_fazendo, caminho_do_vault: Path):
      lista_do_fazendo.linhas("")
      [enter] = lista_do_fazendo.gestos

      efeito = enter.rodar(2, "")

      assert not enter.esconde
      assert efeito == Efeito(mensagem="Moved: Ajustes do flywheel")
      assert "- já estava aqui\n- Ajustes do flywheel\n\n## O que estou fazendo\n" in nota_viva_de(caminho_do_vault)
      assert [linha.titulo for linha in lista_do_fazendo.linhas("")] == ["Revisão do checkout", "botão do pix"]


  def test_enter_numa_busca_move_o_item_filtrado(lista_do_fazendo, caminho_do_vault: Path):
      lista_do_fazendo.linhas("pix")

      lista_do_fazendo.gestos[0].rodar(0, "pix")

      assert "- já estava aqui\n- Revisão do checkout\n\t- botão do pix\n" in nota_viva_de(caminho_do_vault)


  def test_a_nota_mudada_entre_ler_e_mover_nao_mexe_e_avisa_no_rodape(lista_do_fazendo, caminho_do_vault: Path):
      lista_do_fazendo.linhas("")
      mudada = NOTA_DO_DONE.replace("- Ajustes do flywheel\n", "- Ajustes do flywheel v2\n")
      escrever_nota_da_daily(caminho_do_vault, mudada)

      efeito = lista_do_fazendo.gestos[0].rodar(2, "")

      assert efeito == Efeito(mensagem="The note changed — try again")
      assert nota_viva_de(caminho_do_vault) == mudada


  def test_sem_selecao_o_enter_nao_faz_nada(lista_do_fazendo, caminho_do_vault: Path):
      lista_do_fazendo.linhas("vagas")

      assert lista_do_fazendo.gestos[0].rodar(None, "vagas") is None
      assert nota_viva_de(caminho_do_vault) == NOTA_DO_DONE


  def test_a_lista_vazia_ensina_o_doing(configuracao_do_diario, caminho_do_vault: Path):
      escrever_nota_da_daily(caminho_do_vault, "---\ntipo: daily-atual\n---\n\n## O que estou fazendo\n\n")
      lista = ListaDoFazendo(configuracao_do_diario())

      assert lista.linhas("") == []
      assert lista.vazia == "Nothing in O que estou fazendo — type: doing <text>"
  ```
- [ ] **Rodar e ver falhar** (`ImportError: ListaDoFazendo`).
- [ ] **Código.** `vault.py` (importa `SECAO_FAZENDO` e `SECAO_FIZ` de `nota_viva`):
  ```python
  def concluir_item(vault: Path, posicao: int, linha: str) -> tuple[str, ...] | None:
      """Leva um item de *O que estou fazendo* para *O que eu fiz* (`done`) e grava literal.

      `None` quando a nota mudou e o item não é mais achado: nada é gravado.
      """
      nota = ler_nota_viva(vault)
      movidas = nota.concluir(posicao, linha)
      if movidas is None:
          _log.info("O item a concluir não está mais em '%s' de %s", SECAO_FAZENDO, CAMINHO_DA_NOTA_VIVA)
          return None
      escrever_nota_viva(vault, nota)
      _log.info("Item levado de '%s' para '%s' em %s", SECAO_FAZENDO, SECAO_FIZ, CAMINHO_DA_NOTA_VIVA)
      return movidas
  ```
  Docstring de `anotar_ponto`: "Acrescenta uma linha no fim de uma seção da nota viva que tem
  comando" e a lista `did`/`doing`/`note`/`doubt`/`do`. `palheta.py` (importa `Item`, `contem`,
  `SECAO_FAZENDO`, `SECAO_FIZ` de `nota_viva`), depois de `ListaDePrompts`:
  ```python
  class ListaDoFazendo:
      """A lista de `done` na janela: os itens de *O que estou fazendo* e o Enter que leva o escolhido para *O que eu fiz*.

      Relê a nota a cada texto digitado, como a dos prompts; depois do Enter a
      janela fica aberta, para ele marcar outro.
      """

      nome = "Done"
      placeholder = f"Search {SECAO_FAZENDO}…"

      def __init__(self, configuracao: Configuracao) -> None:
          self._configuracao = configuracao
          self._todos: tuple[Item, ...] = ()
          self._achados: list[Item] = []
          self.gestos = (Gesto("<Return>", "↵", "Mark done", self._concluir),)

      @property
      def vazia(self) -> str:
          if not self._todos:
              return f"Nothing in {SECAO_FAZENDO} — type: doing <text>"
          return "No item matches"

      def linhas(self, texto: str) -> list[Linha]:
          self._todos = _vault.ler_nota_viva(self._configuracao.vault).itens(SECAO_FAZENDO)
          self._achados = [item for item in self._todos if contem(item.texto, texto)]
          textos = {item.inicio: item.texto for item in self._todos}
          return [
              Linha("◔", item.texto, "em: " + " › ".join(textos[i] for i in item.ancestrais) if item.ancestrais else "")
              for item in self._achados
          ]

      def detalhe(self, indice: int) -> str:
          return "\n".join(self._achados[indice].linhas) if 0 <= indice < len(self._achados) else ""

      def _concluir(self, indice: int | None, _texto: str) -> Efeito | None:
          if indice is None or not 0 <= indice < len(self._achados):
              return None
          item = self._achados[indice]
          if _vault.concluir_item(self._configuracao.vault, item.inicio, item.linha) is None:
              return Efeito(mensagem="The note changed — try again")
          return Efeito(mensagem=f"Moved: {item.texto}")
  ```
- [ ] **Rodar e ver passar.**

### Tarefa 5: `did`, `doing` e `done` na palheta

**Arquivos:** `src/whis/palheta.py`, `tests/test_palheta.py`, `tests/test_prompts.py`.

- [ ] **Testes primeiro.**
  - `COMANDOS` ganha `"did", "doing", "done"`.
  - Teste novo e o `parametrize` de `test_anotar_sem_texto_…` com `"did", "doing"`:
    ```python
    def test_did_e_doing_escrevem_em_fiz_e_fazendo_sem_caixa(montar, caminho_do_vault: Path, aviso):
        palheta = montar()
        escrever_nota_da_daily(caminho_do_vault)

        palheta.despachar("did FN-131 deploy do frete")
        assert aviso.ultimo()[:2] == ("Anotado em O que eu fiz", "FN-131 deploy do frete")
        palheta.despachar("doing FN-140 revisão do checkout")
        titulo, texto, botao = aviso.ultimo()
        assert (titulo, texto) == ("Anotado em O que estou fazendo", "FN-140 revisão do checkout")
        assert botao[1].endswith("&file=daily%2Fatual")

        nota = (caminho_do_vault / "daily" / "atual.md").read_bytes().decode("utf-8")
        assert "\t- subiu em produção\n- FN-131 deploy do frete\n\n## O que estou fazendo\n" in nota
        assert "- FN-130 diário automático\n- FN-140 revisão do checkout\n\n## Fazer\n" in nota


    def test_done_abre_a_lista_e_fora_da_janela_explica(montar, aviso):
        palheta = montar()
        done = next(comando for comando in palheta.comandos if comando.nome == "done")

        assert isinstance(done.lista(palheta.configuracao), ListaDoFazendo)
        assert done.parametro == "search"
        palheta.despachar("done")
        assert aviso.ultimo()[0] == "Done"
    ```
  - `test_sao_os_onze_comandos_…` vira `test_sao_os_catorze_comandos_…`, com
    `acoes()[:5]` rotulados `["Open note", "Generate daily", "Did", "Doing", "Mark done"]`.
  - `ACOES`, depois de `daily`:
    `Acao("did", "✓", "Did", aceita_argumento=True)`, `Acao("doing", "◔", "Doing", aceita_argumento=True)`,
    `Acao("done", "☑", "Mark done", aceita_argumento=True)`.
  - Filtros: `"d"` → `["daily", "did", "doing", "done", "doubt", "do"]`; `"Do"` e `"do"` →
    `["do", "doing", "done", "doubt"]`.
  - Tab: `ACOES[9]` → `"ask "`, `ACOES[10]` → `"note "`, `ACOES[12]` → `"do "`,
    `ACOES[13]` → `"settings"`, e `completar(ACOES[4]) == "done "`.
  - Tk de verdade: `titulos_desenhados()` de `ACOES[:3]` → `["Open note", "Generate daily", "Did"]`
    e `_clicar(2)` envia `"did"`.
  - `test_prompts.py`: `acoes()[4:6]` → `acoes()[7:9]`.
- [ ] **Rodar e ver falhar.**
- [ ] **Código** em `palheta.py`: `ORDEM_DAS_ACOES = ("open", "daily", "did", "doing", "done",
  NOME_DO_JORNAL, NOME_DAS_REUNIOES, "prompts", "stash", "ask", "note", "doubt", "do",
  NOME_DE_CONFIGURAR)`; em `comandos_padrao`:
  ```python
      def concluir_fora_da_janela(_argumento: str, _configuracao: Configuracao) -> Resultado:
          return Resultado("Done", "A lista do done abre na palheta: ctrl+space e done.")
  ```
  e, depois do `Comando("daily", …)`:
  ```python
          Comando(
              "did",
              f"acrescenta uma linha em {SECAO_FIZ} da nota viva",
              anotar_em(SECAO_FIZ, "did"),
              parametro="text",
              rotulo="Did",
              descricao=f"Add a line to {SECAO_FIZ} in daily/atual.md",
              icone="✓",
          ),
          Comando(
              "doing",
              f"acrescenta uma linha em {SECAO_FAZENDO} da nota viva",
              anotar_em(SECAO_FAZENDO, "doing"),
              parametro="text",
              rotulo="Doing",
              descricao=f"Add a line to {SECAO_FAZENDO} in daily/atual.md",
              icone="◔",
          ),
          Comando(
              "done",
              f"leva um item de {SECAO_FAZENDO} para {SECAO_FIZ}",
              concluir_fora_da_janela,
              parametro="search",
              rotulo="Mark done",
              descricao=f"Move an item from {SECAO_FAZENDO} to {SECAO_FIZ}",
              icone="☑",
              lista=ListaDoFazendo,
          ),
  ```
  Docstring do módulo: a lista de comandos com `did`, `doing`, `done`, e `done` ao lado de
  `prompts` como exceção ao dispara e some.
- [ ] **Rodar `test_palheta` e `test_prompts`, e ver passar.**
- [ ] **Commit:** `Atalhos da daily na palheta: did e doing acrescentam em O que eu fiz e O que estou fazendo, done abre a lista de O que estou fazendo e o Enter leva o item com a subarvore para O que eu fiz, copiando os pais sem repetir`.

### Tarefa 6: glossário, roteiros e suíte

**Arquivos:** `CONTEXT.md`, `docs/smoke-interface.md`, `docs/smoke-daily.md`, `src/whis/nota_viva.py`.

- [ ] `CONTEXT.md`:
  - **Daily**: o slide sai das seções com texto em *O que eu fiz*, *O que estou fazendo*, *Dúvidas*
    e *Falar*; acrescentar "*O que terminei*, criada em 2026-09-30, saiu em 2026-10-01: dizia o
    mesmo que *O que eu fiz*".
  - **Nota viva**: seis seções; "`did` (→ *O que eu fiz*), `doing` (→ *O que estou fazendo*),
    `note` (→ *Pontos*), `doubt` (→ *Dúvidas*) e `do` (→ *Fazer*, com a caixa `- [ ]`)
    acrescentam uma linha; `done` leva um item de *O que estou fazendo*, com o que está embaixo
    dele, para *O que eu fiz*, copiando os pais como cabeçalho".
  - **Zona de propriedade**: "onde o agente só acrescenta e move a pedido".
  - **Palheta**: comandos com `did`, `doing`, `done`; "menos `prompts` e `done`, que trocam a
    lista de comandos pela dos **Prompts** e pela dos itens de *O que estou fazendo*, sem fechar a
    janela".
- [ ] `docs/smoke-interface.md`, passo 5: a ordem das ações (Open note, Generate daily, Did,
  Doing, Mark done, Generate news, …) e três linhas na tabela:
  - `doing testando o fazendo` → toast "Anotado em O que estou fazendo"; a linha entra no fim
    de *O que estou fazendo*;
  - `did testando o fiz` → toast "Anotado em O que eu fiz";
  - `done` (ou **Mark done**) → a janela fica e mostra os itens de *O que estou fazendo*; digitar
    filtra; Enter leva o selecionado para o fim de *O que eu fiz* (confira no Obsidian), o
    rodapé diz *Moved: …* e a lista segue aberta sem ele; mova um sub-item e veja o pai copiado,
    depois mova o pai e veja que ele não se repete; **um clique numa linha também move, sem
    desfazer**; Esc volta aos comandos.
- [ ] `docs/smoke-daily.md`, passo 1: "em *O que eu fiz* e *O que estou fazendo*" (sem
  *O que terminei*); acrescentar que `doing`, `did` e `done` na palheta escrevem e movem sem
  abrir o Obsidian.
- [ ] Docstring do módulo `nota_viva.py`: seis seções; as escritas do agente, todas a pedido —
  anotar (`did`, `doing`, `note`, `doubt`, `do`), concluir (`done`) e abrir título que falte;
  "toda edição insere ou remove linhas inteiras, nunca reescreve uma".
- [ ] **Suíte inteira** verde (1109 + os novos, menos os renomeados).
- [ ] **Commit:** `Glossario e roteiros dos atalhos da daily: did, doing e done na nota viva e na palheta; seis secoes`.
