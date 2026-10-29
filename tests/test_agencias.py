"""As agências Shopify do Brasil, uma vez por mês: só as novas, só contato da empresa, nada enviado."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from whis.agencias import CAMINHO_DA_LISTA, CAMINHO_DAS_NOVAS, SISTEMA_DAS_AGENCIAS, Agencia, buscar_agencias, ler_conhecidas

AGORA = datetime(2026, 10, 17, 4, 0, tzinfo=timezone(timedelta(hours=-3)))

LISTA = """\
---
tipo: pesquisa
---

# Agências Shopify no Brasil

## 1. Agências e estúdios

**1. Aloft** · Criciúma/SC · https://aloftagencia.com
- Contato: contato@aloftagencia.com (site).

**2. DABS Design / DabsFy** · Curitiba/PR · https://dabsdesign.com.br e https://dabsfy.com.br

### Reserva (sem contato verificável ou com prova fraca)

- **G2 Digital** (Joinville/SC): só achei e-mail pessoal.

### Ficaram de fora e por quê

- **Samurai Experts**: a Locaweb comprou.
"""


class _Busca:
    def __init__(self, achadas):
        self.achadas = achadas
        self.pedidos: list[list[str]] = []

    def buscar(self, conhecidas):
        self.pedidos.append(list(conhecidas))
        return tuple(self.achadas)


NOVA = Agencia(
    nome="Estúdio Novo", cidade="Recife/PE", site="https://estudionovo.com.br",
    contato="contato@estudionovo.com.br, joao.silva@estudionovo.com.br, WhatsApp +55 81 99999-0000",
    prova="Lojas: Loja Um (lojaum.com.br)", nota="Service partner no diretório.",
)


def _vault(tmp_path: Path) -> Path:
    arquivo = tmp_path / CAMINHO_DA_LISTA
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text(LISTA, encoding="utf-8")
    return tmp_path


def test_as_conhecidas_sao_todas_as_da_lista_com_reserva_e_as_de_fora(tmp_path: Path):
    nomes, dominios = ler_conhecidas(_vault(tmp_path))

    assert {"aloft", "dabs design / dabsfy", "g2 digital", "samurai experts"} <= nomes
    assert {"aloftagencia.com", "dabsdesign.com.br", "dabsfy.com.br"} <= dominios


def test_a_busca_do_mes_acrescenta_so_as_novas_sem_e_mail_de_pessoa(tmp_path: Path):
    vault = _vault(tmp_path)
    repetida = Agencia(nome="Aloft Agência", cidade="Criciúma/SC", site="https://www.aloftagencia.com/", contato="", prova="", nota="")
    porta = _Busca([NOVA, repetida, Agencia(nome="Samurai Experts", cidade="SP", site="https://wake.tech", contato="", prova="", nota="")])

    resultado = buscar_agencias(vault, porta, estado=tmp_path / "agencias.json", agora=AGORA)

    assert [a.nome for a in resultado.novas] == ["Estúdio Novo"]
    assert "Aloft" in porta.pedidos[0] and "Samurai Experts" in porta.pedidos[0]
    nota = (vault / CAMINHO_DAS_NOVAS).read_text(encoding="utf-8")
    assert "## Outubro de 2026" in nota
    assert "**1. Estúdio Novo** · Recife/PE · https://estudionovo.com.br" in nota
    assert "contato@estudionovo.com.br" in nota and "joao.silva" not in nota
    assert "e-mail com nome de pessoa, não usar" in nota
    assert "Aloft Agência" not in nota


def test_a_agencia_de_trafego_entra_marcada_e_vira_alvo_do_e_mail_de_marketing(tmp_path: Path):
    from whis import agencias_email

    vault = _vault(tmp_path)
    trafego = Agencia(
        nome="Tráfego Bom", cidade="Campinas/SP", site="https://trafegobom.com.br", contato="contato@trafegobom.com.br",
        prova="Clientes: Loja Dois (lojadois.com.br)", nota="Performance para e-commerce.", tipo="marketing",
    )

    buscar_agencias(vault, _Busca([NOVA, trafego]), estado=tmp_path / "agencias.json", agora=AGORA)

    nota = (vault / CAMINHO_DAS_NOVAS).read_text(encoding="utf-8")
    assert "- Tipo: marketing e tráfego" in nota and nota.count("- Tipo:") == 1
    alvo = next(alvo for alvo in agencias_email.ler_alvos(vault) if alvo.nome == "Tráfego Bom")
    assert "Tipo: marketing" in alvo.detalhes


def test_o_curso_de_e_commerce_entra_marcado_e_vira_alvo_do_e_mail_de_curso(tmp_path: Path):
    from whis import agencias_email

    vault = _vault(tmp_path)
    curso = Agencia(
        nome="Escola da Loja", cidade="São Paulo/SP", site="https://escoladaloja.com.br", contato="contato@escoladaloja.com.br",
        prova="Turma Loja do Zero na Shopify", nota="Ensina dropshipping na Shopify.", tipo="curso",
    )

    buscar_agencias(vault, _Busca([curso]), estado=tmp_path / "agencias.json", agora=AGORA)

    nota = (vault / CAMINHO_DAS_NOVAS).read_text(encoding="utf-8")
    assert "- Tipo: curso ou mentoria de e-commerce" in nota
    alvo = next(alvo for alvo in agencias_email.ler_alvos(vault) if alvo.nome == "Escola da Loja")
    assert "Tipo: curso" in alvo.detalhes
    assert '"curso"' in SISTEMA_DAS_AGENCIAS and "Tipo: curso" in agencias_email.SISTEMA_DO_EMAIL


def test_so_uma_vez_por_mes_a_nao_ser_forcando(tmp_path: Path):
    vault = _vault(tmp_path)
    estado = tmp_path / "agencias.json"
    porta = _Busca([NOVA])
    buscar_agencias(vault, porta, estado=estado, agora=AGORA)

    de_novo = buscar_agencias(vault, porta, estado=estado, agora=AGORA + timedelta(days=3))
    forcada = buscar_agencias(vault, porta, estado=estado, agora=AGORA + timedelta(days=3), forcar=True)
    no_mes_seguinte = buscar_agencias(vault, porta, estado=estado, agora=AGORA + timedelta(days=20))

    assert de_novo.ja_feita and len(porta.pedidos) == 3
    assert not forcada.ja_feita and forcada.novas == (), "a do mês passado já é conhecida"
    assert "Estúdio Novo" in porta.pedidos[1]
    assert not no_mes_seguinte.ja_feita
    nota = (vault / CAMINHO_DAS_NOVAS).read_text(encoding="utf-8")
    assert nota.count("## Outubro de 2026") == 2 and "## Novembro de 2026" in nota and "_Nada novo nesta busca._" in nota


def test_na_procura_busca_a_cada_dois_dias_achando_nova_ou_nao(tmp_path: Path):
    from whis.agencias import buscar_na_procura

    vault = _vault(tmp_path)
    estado = tmp_path / "agencias.json"
    porta = _Busca([NOVA])

    primeira = buscar_na_procura(vault, porta, estado=estado, agora=AGORA)
    amanha = buscar_na_procura(vault, porta, estado=estado, agora=AGORA + timedelta(days=1))
    depois_de_amanha = buscar_na_procura(vault, porta, estado=estado, agora=AGORA + timedelta(days=2))
    vazia_e_mais_dois = buscar_na_procura(vault, porta, estado=estado, agora=AGORA + timedelta(days=4))

    assert not primeira.ja_feita and [a.nome for a in primeira.novas] == ["Estúdio Novo"]
    assert amanha.ja_feita and "a próxima em 19/10" in amanha.motivo
    assert not depois_de_amanha.ja_feita and depois_de_amanha.novas == (), "a já mapeada não volta"
    assert not vazia_e_mais_dois.ja_feita, "a busca vazia não faz a próxima esperar mais"
    assert len(porta.pedidos) == 3
    assert buscar_agencias(vault, porta, estado=estado, agora=AGORA + timedelta(days=1)).ja_feita, "a do mês continua valendo"


def test_o_estado_antigo_so_com_o_mes_busca_na_hora(tmp_path: Path):
    from whis.agencias import buscar_na_procura

    estado = tmp_path / "agencias.json"
    estado.write_text('{"mes": "2026-10", "vazia_em": "2026-10-16"}', encoding="utf-8")

    assert not buscar_na_procura(_vault(tmp_path), _Busca([]), estado=estado, agora=AGORA).ja_feita


def test_o_comando_de_teste_nao_usa_o_claude_nem_o_vault(arquivo_de_configuracao: Path, caminho_do_vault: Path, monkeypatch, capsys):
    from whis.__main__ import main

    monkeypatch.setenv("LOCALAPPDATA", str(caminho_do_vault.parent / "local"))

    assert main(["agencias", "--fakes"]) == 0

    saida = capsys.readouterr().out
    assert "1 agência nova" in saida
    assert not (caminho_do_vault / CAMINHO_DAS_NOVAS).exists()
    assert not (caminho_do_vault.parent / "local" / "whis" / "cacada" / "agencias.json").exists()


def test_a_cacada_de_freelas_inteira_faz_a_busca_do_mes(arquivo_de_configuracao: Path, caminho_do_vault: Path, monkeypatch, capsys):
    from whis.__main__ import main

    monkeypatch.setenv("LOCALAPPDATA", str(caminho_do_vault.parent / "local"))

    assert main(["hunt", "--fakes", "--freelas"]) == 0
    assert "Agências do mês: 1 agência nova" in capsys.readouterr().out
    assert main(["hunt", "--fakes"]) == 0
    assert "Agências do mês" not in capsys.readouterr().out, "só no modo freelas"


@pytest.mark.parametrize("contato, fica", [
    ("contato@x.com.br", "contato@x.com.br"),
    ("comercial@x.com.br / formulário no site", "comercial@x.com.br / formulário no site"),
    ("maria@x.com.br", "(e-mail com nome de pessoa, não usar)"),
])
def test_so_fica_e_mail_da_empresa(contato: str, fica: str):
    from whis.agencias import so_contato_da_empresa

    assert so_contato_da_empresa(contato) == fica
