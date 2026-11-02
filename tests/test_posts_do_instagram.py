"""Os posts do Instagram no dia do calendário: o que sai, o que nunca sai duas vezes e o aviso no celular."""

from __future__ import annotations

import json
import subprocess
from datetime import date, datetime, time
from pathlib import Path

import pytest

from whis import automacao
from whis.configuracao import Configuracao
from whis.posts_do_instagram import (
    CARROSSEL,
    ENSAIO,
    ENVIANDO,
    FALHOU,
    INCERTO,
    PUBLICADO,
    REEL,
    SEM_REDE,
    ConteudoIncompleto,
    Envio,
    ErroDoInstagram,
    Postagem,
    SemRede,
    conteudo_da_postagem,
    escolher,
    ler_calendario,
    ler_estado,
    ler_legenda,
    publicar_do_dia,
    rede_pronta,
)

DOMINGO_19H = datetime(2026, 11, 1, 19, 0)

CALENDARIO = {
    "reels": [
        {"pasta": "01-plinko", "dia": "Dom 01/11", "tipo": "3d", "titulo": "100 pessoas entraram na sua loja"},
        {"pasta": "09-analise-marca", "dia": "Seg 02/11", "tipo": "analise"},
        {"pasta": "08-pichau", "dia": "Qui 05/11", "tipo": "corte"},
    ],
    "posts": [
        {"pasta": "03-aqui-e-o-gabriel", "dia": "Sáb 31/10", "hora": "hoje"},
        {"pasta": "01-pagina-responde", "dia": "Sex 06/11"},
    ],
}

LEGENDA = "Cem pessoas entraram na sua loja hoje.\n\nMe chama no direct.\n\n#lojavirtual #shopify"


@pytest.fixture
def raiz(tmp_path: Path) -> Path:
    """O calendário, as legendas do velozo-reels e as mídias de `.scratch/instagram`, de mentira."""
    (tmp_path / "calendario.json").write_text(json.dumps(CALENDARIO), encoding="utf-8")
    for pasta in ("01-plinko", "09-analise-marca", "08-pichau"):
        textos = tmp_path / "textos" / "reels" / pasta
        textos.mkdir(parents=True)
        (textos / "legenda.md").write_text(f"# {pasta}\n\n## Legenda do post\n\n{LEGENDA}\n\n## Áudio\n\nvoz provisória\n", encoding="utf-8")
    reels = tmp_path / "midias" / "reels"
    reels.mkdir(parents=True)
    for nome in ("01-plinko-sem-voz.mp4", "01-plinko.mp4", "01-plinko-capa.jpg", "09-analise-marca-sem-voz.mp4",
                 "09-analise-marca-capa.jpg", "08-pichau.mp4", "08-pichau-capa.jpg"):
        (reels / nome).write_bytes(b"x")
    slides = tmp_path / "midias" / "posts" / "01-pagina-responde"
    slides.mkdir(parents=True)
    for nome in ("02.png", "01.png", "03.png", "folha.jpg"):
        (slides / nome).write_bytes(b"x")
    textos = tmp_path / "textos" / "posts" / "01-pagina-responde"
    textos.mkdir(parents=True)
    (textos / "legenda.md").write_text(f"# post\n\n## Legenda\n\n{LEGENDA}\n", encoding="utf-8")
    return tmp_path


class Porta:
    def __init__(self, *, erro: Exception | None = None, depois_do_clique: Exception | None = None, envio: Envio | None = None) -> None:
        self.erro = erro
        self.depois_do_clique = depois_do_clique
        self.envio = envio or Envio(confirmado=True, link="https://www.instagram.com/reel/ABC123/")
        self.chamadas: list[tuple[str, tuple[str, ...], str, bool]] = []

    def publicar(self, postagem, conteudo, *, compartilhar, antes_do_clique):
        self.chamadas.append((postagem.pasta, tuple(a.name for a in conteudo.arquivos), conteudo.legenda, compartilhar))
        if self.erro:
            raise self.erro
        if compartilhar:
            antes_do_clique()
            if self.depois_do_clique:
                raise self.depois_do_clique
        return self.envio if compartilhar else Envio(confirmado=False)


def _rodar(raiz: Path, porta: Porta, agora: datetime = DOMINGO_19H, **opcoes):
    mandadas: list[str] = []
    resultado = publicar_do_dia(
        porta, estado=raiz / "estado.json", avisar=mandadas.append, agora=agora,
        postagens=ler_calendario(raiz / "calendario.json"), midias=raiz / "midias", textos=raiz / "textos", **opcoes,
    )
    return resultado, mandadas, ler_estado(raiz / "estado.json")


