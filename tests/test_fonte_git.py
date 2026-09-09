"""Comportamento do coletor de git contra repositórios de verdade.

Nada aqui é dublê: cada teste cria repositórios com `git init` e commits
datados em `tmp_path`, roda `coletar(janela)` e olha os `Evento` que saíram —
do mesmo jeito que o diário os receberia. Os repositórios do usuário nunca são
tocados, e nenhum teste fala com a rede.

A configuração global de git da máquina fica de fora (`git_isolado`): sem isso
o `user.email` de quem escreve o teste vazaria para todo repositório de
fixture, e a dedução de autor passaria aqui e falharia no PC de destino.
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

from whis.__main__ import montar_fontes
from whis.configuracao import Configuracao
from whis.fonte_git import FonteGit, de_configuracao
from whis.fontes import ErroDeFonte, Evento, Janela, janela_do_dia

DIA = date(2026, 9, 3)
EMAIL = "gabriel@exemplo.dev"
OUTRO_EMAIL = "colega@exemplo.dev"


# -- cenário ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def git_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isola os testes (e o coletor) da configuração global de git da máquina."""
    vazio = tmp_path / "gitconfig-vazio"
    vazio.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(vazio))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def raiz(tmp_path: Path) -> Path:
    """A raiz de desenvolvimento de mentira, onde os repositórios nascem."""
    caminho = tmp_path / "development"
    caminho.mkdir()
    return caminho


@pytest.fixture
def janela() -> Janela:
    return janela_do_dia(DIA, "04:00")


def git(*argumentos: str, ambiente: dict[str, str] | None = None) -> str:
    concluido = subprocess.run(
        ["git", *argumentos],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, **(ambiente or {})},
        check=True,
    )
    return concluido.stdout


def criar_repositorio(pasta: Path, *, email: str = EMAIL, nome: str = "Gabriel") -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    git("init", "-q", str(pasta))
    git("-C", str(pasta), "config", "user.email", email)
    git("-C", str(pasta), "config", "user.name", nome)
    return pasta


def momento(hora: int, minuto: int = 0, *, dia: date = DIA) -> datetime:
    return datetime.combine(dia, time(hora, minuto)).astimezone()


def commitar(
    repositorio: Path,
    assunto: str,
    quando: datetime,
    *,
    email: str | None = None,
    nome: str | None = None,
    registrado_em: datetime | None = None,
) -> None:
    """Um commit de verdade, com data e autoria escolhidas.

    `quando` é a data de autoria — quando o trabalho foi feito, o que o diário
    quer. `registrado_em` é a data de commit, que um rebase move para depois.
    Cada commit mexe no seu próprio arquivo para que os testes de branch e de
    merge não esbarrem em conflito de conteúdo.
    """
    arquivo = re.sub(r"[^a-z0-9]+", "-", assunto.casefold()).strip("-") + ".md"
    (repositorio / arquivo).write_text(f"{assunto}\n", encoding="utf-8")
    git("-C", str(repositorio), "add", "--", arquivo)
    ambiente = {
        "GIT_AUTHOR_DATE": quando.isoformat(),
        "GIT_COMMITTER_DATE": (registrado_em or quando).isoformat(),
    }
    if email:
        ambiente |= {
            "GIT_AUTHOR_EMAIL": email,
            "GIT_AUTHOR_NAME": nome or email,
            "GIT_COMMITTER_EMAIL": email,
            "GIT_COMMITTER_NAME": nome or email,
        }
    git("-C", str(repositorio), "commit", "-q", "-m", assunto, ambiente=ambiente)


def quebrar(repositorio: Path) -> Path:
    """Um repositório corrompido de verdade: `.git` apontando para o nada.

    É a cara de um submódulo cujo `.git/modules` foi apagado — o caso que não
    pode levar os outros repositórios junto.
    """
    repositorio.mkdir(parents=True, exist_ok=True)
    (repositorio / ".git").write_text("gitdir: ./nao-existe\n", encoding="utf-8")
    return repositorio


