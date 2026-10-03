"""O prompt stash: `prompts/` no vault, `stash` na palheta e a lista com os gestos.

Nenhum teste chega no clipboard de verdade — o `conftest` o tranca; aqui a
área é um fake que guarda o que foi copiado e colado.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from whis import prompts
from whis.fakes import BuscaFake, PublicacaoDoDeckFake
from whis.janela_da_palheta import Acao, Efeito, Gesto, Linha, acao_que_abre, texto_do_detalhe
from whis.palheta import ListaDePrompts, Palheta, comandos_padrao
from whis.vault import ForaDaZonaDePropriedade


class AreaFake:
    def __init__(self, conteudo: str = "") -> None:
        self.conteudo = conteudo
        self.copiados: list[str] = []
        self.colados: list[str] = []

    def ler(self) -> str:
        return self.conteudo

    def copiar(self, texto: str) -> None:
        self.copiados.append(texto)

    def colar(self, texto: str) -> None:
        self.colados.append(texto)


def escrever_prompt(vault: Path, nome: str, texto: str) -> Path:
    arquivo = vault / "prompts" / f"{nome}.md"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_bytes(texto.encode("utf-8"))
    return arquivo


# -- ler e filtrar ---------------------------------------------------------------


def test_sem_pasta_nao_ha_prompt(tmp_path: Path):
    assert prompts.listar(tmp_path) == []


def test_le_os_dois_formatos_de_lista_do_obsidian_e_o_prompt_sem_frontmatter(tmp_path: Path):
    escrever_prompt(tmp_path, "Revisar PR", "---\ntags: [review, \"claude\"]\nfavorito: true\n---\n\nOlhe o diff.\n")
    escrever_prompt(tmp_path, "Commit", "---\ntags:\n  - git\n  - '#msg'\nfavorito: false\n---\nEscreva a mensagem.")
    escrever_prompt(tmp_path, "Solto", "Só o corpo, criado no Obsidian.")

    achados = {prompt.titulo: prompt for prompt in prompts.listar(tmp_path)}

    assert achados["Revisar PR"].tags == ("review", "claude") and achados["Revisar PR"].favorito
    assert achados["Revisar PR"].conteudo == "Olhe o diff."
    assert achados["Commit"].tags == ("git", "msg") and not achados["Commit"].favorito
    assert achados["Solto"].conteudo == "Só o corpo, criado no Obsidian." and achados["Solto"].tags == ()
    assert achados["Commit"].caminho == "prompts/Commit.md"


def test_subpastas_valem_e_favoritos_vem_primeiro(tmp_path: Path):
    escrever_prompt(tmp_path, "b", "B")
    escrever_prompt(tmp_path, "sub/a", "A")
    escrever_prompt(tmp_path, "z", "---\nfavorito: true\n---\nZ")

    assert [prompt.titulo for prompt in prompts.listar(tmp_path)] == ["z", "a", "b"]


def _p(titulo: str, conteudo: str = "", tags: tuple[str, ...] = (), favorito: bool = False) -> prompts.Prompt:
    return prompts.Prompt(titulo, conteudo, f"prompts/{titulo}.md", tags, favorito)


def test_filtra_por_palavras_tag_e_favorito():
    todos = [
        _p("Revisar PR", "olhe o diff com calma", ("review", "claude")),
        _p("Commit", "escreva a mensagem do diff", ("git",), favorito=True),
        _p("Resumo", "resuma a reunião", ("meeting",)),
    ]

    assert [p.titulo for p in prompts.filtrar(todos, "")] == ["Commit", "Resumo", "Revisar PR"]
    assert [p.titulo for p in prompts.filtrar(todos, "diff")] == ["Commit", "Revisar PR"]
    assert [p.titulo for p in prompts.filtrar(todos, "#rev")] == ["Revisar PR"]
    assert [p.titulo for p in prompts.filtrar(todos, "*")] == ["Commit"]
    assert [p.titulo for p in prompts.filtrar(todos, "#git *")] == ["Commit"]
    assert [p.titulo for p in prompts.filtrar(todos, "#claude diff")] == ["Revisar PR"]
    assert prompts.filtrar(todos, "#nada") == []


def test_quem_casa_no_titulo_vem_antes_de_quem_casa_so_no_corpo():
    todos = [_p("Alfa", "fala de resumo"), _p("Resumo curto", "texto")]

    assert [p.titulo for p in prompts.filtrar(todos, "resumo")] == ["Resumo curto", "Alfa"]


# -- guardar ---------------------------------------------------------------------


def test_o_pedido_separa_titulo_tags_e_favorito():
    assert prompts.interpretar_pedido("Revisar PR #review #claude *") == prompts.Pedido(
        "Revisar PR", ("review", "claude"), True
    )
    assert prompts.interpretar_pedido("  ") == prompts.Pedido("", (), False)


def test_guardar_escreve_o_frontmatter_e_o_corpo_sem_crlf(tmp_path: Path):
    prompt = prompts.guardar(tmp_path, prompts.Pedido("Revisar PR", ("review",), True), "linha 1\r\nlinha 2\r\n")

    assert prompt.caminho == "prompts/Revisar PR.md"
    assert (tmp_path / prompt.caminho).read_bytes().decode("utf-8") == (
        "---\ntags:\n  - review\nfavorito: true\n---\nlinha 1\nlinha 2\n"
    )
    [lido] = prompts.listar(tmp_path)
    assert lido == prompt


def test_sem_titulo_o_titulo_e_a_primeira_linha_e_o_nome_sai_limpo(tmp_path: Path):
    prompt = prompts.guardar(tmp_path, prompts.Pedido("", (), False), "\n# Explique: o que é <isto>?\nresto")

    assert prompt.titulo == "Explique o que é isto"
    assert (tmp_path / "prompts" / "Explique o que é isto.md").is_file()


@pytest.mark.parametrize("conteudo", ["", "  \r\n  "])
def test_clipboard_vazio_e_recusado(tmp_path: Path, conteudo: str):
    with pytest.raises(prompts.PromptRecusado, match="clipboard está vazio"):
        prompts.guardar(tmp_path, prompts.Pedido("x", (), False), conteudo)


def test_titulo_repetido_nunca_sobrescreve(tmp_path: Path):
    original = escrever_prompt(tmp_path, "sub/Revisar PR", "meu texto")

    with pytest.raises(prompts.PromptJaExiste) as erro:
        prompts.guardar(tmp_path, prompts.Pedido("revisar pr", (), False), "outro")

    assert erro.value.caminho == "prompts/sub/Revisar PR.md"
    assert original.read_text(encoding="utf-8") == "meu texto"


def test_a_zona_dos_prompts_nao_alcanca_outra_pasta(tmp_path: Path):
    from whis import vault

    with pytest.raises(ForaDaZonaDePropriedade):
        vault.escrever(tmp_path, "notas/x.md", "", zonas=prompts.ZONAS_DOS_PROMPTS)


# -- favoritar -------------------------------------------------------------------


def test_favoritar_troca_so_a_linha_e_preserva_o_resto_byte_a_byte(tmp_path: Path):
    arquivo = escrever_prompt(tmp_path, "p", "---\r\ntags: [a]\r\nfavorito: false\r\nautor: eu\r\n---\r\ncorpo\r\n  com espaço \r\n")
    [prompt] = prompts.listar(tmp_path)

    novo = prompts.alternar_favorito(tmp_path, prompt)

    assert novo.favorito
    assert arquivo.read_bytes() == (
        "---\r\ntags: [a]\r\nfavorito: true\r\nautor: eu\r\n---\r\ncorpo\r\n  com espaço \r\n"
    ).encode("utf-8")
    prompts.alternar_favorito(tmp_path, novo)
    assert b"favorito: false" in arquivo.read_bytes()


def test_favoritar_prompt_sem_frontmatter_cria_um(tmp_path: Path):
    arquivo = escrever_prompt(tmp_path, "p", "só corpo\n")
    [prompt] = prompts.listar(tmp_path)

    prompts.alternar_favorito(tmp_path, prompt)

    assert arquivo.read_text(encoding="utf-8") == "---\nfavorito: true\n---\nsó corpo\n"
    assert prompts.listar(tmp_path)[0].favorito


def test_favoritar_frontmatter_sem_a_chave_acrescenta_antes_do_fim(tmp_path: Path):
    arquivo = escrever_prompt(tmp_path, "p", "---\ntags: [a]\n---\ncorpo")
    [prompt] = prompts.listar(tmp_path)

    prompts.alternar_favorito(tmp_path, prompt)

    assert arquivo.read_text(encoding="utf-8") == "---\ntags: [a]\nfavorito: true\n---\ncorpo"


# -- o comando stash -------------------------------------------------------------


@pytest.fixture
def palheta_com(configuracao_do_diario):
    def montar(area: AreaFake, lancados: list[str] | None = None) -> Palheta:
        configuracao = configuracao_do_diario()
        comandos = comandos_padrao(
            publicacao_do_deck=lambda _c: PublicacaoDoDeckFake(),
            busca=lambda _c: BuscaFake(),
            lancar=(lancados if lancados is not None else []).append,
            relogio=lambda: datetime(2026, 9, 24, 10, tzinfo=timezone.utc),
            area=area,
        )
        return Palheta(comandos, configuracao, avisar=avisos.append_aviso, iniciar_thread=lambda alvo: alvo())

    class Avisos(list):
        def append_aviso(self, titulo, texto, *, botao=None, executar=None):
            self.append((titulo, texto, botao))
            return True

    avisos = Avisos()
    montar.avisos = avisos
    return montar


def test_stash_guarda_o_clipboard_e_avisa_com_o_botao(palheta_com, caminho_do_vault: Path):
    palheta = palheta_com(AreaFake("Revise este diff."))

    palheta.despachar("stash Revisar PR #review *")

    titulo, texto, botao = palheta_com.avisos[-1]
    assert titulo == "Prompt guardado" and texto == "Revisar PR #review ★"
    assert botao and botao[1].endswith("prompts%2FRevisar%20PR")
    [prompt] = prompts.listar(caminho_do_vault)
    assert prompt.conteudo == "Revise este diff." and prompt.favorito


def test_stash_com_clipboard_vazio_nao_escreve(palheta_com, caminho_do_vault: Path):
    palheta = palheta_com(AreaFake(""))

    palheta.despachar("stash X")

    assert palheta_com.avisos[-1][0] == "Nada guardado"
    assert prompts.listar(caminho_do_vault) == []


def test_stash_repetido_avisa_com_o_botao_do_que_existe(palheta_com, caminho_do_vault: Path):
    escrever_prompt(caminho_do_vault, "X", "antigo")
    palheta = palheta_com(AreaFake("novo"))

    palheta.despachar("stash X")

    titulo, _texto, botao = palheta_com.avisos[-1]
    assert titulo == "Esse prompt já existe" and botao[1].endswith("prompts%2FX")
    assert (caminho_do_vault / "prompts" / "X.md").read_text(encoding="utf-8") == "antigo"


def test_prompts_tem_lista_e_stash_nao(palheta_com):
    palheta = palheta_com(AreaFake())
    por_nome = {comando.nome: comando for comando in palheta.comandos}

    assert por_nome["prompts"].lista is not None
    assert por_nome["stash"].lista is None
    assert [comando.nome for comando in palheta.acoes()][10:12] == ["prompts", "stash"]


# -- a lista ---------------------------------------------------------------------


@pytest.fixture
def lista(configuracao_do_diario, caminho_do_vault: Path):
    escrever_prompt(caminho_do_vault, "Commit", "---\ntags: [git]\nfavorito: false\n---\nEscreva a mensagem.\nSegunda linha.")
    escrever_prompt(caminho_do_vault, "Revisar PR", "---\ntags: [review]\nfavorito: false\n---\nOlhe o diff.")
    area = AreaFake("Prompt novo do clipboard")
    lancados: list[str] = []
    lista = ListaDePrompts(configuracao_do_diario(), area=area, lancar=lancados.append)
    lista.area, lista.lancados = area, lancados
    return lista


def gesto(lista: ListaDePrompts, dica: str) -> Gesto:
    return next(g for g in lista.gestos if g.dica == dica)


def test_as_linhas_trazem_icone_titulo_primeira_linha_e_tags(lista):
    assert lista.linhas("") == [
        Linha("❝", "Commit", "Escreva a mensagem.", "#git"),
        Linha("❝", "Revisar PR", "Olhe o diff.", "#review"),
    ]
    assert lista.detalhe(0) == "Escreva a mensagem.\nSegunda linha."
    assert lista.linhas("#rev") == [Linha("❝", "Revisar PR", "Olhe o diff.", "#review")]


def test_enter_cola_e_ctrl_enter_so_copia_os_dois_escondendo(lista):
    lista.linhas("")

    assert gesto(lista, "Paste").esconde and gesto(lista, "Paste").tecla == "<Return>"
    gesto(lista, "Paste").rodar(1, "")
    gesto(lista, "Copy").rodar(0, "")

    assert lista.area.colados == ["Olhe o diff."]
    assert lista.area.copiados == ["Escreva a mensagem.\nSegunda linha."]


def test_sem_selecao_os_gestos_nao_fazem_nada(lista):
    lista.linhas("#nada")

    for dica in ("Paste", "Copy", "Edit", "Favorite"):
        gesto(lista, dica).rodar(None, "#nada")

    assert lista.area.colados == lista.area.copiados == lista.lancados == []


def test_ctrl_f_favorita_e_a_selecao_segue_o_prompt_para_o_topo(lista, caminho_do_vault: Path):
    lista.linhas("")

    efeito = gesto(lista, "Favorite").rodar(1, "")

    assert efeito == Efeito(selecionar=0, mensagem="★ Revisar PR")
    assert lista.linhas("")[0] == Linha("★", "Revisar PR", "Olhe o diff.", "#review")
    assert not gesto(lista, "Favorite").esconde


def test_ctrl_e_abre_a_nota_no_obsidian(lista):
    lista.linhas("")

    gesto(lista, "Edit").rodar(0, "")

    assert lista.lancados and lista.lancados[0].endswith("prompts%2FCommit")


def test_ctrl_n_guarda_o_clipboard_com_o_texto_do_campo_e_seleciona(lista, caminho_do_vault: Path):
    lista.linhas("Novo #ia")

    efeito = gesto(lista, "New").rodar(None, "Novo #ia")

    assert efeito.mensagem == "Stashed Novo"
    assert lista.linhas("Novo #ia")[efeito.selecionar].titulo == "Novo"
    novo = next(p for p in prompts.listar(caminho_do_vault) if p.titulo == "Novo")
    assert novo.tags == ("ia",) and novo.conteudo == "Prompt novo do clipboard"


def test_ctrl_n_repetido_diz_no_rodape_e_nao_escreve(lista, caminho_do_vault: Path):
    efeito = gesto(lista, "New").rodar(None, "Commit")

    assert "already exists" in efeito.mensagem and efeito.selecionar is None
    assert "Escreva a mensagem." in (caminho_do_vault / "prompts" / "Commit.md").read_text(encoding="utf-8")


def test_vazia_diz_como_comecar_ou_que_nada_casa(lista, configuracao_do_diario, tmp_path: Path):
    lista.linhas("#nada")
    assert "No prompt matches" in lista.vazia

    vazia = ListaDePrompts(
        configuracao_do_diario().__class__(vault=tmp_path / "vazio"),
        area=AreaFake(),
        lancar=lambda _uri: None,
    )
    vazia.linhas("")
    assert "No prompts yet" in vazia.vazia


# -- a janela --------------------------------------------------------------------


def test_o_nome_da_acao_abre_a_lista_com_o_resto_como_busca():
    acoes = (Acao("prompts", "❝", "Search prompts", abre=lambda: None), Acao("ask", "?", "Ask"))

    assert acao_que_abre("prompts #git", acoes) == (acoes[0], "#git")
    assert acao_que_abre("  Search   prompts ", acoes) == (acoes[0], "")
    assert acao_que_abre("ask x", acoes) is None
    assert acao_que_abre("", acoes) is None


def test_o_detalhe_quebra_e_corta_com_reticencias():
    assert texto_do_detalhe("a\nb") == "a\nb"
    longo = "\n".join(f"linha {n}" for n in range(20))
    cortado = texto_do_detalhe(longo).splitlines()
    assert len(cortado) == 7 and cortado[-1] == "linha 6 …"


class ListaDublê:
    nome = "Prompts"
    placeholder = "Search prompts…"
    vazia = "Nada"

    def __init__(self, titulos: list[str]) -> None:
        self.titulos = titulos
        self.rodados: list[tuple[str, int | None, str]] = []
        self.gestos = (
            Gesto("<Return>", "↵", "Paste", lambda i, t: self.rodados.append(("paste", i, t)), esconde=True),
            Gesto("<Control-f>", "Ctrl F", "Favorite", self._favoritar),
        )

    def _favoritar(self, indice, texto):
        self.rodados.append(("fav", indice, texto))
        self.titulos.insert(0, self.titulos.pop(indice))
        return Efeito(selecionar=0, mensagem="★")

    def linhas(self, texto: str) -> list[Linha]:
        return [Linha("❝", titulo, f"corpo de {titulo}") for titulo in self.titulos if texto.casefold() in titulo.casefold()]

    def detalhe(self, indice: int) -> str:
        return f"corpo de {self.linhas('')[indice].titulo}"


def test_a_janela_de_verdade_abre_a_lista_rola_favorita_cola_e_volta():
    tk = pytest.importorskip("tkinter")
    from whis.janela_da_palheta import MAXIMO_DE_LINHAS, JanelaDaPalheta

    try:
        janela = JanelaDaPalheta()
    except tk.TclError as erro:
        pytest.skip(f"sem tela para o Tk: {erro}")
    enviados: list[str] = []
    titulos = [f"prompt {n:02d}" for n in range(12)]
    lista = ListaDublê(titulos)
    janela.ao_enviar(enviados.append)
    janela.definir_acoes((Acao("prompts", "❝", "Search prompts", aceita_argumento=True, abre=lambda: lista), Acao("ask", "?", "Ask")))
    try:
        janela.mostrar()
        janela.raiz.update()
        janela.digitar("prompts")
        janela._enter()
        assert janela.visivel() and janela.lista_aberta() is lista and enviados == []
        assert len(janela.linhas_da_lista()) == 12
        assert len(janela.titulos_desenhados()) == MAXIMO_DE_LINHAS
        assert janela.detalhe_desenhado() == "corpo de prompt 00"

        for _ in range(9):
            janela._mover_selecao(1)
        assert janela.indice_selecionado() == 9
        assert janela.titulos_desenhados()[-1] == "prompt 09"
        assert janela.detalhe_desenhado() == "corpo de prompt 09"

        janela._campo.event_generate("<Control-f>")
        janela.raiz.update()
        assert lista.rodados[-1] == ("fav", 9, "")
        assert janela.indice_selecionado() == 0 and janela.titulos_desenhados()[0] == "prompt 09"
        assert janela.mensagem() == "★" and janela.visivel()

        janela.digitar("11")
        assert [linha.titulo for linha in janela.linhas_da_lista()] == ["prompt 11"]
        janela._enter()
        assert lista.rodados[-1] == ("paste", 0, "11") and not janela.visivel()
        assert enviados == []

        janela.mostrar()
        janela.raiz.update()
        assert janela.lista_aberta() is None
        janela.digitar("prompts 03")
        janela._enter()
        assert [linha.titulo for linha in janela.linhas_da_lista()] == ["prompt 03"]
        janela.digitar("")
        janela._campo.event_generate("<BackSpace>")
        janela.raiz.update()
        assert janela.lista_aberta() is None and janela.visivel()
        assert [acao.nome for acao in janela.acoes_visiveis()] == ["prompts", "ask"]

        janela.abrir_lista(lista, "zzz")
        assert janela.linhas_da_lista() == ()
        janela._campo.event_generate("<Escape>")
        janela.raiz.update()
        assert janela.lista_aberta() is None and janela.visivel()
        janela._campo.event_generate("<Escape>")
        janela.raiz.update()
        assert not janela.visivel()
    finally:
        janela.raiz.destroy()