def test_o_calendario_vira_dia_de_2026_as_19h_e_o_corte_de_podcast_fica_marcado(raiz: Path) -> None:
    postagens = {p.pasta: p for p in ler_calendario(raiz / "calendario.json")}
    assert postagens["01-plinko"] == Postagem("01-plinko", REEL, date(2026, 11, 1), time(19, 0), "100 pessoas entraram na sua loja")
    assert postagens["03-aqui-e-o-gabriel"].hora == time(19, 0) and postagens["03-aqui-e-o-gabriel"].tipo == CARROSSEL
    assert postagens["08-pichau"].corte and not postagens["01-plinko"].corte


def test_a_legenda_e_so_a_secao_legenda_com_ou_sem_do_post() -> None:
    assert ler_legenda("# x\n\n## Legenda\n\nUm.\n\nDois.\n\n## Áudio\n\nnão\n") == "Um.\n\nDois."
    assert ler_legenda("# x\r\n\r\n## Legenda do post\r\n\r\nTrês.\r\n") == "Três."
    assert ler_legenda("# x\n\n## Gancho\n\nnada\n") == ""


def test_o_reel_sai_sem_voz_e_o_corte_sai_no_mp4_original(raiz: Path) -> None:
    postagens = {p.pasta: p for p in ler_calendario(raiz / "calendario.json")}
    plinko = conteudo_da_postagem(postagens["01-plinko"], midias=raiz / "midias", textos=raiz / "textos")
    assert [a.name for a in plinko.arquivos] == ["01-plinko-sem-voz.mp4"] and plinko.capa.name == "01-plinko-capa.jpg"
    assert plinko.legenda == LEGENDA
    pichau = conteudo_da_postagem(postagens["08-pichau"], midias=raiz / "midias", textos=raiz / "textos")
    assert [a.name for a in pichau.arquivos] == ["08-pichau.mp4"]


def test_sem_o_arquivo_sem_voz_o_reel_nao_cai_no_narrado(raiz: Path) -> None:
    (raiz / "midias" / "reels" / "01-plinko-sem-voz.mp4").unlink()
    plinko = next(p for p in ler_calendario(raiz / "calendario.json") if p.pasta == "01-plinko")
    with pytest.raises(ConteudoIncompleto, match="01-plinko-sem-voz.mp4"):
        conteudo_da_postagem(plinko, midias=raiz / "midias", textos=raiz / "textos")


def test_o_carrossel_leva_so_os_slides_numerados_em_ordem(raiz: Path) -> None:
    post = next(p for p in ler_calendario(raiz / "calendario.json") if p.pasta == "01-pagina-responde")
    conteudo = conteudo_da_postagem(post, midias=raiz / "midias", textos=raiz / "textos")
    assert [a.name for a in conteudo.arquivos] == ["01.png", "02.png", "03.png"] and conteudo.capa is None


def test_no_domingo_as_19h_sai_o_reel_01_com_link_no_celular(raiz: Path) -> None:
    porta = Porta()
    resultado, mandadas, estado = _rodar(raiz, porta, agendada=True)
    assert resultado.situacao == PUBLICADO
    assert porta.chamadas == [("01-plinko", ("01-plinko-sem-voz.mp4",), LEGENDA, True)]
    assert estado["01-plinko"]["situacao"] == PUBLICADO and estado["01-plinko"]["link"].endswith("/reel/ABC123/")
    assert mandadas == ["Instagram: saiu o Reel 01-plinko.\n100 pessoas entraram na sua loja\nhttps://www.instagram.com/reel/ABC123/"]


def test_antes_das_19h_e_em_dia_sem_item_nada_abre(raiz: Path) -> None:
    porta = Porta()
    assert _rodar(raiz, porta, datetime(2026, 11, 1, 18, 59))[0].motivo == "01-plinko é às 19:00"
    saidos = {p: {"situacao": PUBLICADO, "quando": "2026-11-06T19:00:00"} for p in ("01-plinko", "09-analise-marca", "08-pichau", "01-pagina-responde")}
    (raiz / "estado.json").write_text(json.dumps({"posts": saidos}), encoding="utf-8")
    assert _rodar(raiz, porta, datetime(2026, 11, 7, 19, 0))[0].motivo == "nada no calendário hoje"
    assert porta.chamadas == []