def assuntos(eventos: tuple[Evento, ...]) -> list[str]:
    """Os títulos sem o hash curto — o que sobra é o assunto do commit."""
    return [evento.titulo.split("` ", 1)[1] for evento in eventos]


# -- varredura --------------------------------------------------------------


def test_traz_os_commits_do_dia_do_repositorio_varrido(raiz: Path, janela: Janela):
    repositorio = criar_repositorio(raiz / "whis")
    commitar(repositorio, "Fecha a camada 02", momento(9, 12))

    eventos = FonteGit(raiz).coletar(janela)

    assert len(eventos) == 1
    evento = eventos[0]
    assert evento.fonte == "git"
    assert evento.referencia == "whis"
    assert evento.titulo.endswith("Fecha a camada 02")
    assert evento.momento == momento(9, 12)
    assert evento.momento.tzinfo is not None
    assert evento.pessoas == ("Gabriel",)


def test_titulo_carrega_o_hash_curto_do_commit(raiz: Path, janela: Janela):
    """O hash é o que liga a linha do diário ao commit de verdade."""
    repositorio = criar_repositorio(raiz / "loja")
    commitar(repositorio, "Corrige o calculo de frete", momento(17, 45))
    curto = git("-C", str(repositorio), "log", "-1", "--pretty=format:%h").strip()

    eventos = FonteGit(raiz).coletar(janela)

    assert eventos[0].titulo == f"`{curto}` Corrige o calculo de frete"


def test_varre_varios_repositorios_da_raiz(raiz: Path, janela: Janela):
    commitar(criar_repositorio(raiz / "um"), "commit do um", momento(9, 0))
    commitar(criar_repositorio(raiz / "dois"), "commit do dois", momento(10, 0))

    eventos = FonteGit(raiz).coletar(janela)

    assert sorted(evento.referencia for evento in eventos) == ["dois", "um"]


def test_acha_repositorio_aninhado_ate_a_profundidade(raiz: Path, janela: Janela):
    fundo = criar_repositorio(raiz / "clientes" / "acme" / "api")
    commitar(fundo, "commit fundo", momento(11, 0))

    assert assuntos(FonteGit(raiz, profundidade=3).coletar(janela)) == ["commit fundo"]


def test_profundidade_curta_nao_alcanca_o_repositorio(raiz: Path, janela: Janela):
    fundo = criar_repositorio(raiz / "clientes" / "acme" / "api")
    commitar(fundo, "commit fundo", momento(11, 0))

    assert FonteGit(raiz, profundidade=2).coletar(janela) == ()


def test_a_propria_raiz_pode_ser_um_repositorio(raiz: Path, janela: Janela):
    criar_repositorio(raiz)
    commitar(raiz, "commit na raiz", momento(8, 0))

    assert assuntos(FonteGit(raiz).coletar(janela)) == ["commit na raiz"]


def test_pasta_excluida_fica_fora_da_varredura(raiz: Path, janela: Janela):
    commitar(criar_repositorio(raiz / "trabalho"), "commit do trabalho", momento(9, 0))
    commitar(criar_repositorio(raiz / "arquivados" / "velho"), "commit velho", momento(10, 0))

    eventos = FonteGit(raiz, excluir=("arquivados",)).coletar(janela)

    assert assuntos(eventos) == ["commit do trabalho"]


def test_git_como_arquivo_e_aceito(raiz: Path, janela: Janela):
    """`.git` é arquivo em worktree e em submódulo — a varredura tem que aceitar."""
    repositorio = criar_repositorio(raiz / "com-gitdir")
    commitar(repositorio, "commit do submodulo", momento(12, 0))
    de_verdade = raiz / "guardado" / "com-gitdir.git"
    de_verdade.parent.mkdir(parents=True, exist_ok=True)
    (repositorio / ".git").rename(de_verdade)
    (repositorio / ".git").write_text(f"gitdir: {de_verdade.as_posix()}\n", encoding="utf-8")

    eventos = FonteGit(raiz).coletar(janela)

    assert [evento.referencia for evento in eventos] == ["com-gitdir"]
    assert assuntos(eventos) == ["commit do submodulo"]


