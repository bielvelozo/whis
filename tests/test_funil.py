"""O funil das propostas de freela: mandadas, respondidas e fechadas por semana, e o que os sites mostram."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from whis.cacada import cacar
from whis.configuracao import Configuracao
from whis.fakes_da_cacada import NavegadorLogadoFake, portas_fake
from whis.funil import Mandada, ler_mandadas, montar_funil, situacao_nos_sites
from whis.navegador_logado import PAGINAS_DE_CONFERENCIA

FIXTURES = Path(__file__).parent / "fixtures" / "cacada_logada"
NOVENTA = "https://www.99freelas.com.br/project/auditoria-de-planilhas-790661"
FREELANCER = "https://www.freelancer.com/projects/shopify/fix-shopify-theme-40761662"


def _nota(vault: Path, relativo: str, **campos: str) -> None:
    arquivo = vault / "cacada" / relativo
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = "\n".join(f"{chave}: {valor}" for chave, valor in campos.items())
    arquivo.write_text(f"---\n{frontmatter}\n---\n\nTexto da proposta.\n", encoding="utf-8")


def _vault_com_propostas(vault: Path) -> None:
    pasta = "2026-10-12-1832-propostas"
    _nota(vault, f"{pasta}/auditoria.md", titulo='"Auditoria de planilhas"', link=NOVENTA, status="enviada em 2026-10-13 (R$ 50, 7 dias)")
    _nota(vault, f"{pasta}/tema.md", titulo='"Fix Shopify theme"', link=FREELANCER, status="enviada em 2026-10-14 (USD 30, 5 dias)")
    _nota(vault, f"{pasta}/bot.md", titulo='"Bot de WhatsApp"', link="https://www.99freelas.com.br/project/bot-2", status="respondida em 2026-10-16 (enviada em 2026-10-13)")
    _nota(vault, f"{pasta}/loja.md", titulo='"Loja do zero"', link="https://www.99freelas.com.br/project/loja-3", status="fechado (enviada em 2026-10-06)")
    _nota(vault, f"{pasta}/escrita.md", titulo='"Ainda não mandei"', link="https://www.99freelas.com.br/project/x-4", status="escrita")
    _nota(vault, "2026-10-10-0618/vaga.md", tipo="pacote", titulo='"Vaga full stack"', link="https://acme.gupy.io/jobs/1", status="enviada")


def test_as_mandadas_sao_as_notas_de_freela_enviadas_com_a_data_do_envio(tmp_path: Path):
    _vault_com_propostas(tmp_path)

    mandadas = {m.titulo: m for m in ler_mandadas(tmp_path)}

    assert set(mandadas) == {"Auditoria de planilhas", "Fix Shopify theme", "Bot de WhatsApp", "Loja do zero"}
    assert mandadas["Bot de WhatsApp"].enviada == date(2026, 10, 13)
    assert mandadas["Loja do zero"].enviada == date(2026, 10, 6)


def test_o_funil_conta_por_semana_do_envio(tmp_path: Path):
    _vault_com_propostas(tmp_path)

    texto = "\n".join(montar_funil(ler_mandadas(tmp_path), {}, motivo="sem o Chrome da caçada nesta corrida"))

    assert "## Funil" in texto
    assert "| semana de 12/10 | 3 | 1 | 0 |" in texto
    assert "| semana de 05/10 | 1 | 1 | 1 |" in texto
    assert texto.index("semana de 12/10") < texto.index("semana de 05/10"), "a mais nova primeiro"
    assert "sem o Chrome da caçada nesta corrida" in texto


def test_o_que_os_sites_mostram_das_que_esperam_resposta(tmp_path: Path):
    paginas = {
        PAGINAS_DE_CONFERENCIA["99freelas"]: (FIXTURES / "99freelas_aberto.html").read_text(encoding="utf-8"),
        PAGINAS_DE_CONFERENCIA["freelancer"]: (FIXTURES / "freelancer_aberto.html").read_text(encoding="utf-8"),
        NOVENTA: (FIXTURES / "99freelas_ja_propos.html").read_text(encoding="utf-8"),
        f"{FREELANCER}/proposals": (FIXTURES / "freelancer_ja_ofertou_propostas.html").read_text(encoding="utf-8"),
    }
    mandadas = [
        Mandada("Auditoria de planilhas", NOVENTA, "enviada em 2026-10-13", date(2026, 10, 13), ""),
        Mandada("Fix Shopify theme", FREELANCER, "enviada em 2026-10-14", date(2026, 10, 14), ""),
        Mandada("Loja do zero", "https://www.99freelas.com.br/project/loja-3", "fechado", date(2026, 10, 6), ""),
    ]

    with NavegadorLogadoFake(paginas).abrir() as sessao:
        situacoes = situacao_nos_sites(mandadas, sessao)

    assert situacoes[NOVENTA].startswith("99Freelas: aberto, esperando o cliente")
    assert situacoes[FREELANCER] == "Freelancer.com: aberto, sua proposta em 60º de 98"
    assert "https://www.99freelas.com.br/project/loja-3" not in situacoes, "a fechada não precisa abrir"
    texto = "\n".join(montar_funil(mandadas, situacoes))
    assert f"- [Fix Shopify theme]({FREELANCER}) — enviada em 2026-10-14 · Freelancer.com: aberto, sua proposta em 60º de 98" in texto


def test_o_cliente_que_escolheu_outro_aparece(tmp_path: Path):
    paginas = {
        PAGINAS_DE_CONFERENCIA["99freelas"]: (FIXTURES / "99freelas_aberto.html").read_text(encoding="utf-8"),
        NOVENTA: (FIXTURES / "99freelas_escolhido.html").read_text(encoding="utf-8"),
    }
    with NavegadorLogadoFake(paginas).abrir() as sessao:
        situacoes = situacao_nos_sites([Mandada("A", NOVENTA, "enviada", date(2026, 10, 13), "")], sessao)

    assert situacoes[NOVENTA] == "99Freelas: o cliente já escolheu um freelancer (se não foi você, perdida)"


def test_o_relatorio_da_caçada_ganha_a_secao_funil(configuracao: Configuracao, tmp_path: Path):
    _vault_com_propostas(Path(configuracao.vault))

    resultado = cacar(configuracao, portas_fake(), pasta_do_estado=tmp_path / "estado", modo="freelas")

    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    funil = relatorio.split("## Funil", 1)[1].split("## Fontes", 1)[0]
    assert "| semana de 12/10 | 3 | 1 | 0 |" in funil
    assert "sem o Chrome da caçada" in funil