def test_o_que_ja_saiu_nunca_sai_de_novo_e_dois_posts_tem_intervalo(raiz: Path) -> None:
    porta = Porta()
    _rodar(raiz, porta, agendada=True)
    resultado, mandadas, _ = _rodar(raiz, porta, datetime(2026, 11, 1, 20, 0), agendada=True)
    assert resultado.postagem is None and resultado.motivo == "o último saiu às 19:00; o próximo espera até 21:00"
    resultado, _, _ = _rodar(raiz, porta, datetime(2026, 11, 1, 20, 0), pasta="09-analise-marca")
    assert resultado.motivo == "o último saiu às 19:00; o próximo espera até 21:00"
    resultado, _, _ = _rodar(raiz, porta, datetime(2026, 11, 1, 21, 0), agendada=True)
    assert resultado.postagem is None and resultado.motivo == "01-plinko já está como publicado"
    assert len(porta.chamadas) == 1 and mandadas == []


def test_o_carrossel_ja_publicado_a_mao_nunca_sai(raiz: Path) -> None:
    porta = Porta()
    resultado, mandadas, estado = _rodar(raiz, porta, datetime(2026, 10, 31, 19, 30), pasta="03-aqui-e-o-gabriel")
    assert resultado.postagem is None and "já está como publicado" in resultado.motivo
    resultado, _, _ = _rodar(raiz, porta, datetime(2026, 10, 31, 19, 30))
    assert resultado.postagem is None and porta.chamadas == []


def test_login_vencido_avisa_uma_vez_e_a_tarefa_nao_tenta_de_novo(raiz: Path) -> None:
    porta = Porta(erro=ErroDoInstagram("o login do Instagram venceu no Chrome do Whis"))
    resultado, mandadas, estado = _rodar(raiz, porta, agendada=True)
    assert resultado.situacao == FALHOU and estado["01-plinko"]["situacao"] == FALHOU
    assert len(mandadas) == 1 and "Nada foi publicado" in mandadas[0] and "whis instagram-login" in mandadas[0]
    resultado, mandadas, _ = _rodar(raiz, porta, datetime(2026, 11, 1, 20, 0), agendada=True)
    assert resultado.postagem is None and mandadas == [] and len(porta.chamadas) == 1


def test_a_mao_o_que_falhou_pode_ir_de_novo(raiz: Path) -> None:
    _rodar(raiz, Porta(erro=ErroDoInstagram("o Chrome não abriu")), agendada=True)
    porta = Porta()
    resultado, _, estado = _rodar(raiz, porta, datetime(2026, 11, 1, 20, 0))
    assert resultado.situacao == PUBLICADO and estado["01-plinko"]["situacao"] == PUBLICADO


def test_sem_confirmacao_depois_do_clique_fica_incerto_e_nunca_repete(raiz: Path) -> None:
    porta = Porta(envio=Envio(confirmado=False))
    resultado, mandadas, estado = _rodar(raiz, porta, agendada=True)
    assert resultado.situacao == INCERTO and estado["01-plinko"]["situacao"] == INCERTO
    assert "não tenta de novo" in mandadas[0]
    resultado, _, _ = _rodar(raiz, Porta(), datetime(2026, 11, 1, 21, 0), pasta="01-plinko")
    assert resultado.postagem is None


def test_erro_depois_do_clique_tambem_fica_incerto(raiz: Path) -> None:
    resultado, mandadas, estado = _rodar(raiz, Porta(depois_do_clique=RuntimeError("a página fechou")), agendada=True)
    assert resultado.situacao == INCERTO and estado["01-plinko"]["situacao"] == INCERTO and len(mandadas) == 1


def test_o_estado_vira_enviando_antes_do_clique(raiz: Path) -> None:
    vistos: list[str] = []

    class Espia(Porta):
        def publicar(self, postagem, conteudo, *, compartilhar, antes_do_clique):
            antes_do_clique()
            vistos.append(ler_estado(raiz / "estado.json")["01-plinko"]["situacao"])
            return Envio(confirmado=True, link="https://www.instagram.com/reel/X1234/")

    _rodar(raiz, Espia(), agendada=True)
    assert vistos == [ENVIANDO]


def test_o_que_nao_saiu_no_domingo_sai_quando_o_pc_volta_e_o_do_dia_continua_no_horario(raiz: Path) -> None:
    porta = Porta()
    resultado, mandadas, estado = _rodar(raiz, porta, datetime(2026, 11, 2, 10, 0), agendada=True)
    assert resultado.situacao == PUBLICADO and resultado.postagem.pasta == "01-plinko"
    assert mandadas[0].startswith("Instagram: saiu o Reel 01-plinko (era de 01/11 às 19:00).")
    assert _rodar(raiz, porta, datetime(2026, 11, 2, 13, 0), agendada=True)[0].motivo == "09-analise-marca é às 19:00"
    resultado, mandadas, _ = _rodar(raiz, porta, datetime(2026, 11, 2, 19, 0), agendada=True)
    assert resultado.situacao == PUBLICADO and resultado.postagem.pasta == "09-analise-marca"
    assert mandadas[0].startswith("Instagram: saiu o Reel 09-analise-marca.")
    assert [chamada[0] for chamada in porta.chamadas] == ["01-plinko", "09-analise-marca"]