def test_worktree_nao_duplica_o_mesmo_commit(raiz: Path, janela: Janela):
    """O worktree enxerga os mesmos objetos: sem cuidado, o commit sairia duas vezes."""
    repositorio = criar_repositorio(raiz / "principal")
    commitar(repositorio, "commit compartilhado", momento(13, 0))
    git("-C", str(repositorio), "worktree", "add", "-q", "-b", "recorte", str(raiz / "recorte"))

    eventos = FonteGit(raiz).coletar(janela)

    assert assuntos(eventos) == ["commit compartilhado"]
    assert eventos[0].referencia == "principal"


def test_junction_nao_e_seguida(raiz: Path, tmp_path: Path, janela: Janela):
    """Seguir uma junção que aponta para fora da raiz varreria o disco do usuário."""
    fora = tmp_path / "fora-da-raiz"
    commitar(criar_repositorio(fora / "segredo"), "commit de fora", momento(14, 0))
    try:
        ligacao = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(raiz / "atalho"), str(fora)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as erro:  # fora do Windows não existe junção para testar
        pytest.skip(f"sem mklink nesta plataforma: {erro}")
    if ligacao.returncode != 0:
        pytest.skip(f"não foi possível criar a junção: {ligacao.stderr.strip()}")

    assert FonteGit(raiz).coletar(janela) == ()


def test_raiz_sem_repositorio_nenhum_nao_e_falha(raiz: Path, janela: Janela):
    (raiz / "documentos").mkdir()

    assert FonteGit(raiz).coletar(janela) == ()


# -- a janela ---------------------------------------------------------------


def test_commit_de_outro_dia_nao_entra(raiz: Path, janela: Janela):
    repositorio = criar_repositorio(raiz / "whis")
    commitar(repositorio, "commit de ontem", momento(9, 0, dia=DIA - timedelta(days=1)))
    commitar(repositorio, "commit de hoje", momento(9, 0))

    assert assuntos(FonteGit(raiz).coletar(janela)) == ["commit de hoje"]


def test_commit_da_madrugada_seguinte_entra_no_dia_anterior(raiz: Path, janela: Janela):
    repositorio = criar_repositorio(raiz / "whis")
    commitar(repositorio, "commit da uma da manha", momento(1, 0, dia=DIA + timedelta(days=1)))

    assert assuntos(FonteGit(raiz).coletar(janela)) == ["commit da uma da manha"]


def test_commit_na_virada_fica_fora_da_janela(raiz: Path, janela: Janela):
    """O fim da janela é exclusivo e o `--until` do git é inclusivo: quem recorta é a fonte."""
    repositorio = criar_repositorio(raiz / "whis")
    commitar(repositorio, "commit das quatro em ponto", momento(4, 0, dia=DIA + timedelta(days=1)))

    assert FonteGit(raiz).coletar(janela) == ()


def test_commit_do_dia_sob_um_tip_com_data_velha_nao_some(raiz: Path, janela: Janela):
    """`git log --since` pararia a caminhada no tip velho e engoliria o dia inteiro."""
    repositorio = criar_repositorio(raiz / "whis")
    commitar(repositorio, "commit do dia", momento(9, 0))
    commitar(
        repositorio,
        "commit com data de semana passada",
        momento(9, 0, dia=DIA - timedelta(days=7)),
    )

    assert assuntos(FonteGit(raiz).coletar(janela)) == ["commit do dia"]


def test_commit_rebaseado_depois_continua_no_dia_em_que_foi_escrito(raiz: Path, janela: Janela):
    """A data que vale é a de autoria: o rebase de amanhã não muda o que eu fiz hoje."""
    repositorio = criar_repositorio(raiz / "whis")
    commitar(
        repositorio,
        "commit escrito hoje e rebaseado depois",
        momento(22, 30),
        registrado_em=momento(11, 0, dia=DIA + timedelta(days=6)),
    )

    assert assuntos(FonteGit(raiz).coletar(janela)) == ["commit escrito hoje e rebaseado depois"]


