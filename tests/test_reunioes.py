"""A costura das reuniões: o que a Granola tem e o vault não vira nota em `reunioes/`.

A Granola entra pelo `ReunioesFake`; o vault é o de `tmp_path`. O que se prova
é o que aparece em `reunioes/` e o resultado devolvido.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fixtures.leitura import arquivos_do_vault, corpo, ler_frontmatter
from whis import vault as _vault
from whis.fakes import ReunioesFake
from whis.portas import ErroDaGranola, LoginNecessario, Reuniao
from whis.reunioes import LOTE, puxar_reunioes

MENOS_TRES = timezone(timedelta(hours=-3))


def reuniao(numero: int, *, titulo: str | None = None, resumo: str = "# Decisões\n\n- algo", hora: int = 14) -> Reuniao:
    return Reuniao(
        id=f"{numero:08d}-0000-4000-8000-000000000000",
        titulo=titulo or f"Reunião {numero}",
        inicio=datetime(2026, 9, 1 + numero % 28, hora, 0, tzinfo=MENOS_TRES),
        participantes=("Ana Lima",),
        resumo=resumo,
        url=f"https://notes.granola.ai/d/{numero}",
    )


def notas(vault: Path) -> list[str]:
    return sorted(a for a in arquivos_do_vault(vault) if a.startswith("reunioes/"))


def test_escreve_so_a_reuniao_nova(configuracao, caminho_do_vault: Path):
    primeira = ReunioesFake([reuniao(1)])
    puxar_reunioes(configuracao, primeira)

    segunda = ReunioesFake([reuniao(1), reuniao(2)])
    resultado = puxar_reunioes(configuracao, segunda)

    assert segunda.lotes == [(reuniao(2).id,)]
    assert resultado.novas == (_vault.caminho_da_reuniao(reuniao(2).inicio, "Reunião 2"),)
    assert resultado.ja_no_vault == 1
    assert len(notas(caminho_do_vault)) == 2


def test_reconhece_pelo_granola_id_mesmo_com_titulo_trocado(configuracao, caminho_do_vault: Path):
    puxar_reunioes(configuracao, ReunioesFake([reuniao(1, titulo="Daily")]))

    resultado = puxar_reunioes(configuracao, ReunioesFake([reuniao(1, titulo="Daily (renomeada)")]))

    assert resultado.novas == () and resultado.ja_no_vault == 1
    assert len(notas(caminho_do_vault)) == 1


def test_a_nota_que_existe_nunca_e_reescrita(configuracao, caminho_do_vault: Path):
    puxar_reunioes(configuracao, ReunioesFake([reuniao(1)]))
    [nota] = notas(caminho_do_vault)
    (caminho_do_vault / nota).write_text(
        (caminho_do_vault / nota).read_text(encoding="utf-8") + "\nminha anotação\n", encoding="utf-8"
    )

    puxar_reunioes(configuracao, ReunioesFake([reuniao(1, resumo="outro resumo")]))

    assert "minha anotação" in (caminho_do_vault / nota).read_text(encoding="utf-8")


def test_pula_reuniao_sem_resumo(configuracao, caminho_do_vault: Path):
    resultado = puxar_reunioes(configuracao, ReunioesFake([reuniao(1, resumo="  "), reuniao(2)]))

    assert resultado.sem_resumo == ("Reunião 1",)
    assert len(resultado.novas) == 1
    assert len(notas(caminho_do_vault)) == 1

    depois = puxar_reunioes(configuracao, ReunioesFake([reuniao(1), reuniao(2)]))
    assert len(depois.novas) == 1 and depois.ja_no_vault == 1


def test_nome_com_a_hora_local(configuracao):
    resultado = puxar_reunioes(configuracao, ReunioesFake([reuniao(1, titulo="Daily - Engenharia")]))

    local = reuniao(1).inicio.astimezone()
    assert resultado.novas == (f"reunioes/{local:%Y-%m-%d-%H%M}-daily-engenharia.md",)


def test_nome_que_colide_ganha_sufixo(configuracao, caminho_do_vault: Path):
    gemea = Reuniao(**{**reuniao(1).__dict__, "id": "outra-id"})

    resultado = puxar_reunioes(configuracao, ReunioesFake([reuniao(1), gemea]))

    base = _vault.caminho_da_reuniao(reuniao(1).inicio, "Reunião 1").removesuffix(".md")
    assert sorted(resultado.novas) == sorted([f"{base}.md", f"{base}-2.md"])
    assert len(notas(caminho_do_vault)) == 2


def test_lotes_de_dez(configuracao):
    granola = ReunioesFake([reuniao(numero) for numero in range(1, 24)])

    puxar_reunioes(configuracao, granola)

    assert [len(lote) for lote in granola.lotes] == [LOTE, LOTE, 3]


def test_lote_que_falha_da_parcial_e_o_resto_e_escrito(configuracao):
    granola = ReunioesFake(
        [reuniao(numero) for numero in range(1, 13)],
        erro_no_lote={0: ErroDaGranola("Rate limit exceeded")},
    )

    resultado = puxar_reunioes(configuracao, granola)

    assert len(resultado.falhas) == LOTE
    assert resultado.falhas[0].endswith(": Rate limit exceeded")
    assert len(resultado.novas) == 2
    assert resultado.parcial and not resultado.nada_veio


def test_tudo_falhando_e_nada_veio(configuracao):
    resultado = puxar_reunioes(
        configuracao, ReunioesFake([reuniao(1)], erro_no_lote={0: ErroDaGranola("fora do ar")})
    )

    assert resultado.nada_veio and not resultado.parcial


def test_id_que_nao_volta_conta_como_falha(configuracao):
    resultado = puxar_reunioes(configuracao, ReunioesFake([reuniao(1), reuniao(2)], omitir={reuniao(2).id}))

    assert resultado.falhas == ("Reunião 2: não veio da Granola",)
    assert len(resultado.novas) == 1


def test_login_necessario_sobe(configuracao):
    with pytest.raises(LoginNecessario):
        puxar_reunioes(
            configuracao, ReunioesFake([reuniao(1)], erro_no_lote={0: LoginNecessario("pediu login")})
        )


def test_listar_que_falha_sobe(configuracao, caminho_do_vault: Path):
    with pytest.raises(ErroDaGranola):
        puxar_reunioes(configuracao, ReunioesFake(erro_ao_listar=ErroDaGranola("sem rede")))

    assert notas(caminho_do_vault) == []


def test_a_nota_tem_o_frontmatter_e_nao_tem_data(configuracao, caminho_do_vault: Path):
    resultado = puxar_reunioes(configuracao, ReunioesFake([reuniao(1)]))

    frontmatter = ler_frontmatter(caminho_do_vault / resultado.novas[0])

    assert frontmatter["tipo"] == "reuniao"
    assert frontmatter["participantes"] == ["Ana Lima"]
    assert frontmatter["granola"] == "https://notes.granola.ai/d/1"
    assert frontmatter["granola_id"] == reuniao(1).id
    assert "data" not in frontmatter


def test_o_resumo_entra_literal_com_titulo_e_quando(configuracao, caminho_do_vault: Path):
    resumo = "# Ana: entregas\n\n- Fix \\&B no PDF\n- *nada* reescrito"
    resultado = puxar_reunioes(configuracao, ReunioesFake([reuniao(1, titulo="Daily", resumo=resumo)]))

    texto = corpo(caminho_do_vault / resultado.novas[0]).lstrip("\n")

    assert texto.startswith("# Daily\n\n2 de setembro de 2026 (quarta-feira), 14:00\n\n")
    assert resumo in texto


def test_o_vault_que_ja_tinha_a_nota_a_reconhece_com_aspas(configuracao, caminho_do_vault: Path):
    """`_frontmatter` cita UUID que começa por dígito; a leitura tira as aspas."""
    _vault.preparar(caminho_do_vault)
    (caminho_do_vault / "reunioes" / "2026-09-02-1400-feita-a-mao.md").write_text(
        f'---\ntipo: reuniao\ngranola_id: "{reuniao(1).id}"\n---\n# Feita à mão\n', encoding="utf-8"
    )

    resultado = puxar_reunioes(configuracao, ReunioesFake([reuniao(1)]))

    assert resultado.novas == () and resultado.ja_no_vault == 1