def test_atrasado_e_o_do_dia_saem_um_de_cada_vez_e_o_mais_antigo_primeiro(raiz: Path) -> None:
    porta = Porta()
    _rodar(raiz, porta, datetime(2026, 11, 2, 19, 0), agendada=True)
    resultado, _, _ = _rodar(raiz, porta, datetime(2026, 11, 2, 20, 0), agendada=True)
    assert resultado.postagem is None and "espera até 21:00" in resultado.motivo
    resultado, _, _ = _rodar(raiz, porta, datetime(2026, 11, 2, 21, 0), agendada=True)
    assert resultado.situacao == PUBLICADO
    assert [chamada[0] for chamada in porta.chamadas] == ["01-plinko", "09-analise-marca"]


def test_sem_internet_nada_e_gravado_nem_avisado_e_a_proxima_rodada_posta(raiz: Path) -> None:
    porta = Porta()
    resultado, mandadas, estado = _rodar(raiz, porta, agendada=True, esperar_rede=lambda: False)
    assert resultado.situacao == SEM_REDE and estado == {} and mandadas == [] and porta.chamadas == []
    resultado, mandadas, estado = _rodar(raiz, Porta(erro=SemRede("net::ERR_NAME_NOT_RESOLVED")), agendada=True)
    assert resultado.situacao == SEM_REDE and estado == {} and mandadas == []
    resultado, mandadas, estado = _rodar(raiz, porta, datetime(2026, 11, 1, 21, 0), agendada=True)
    assert resultado.situacao == PUBLICADO and estado["01-plinko"]["situacao"] == PUBLICADO and len(mandadas) == 1


def test_a_rede_e_esperada_ate_o_limite() -> None:
    agora = [0.0]
    tentativas: list[tuple] = []

    class Conexao:
        def close(self) -> None:
            pass

    def conectar(endereco, timeout):
        tentativas.append(endereco)
        if len(tentativas) < 3:
            raise OSError("getaddrinfo failed")
        return Conexao()

    def dormir(segundos: float) -> None:
        agora[0] += segundos

    assert rede_pronta(600, conectar=conectar, dormir=dormir, relogio=lambda: agora[0])
    assert tentativas == [("www.instagram.com", 443)] * 3 and agora[0] == 30

    def sem_rede(endereco, timeout):
        raise OSError("getaddrinfo failed")

    agora[0] = 0.0
    assert not rede_pronta(60, conectar=sem_rede, dormir=dormir, relogio=lambda: agora[0])
    assert agora[0] == 60


def test_arquivo_que_falta_nao_abre_o_chrome_e_avisa(raiz: Path) -> None:
    (raiz / "midias" / "reels" / "01-plinko-capa.jpg").unlink()
    porta = Porta()
    resultado, mandadas, estado = _rodar(raiz, porta, agendada=True)
    assert resultado.situacao == FALHOU and porta.chamadas == [] and "01-plinko-capa.jpg" in mandadas[0]


def test_o_ensaio_nao_clica_nem_grava_nem_avisa(raiz: Path) -> None:
    porta = Porta()
    resultado, mandadas, estado = _rodar(raiz, porta, datetime(2026, 10, 31, 20, 0), ensaio=True)
    assert resultado.situacao == ENSAIO and resultado.postagem.pasta == "01-plinko"
    assert porta.chamadas[0][3] is False and mandadas == [] and estado == {}


def test_a_tarefa_roda_as_19h_e_nas_horas_do_atrasado_o_postar_agendado(tmp_path: Path) -> None:
    comandos: list[list[str]] = []

    def espiao(comando: list[str]) -> subprocess.CompletedProcess:
        comandos.append(comando)
        return subprocess.CompletedProcess(comando, 0, "", "")

    nome = automacao.agendar_posts_do_instagram(Configuracao(vault=Path("V"), origem=tmp_path / "config.toml"), executar=espiao)
    [comando] = comandos
    assert nome == "Whis-Instagram"
    assert comando[comando.index("-Gatilhos") + 1] == "Daily=10:00,Daily=13:00,Daily=16:00,Daily=19:00,Daily=21:00,Logon"
    assert comando[comando.index("-Argumentos") + 1] == f'-m whis instagram-postar --agendada --config "{tmp_path / "config.toml"}"'


def test_escolher_com_pasta_fora_do_calendario(raiz: Path) -> None:
    postagens = ler_calendario(raiz / "calendario.json")
    assert escolher(postagens, {}, DOMINGO_19H, pasta="99-nada") == (None, "99-nada não está no calendário")