def test_commit_feito_em_outro_fuso_cai_na_hora_local(raiz: Path, janela: Janela):
    """A data do commit traz o fuso em que ele foi feito; o diário quer o relógio de casa."""
    aqui = momento(9, 30)
    distante = aqui.astimezone(timezone(aqui.utcoffset() + timedelta(hours=5)))
    repositorio = criar_repositorio(raiz / "whis")
    commitar(repositorio, "commit de viagem", distante)

    eventos = FonteGit(raiz).coletar(janela)

    assert eventos[0].momento == aqui
    assert eventos[0].momento.utcoffset() == aqui.utcoffset()


# -- autoria ----------------------------------------------------------------


def test_so_traz_os_commits_do_dono_do_repositorio(raiz: Path, janela: Janela):
    repositorio = criar_repositorio(raiz / "whis", email=EMAIL)
    commitar(repositorio, "commit meu", momento(9, 0))
    commitar(repositorio, "commit do colega", momento(10, 0), email=OUTRO_EMAIL, nome="Colega")

    assert assuntos(FonteGit(raiz).coletar(janela)) == ["commit meu"]


def test_cada_repositorio_deduz_o_proprio_email(raiz: Path, janela: Janela):
    """É o que faz o repositório do trabalho funcionar sem cadastro manual."""
    pessoal = criar_repositorio(raiz / "pessoal", email=EMAIL)
    commitar(pessoal, "commit pessoal", momento(9, 0))
    trabalho = criar_repositorio(raiz / "trabalho", email="gabriel@empresa.com", nome="Gabriel FN")
    commitar(trabalho, "commit do trabalho", momento(11, 0))
    commitar(trabalho, "commit de terceiro", momento(12, 0), email=OUTRO_EMAIL, nome="Colega")

    eventos = FonteGit(raiz).coletar(janela)

    assert sorted(assuntos(eventos)) == ["commit do trabalho", "commit pessoal"]


def test_autores_da_configuracao_valem_para_todos_os_repositorios(raiz: Path, janela: Janela):
    repositorio = criar_repositorio(raiz / "whis", email=EMAIL)
    commitar(repositorio, "commit meu", momento(9, 0))
    commitar(repositorio, "commit do colega", momento(10, 0), email=OUTRO_EMAIL, nome="Colega")

    eventos = FonteGit(raiz, autores=(EMAIL, OUTRO_EMAIL)).coletar(janela)

    assert sorted(assuntos(eventos)) == ["commit do colega", "commit meu"]


def test_repositorio_sem_email_configurado_e_pulado_com_aviso(
    raiz: Path, janela: Janela, caplog: pytest.LogCaptureFixture
):
    """Sem saber quem é o usuário, trazer tudo encheria o diário de commit alheio."""
    repositorio = raiz / "sem-dono"
    repositorio.mkdir()
    git("init", "-q", str(repositorio))
    commitar(repositorio, "commit sem dono", momento(9, 0), email=OUTRO_EMAIL, nome="Alguem")

    with caplog.at_level("WARNING", logger="whis.fonte_git"):
        eventos = FonteGit(raiz).coletar(janela)

    assert eventos == ()
    assert "user.email" in caplog.text


# -- o que o git filtra -----------------------------------------------------


def test_merge_commit_nao_entra(raiz: Path, janela: Janela):
    repositorio = criar_repositorio(raiz / "whis")
    commitar(repositorio, "commit base", momento(8, 0))
    git("-C", str(repositorio), "checkout", "-q", "-b", "lateral")
    commitar(repositorio, "commit lateral", momento(9, 0))
    git("-C", str(repositorio), "checkout", "-q", "-")
    commitar(repositorio, "commit principal", momento(10, 0))
    git(
        "-C",
        str(repositorio),
        "merge",
        "-q",
        "--no-ff",
        "-m",
        "Merge da lateral",
        "lateral",
        ambiente={
            "GIT_AUTHOR_DATE": momento(11, 0).isoformat(),
            "GIT_COMMITTER_DATE": momento(11, 0).isoformat(),
        },
    )

    eventos = FonteGit(raiz).coletar(janela)

    assert sorted(assuntos(eventos)) == ["commit base", "commit lateral", "commit principal"]


