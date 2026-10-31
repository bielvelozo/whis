"""A ideia de post do X: os dias, a conferência do tamanho e das regras dele, a nota e o celular."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from whis.ideias_do_x import (
    CAMINHO_DAS_IDEIAS,
    Ideia,
    IdeiaFake,
    do_dia,
    ja_usados,
    mensagem_no_celular,
    problemas_da_ideia,
    tamanho_no_x,
)

SEGUNDA = datetime(2026, 11, 2, 12, 30).astimezone()
TERCA = datetime(2026, 11, 3, 12, 30).astimezone()


class Porta:
    def __init__(self, bruto: dict | None = None) -> None:
        self.bruto = bruto
        self.recebidos: list[list[str]] = []

    def escrever(self, ja_usados, voz, contexto):
        self.recebidos.append(list(ja_usados))
        return self.bruto if self.bruto is not None else IdeiaFake().escrever(ja_usados, voz, contexto)


def _rodar(tmp_path: Path, porta: Porta, agora: datetime = SEGUNDA, forcar: bool = False):
    mandadas: list[str] = []
    resultado = do_dia(
        tmp_path / "vault", porta, estado=tmp_path / "x-ideias.json", avisar=lambda t: mandadas.append(t) is None,
        agora=agora, forcar=forcar,
    )
    return resultado, mandadas


def test_seg_qua_e_sex_sai_uma_ideia_por_dia_com_nota_e_celular(tmp_path: Path) -> None:
    porta = Porta()
    resultado, mandadas = _rodar(tmp_path, porta)
    assert resultado.ideia and resultado.caminho == CAMINHO_DAS_IDEIAS
    nota = (tmp_path / "vault" / CAMINHO_DAS_IDEIAS).read_text(encoding="utf-8")
    assert "## 02/11 · App esquecido pesa na loja" in nota and "velozo.dev/velocidade" in nota
    assert len(mandadas) == 1 and mandadas[0].count("<pre>") == 4
    assert _rodar(tmp_path, porta)[0].ja_feita
    assert _rodar(tmp_path, porta, TERCA)[0].motivo.startswith("hoje não é dia")
    assert len(porta.recebidos) == 1
    estado = json.loads((tmp_path / "x-ideias.json").read_text(encoding="utf-8"))
    assert estado["temas"] == ["App esquecido pesa na loja"]


def test_o_tema_ja_usado_e_os_posts_preparados_vao_ao_claude(tmp_path: Path) -> None:
    pasta = tmp_path / "vault" / "cacada" / "x"
    pasta.mkdir(parents=True)
    (pasta / "posts-semana-1.md").write_text("# Posts\n\n## 1. Portfólio (fixar no perfil)\n\n## 2. Inkly de 11,9 s para 3,5 s\n", encoding="utf-8")
    assert ja_usados(tmp_path / "vault", {"temas": ["Frete na sacola"]}) == [
        "Frete na sacola", "Portfólio (fixar no perfil)", "Inkly de 11,9 s para 3,5 s",
    ]


def test_ideia_fora_das_regras_nao_sai_nem_conta_o_dia(tmp_path: Path) -> None:
    ruim = {"tema": "t", "formato": "post", "posts": ["Check velozo.dev 🙂 I use ChatGPT for every store."], "resposta": ""}
    resultado, mandadas = _rodar(tmp_path, Porta(ruim))
    assert mandadas == [] and resultado.problemas
    assert not (tmp_path / "x-ideias.json").exists()


def test_problemas_contam_o_link_como_23_e_barram_o_que_ele_nao_quer() -> None:
    assert tamanho_no_x("See https://velozo.dev/velocidade/?utm_source=x now") == len("See ") + 23 + len(" now")
    boa = Ideia("t", "post", ("Photos straight from the camera slow a store down on a phone.",), resposta="More: velozo.dev")
    assert problemas_da_ideia(boa) == []
    assert problemas_da_ideia(Ideia("t", "post", ("a" * 281,))) == ["o post 1 passa de 280 caracteres"]
    assert "o post 1 tem link (vai na resposta)" in problemas_da_ideia(Ideia("t", "post", ("More at velozo.dev",)))
    assert "mais de 2 hashtags" in problemas_da_ideia(Ideia("t", "post", ("#a #b #c",)))
    assert "fala do preço dele" in problemas_da_ideia(Ideia("t", "post", ("My rates start low.",)))
    assert "diz que usa IA" in problemas_da_ideia(Ideia("t", "post", ("I build every theme with Claude.",)))
    assert problemas_da_ideia(Ideia("t", "post", ())) == ["sem post"]


def test_o_celular_numera_a_thread_e_escapa_o_html() -> None:
    ideia = Ideia("Tema <b>", "thread", ("one < two", "three"), resposta="r", fonte="https://ex.com", por_que="p", arte="print")
    mensagem = mensagem_no_celular(ideia)
    assert "Tema &lt;b&gt;" in mensagem and "1/2" in mensagem and "<pre>one &lt; two</pre>" in mensagem
    assert "Fonte: https://ex.com" in mensagem and "Imagem: print" in mensagem


def test_o_post_preparado_sai_antes_da_ideia_nova_e_o_publicado_fica_de_fora(tmp_path: Path) -> None:
    pasta = tmp_path / "vault" / "cacada" / "x"
    pasta.mkdir(parents=True)
    (pasta / "posts-semana-1.md").write_text(
        "# Posts\n\n## 1. Portfólio\n\n- Publicado: 31/10\n\n```\nI'm Gabriel.\n```\n\n"
        "## 2. Velocidade\n\nImagem: `velocidade.png`\n\n```\nInkly took 11.9 s.\n```\n\n"
        "Primeira resposta ao próprio post, com o link:\n\n```\nCheck yours: velozo.dev/velocidade\n```\n\n"
        "## 3. Thread\n\n```\nOne.\n```\n\n```\nTwo.\n```\n",
        encoding="utf-8",
    )
    porta = Porta()
    resultado, mandadas = _rodar(tmp_path, porta)
    assert resultado.ideia.tema == "Velocidade" and resultado.ideia.resposta == "Check yours: velozo.dev/velocidade"
    assert resultado.ideia.arte == "`velocidade.png`" and resultado.caminho == "" and porta.recebidos == []
    assert "Check yours" in mandadas[0]
    quarta = datetime(2026, 11, 4, 12, 30).astimezone()
    resultado, _ = _rodar(tmp_path, porta, quarta)
    assert resultado.ideia.tema == "Thread" and resultado.ideia.posts == ("One.", "Two.") and resultado.ideia.formato == "thread"
    sexta = datetime(2026, 11, 6, 12, 30).astimezone()
    resultado, _ = _rodar(tmp_path, porta, sexta)
    assert resultado.ideia.tema == "App esquecido pesa na loja" and len(porta.recebidos) == 1
