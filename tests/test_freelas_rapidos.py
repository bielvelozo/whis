"""O modo freelas rápidos da caçada: só freela, fontes de freela e a web vasculhada a fundo."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from whis.cacada import cacar
from whis.corrida import Checkpoint
from whis.cacada_claude import TURNOS_DO_EXPLORADOR, TURNOS_DO_EXPLORADOR_A_FUNDO, ExploradorClaude
from whis.configuracao import Configuracao
from whis.criterios_da_cacada import Criterios, FonteDaCacada
from whis.fakes_da_cacada import coleta_fake, portas_fake
from whis.freelas_rapidos import FONTES_DE_FREELA_RAPIDO, PEDIDO_DE_FREELAS_RAPIDOS, criterios_de_freelas


def _criterios() -> Criterios:
    return Criterios(
        procuro="- Quero mais dinheiro.",
        sobre_mim="- Inglês: intermediário",
        fontes=(
            FonteDaCacada("Himalayas · full stack", "himalayas", "full stack developer"),
            FonteDaCacada("Workana · TI e programação", "workana", "it-programming"),
            FonteDaCacada("99Freelas · web", "99freelas", "web-mobile-e-software"),
            FonteDaCacada("Freelancer.com · React", "freelancer", "react"),
            FonteDaCacada("Gupy · desenvolvedor", "gupy", "desenvolvedor"),
            FonteDaCacada("Web · vagas e freelas", "web", "vagas remotas e freelas"),
        ),
    )


def test_o_modo_fica_so_com_as_fontes_de_freela_e_acrescenta_as_dele():
    criterios = criterios_de_freelas(_criterios())

    nomes = [f.nome for f in criterios.fontes]
    assert nomes[:3] == ["Workana · TI e programação", "99Freelas · web", "Freelancer.com · React"]
    assert not {"Himalayas · full stack", "Gupy · desenvolvedor", "Web · vagas e freelas"} & set(nomes)
    assert {f.nome for f in FONTES_DE_FREELA_RAPIDO} <= set(nomes)
    assert len(nomes) == len(set(nomes))
    assert sum(f.tipo == "web" for f in criterios.fontes) >= 5, "a web vasculhada por vários lados"
    assert criterios.procuro.startswith(PEDIDO_DE_FREELAS_RAPIDOS) and criterios.procuro.endswith("- Quero mais dinheiro.")
    assert criterios.sobre_mim == "- Inglês: intermediário"


def test_a_caçada_de_freelas_le_so_as_fontes_do_modo_e_diz_no_relatorio(configuracao: Configuracao, tmp_path: Path):
    lidas: list[str] = []

    def coletar(fontes, agora, **opcoes):
        lidas.extend(f.nome for f in fontes)
        return coleta_fake(fontes, agora, **opcoes)

    portas = portas_fake()
    portas.coletar = coletar

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado", modo="freelas")

    assert resultado.completa
    assert lidas and all(not n.startswith(("Himalayas", "Gupy", "LinkedIn", "Remotive")) for n in lidas)
    assert portas.explorador.chamadas == sum(f.tipo == "web" for f in FONTES_DE_FREELA_RAPIDO)
    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    assert "freelas rápidos" in relatorio.splitlines()[relatorio.splitlines().index("---", 1) + 2]


def test_trocar_de_modo_comeca_uma_caçada_nova_em_vez_de_retomar(configuracao: Configuracao, tmp_path: Path):
    pasta = tmp_path / "estado"
    inacabada = Checkpoint.abrir(pasta)
    inacabada.guardar(
        inicio=datetime.now().astimezone().isoformat(timespec="seconds"), corrida="2000-01-01-0000", etapa="perfil", modo="freelas"
    )

    resultado = cacar(configuracao, portas_fake(), pasta_do_estado=pasta)

    assert resultado.corrida != "2000-01-01-0000"


def test_o_explorador_a_fundo_tem_mais_turnos():
    assert ExploradorClaude().turnos == TURNOS_DO_EXPLORADOR
    assert ExploradorClaude(a_fundo=True).turnos == TURNOS_DO_EXPLORADOR_A_FUNDO > TURNOS_DO_EXPLORADOR