def test_commit_em_branch_nao_mergeada_entra(raiz: Path, janela: Janela):
    """Sem `--all` o trabalho do dia numa branch aberta sumiria do diário."""
    repositorio = criar_repositorio(raiz / "whis")
    commitar(repositorio, "commit base", momento(8, 0))
    git("-C", str(repositorio), "checkout", "-q", "-b", "experimento")
    commitar(repositorio, "commit da branch aberta", momento(9, 0))
    git("-C", str(repositorio), "checkout", "-q", "-")

    assert "commit da branch aberta" in assuntos(FonteGit(raiz).coletar(janela))


def test_repositorio_recem_criado_sem_commit_nenhum_nao_e_falha(raiz: Path, janela: Janela):
    criar_repositorio(raiz / "novinho")
    commitar(criar_repositorio(raiz / "com-historia"), "commit de verdade", momento(9, 0))

    eventos = FonteGit(raiz).coletar(janela)

    assert [evento.referencia for evento in eventos] == ["com-historia"]


# -- falhas -----------------------------------------------------------------


def test_repositorio_quebrado_nao_derruba_a_coleta_dos_outros(
    raiz: Path, janela: Janela, caplog: pytest.LogCaptureFixture
):
    commitar(criar_repositorio(raiz / "saudavel"), "commit que precisa chegar", momento(9, 0))
    quebrar(raiz / "corrompido")

    with caplog.at_level("ERROR", logger="whis.fonte_git"):
        eventos = FonteGit(raiz).coletar(janela)

    assert assuntos(eventos) == ["commit que precisa chegar"]
    assert "corrompido" in caplog.text


def test_todos_os_repositorios_quebrados_viram_erro_de_fonte(raiz: Path, janela: Janela):
    """Git mudo passando por "dia sem commits" é pior que diário marcado como incompleto."""
    quebrar(raiz / "um")
    quebrar(raiz / "dois")

    with pytest.raises(ErroDeFonte) as erro:
        FonteGit(raiz).coletar(janela)

    assert "Nenhum dos 2 repositórios" in str(erro.value)


def test_git_ausente_no_path_vira_erro_de_fonte(raiz: Path, janela: Janela):
    """A costura só conhece `ErroDeFonte` — um `FileNotFoundError` mataria o diário."""
    criar_repositorio(raiz / "whis")

    with pytest.raises(ErroDeFonte) as erro:
        FonteGit(raiz, git="git-que-nao-existe").coletar(janela)

    assert "PATH" in str(erro.value)


def test_raiz_inexistente_vira_erro_de_fonte_com_o_que_fazer(tmp_path: Path, janela: Janela):
    with pytest.raises(ErroDeFonte) as erro:
        FonteGit(tmp_path / "nunca-existiu").coletar(janela)

    assert "[git].raiz" in str(erro.value)


# -- a fábrica e a CLI ------------------------------------------------------


def configuracao_com_git(raiz: Path, tmp_path: Path, **extras) -> Configuracao:
    return Configuracao(
        vault=tmp_path / "vault",
        gravacoes=tmp_path / "gravacoes",
        git_raiz=raiz,
        origem=tmp_path / "config.toml",
        **extras,
    )


def test_de_configuracao_monta_a_fonte_com_as_chaves_do_git(
    raiz: Path, tmp_path: Path, janela: Janela
):
    commitar(criar_repositorio(raiz / "guardado" / "velho"), "commit velho", momento(9, 0))
    commitar(criar_repositorio(raiz / "atual"), "commit atual", momento(10, 0))

    fonte = de_configuracao(
        configuracao_com_git(raiz, tmp_path, git_profundidade=2, git_excluir=("guardado",))
    )

    assert fonte.nome == "git"
    assert [evento.referencia for evento in fonte.coletar(janela)] == ["atual"]


def test_montar_fontes_liga_o_git_quando_a_raiz_esta_configurada(raiz: Path, tmp_path: Path):
    fontes = montar_fontes(configuracao_com_git(raiz, tmp_path))

    assert [fonte.nome for fonte in fontes] == ["git"]
    assert isinstance(fontes[0], FonteGit)
