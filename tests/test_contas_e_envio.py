"""A entrega 2, sem rede, sem Claude e sem navegador: a regra de quem envia, o registro, a caixa,
as contas e a etapa de envio da caçada.

O que se prova é a borda: só tentar a sorte, só vaga, só formulário grátis e sem
limite, nunca LinkedIn, nunca duas vezes; senha no cofre antes de o agente
começar; link de confirmação seguido só do site onde o Whis pediu a conta.
"""

from __future__ import annotations

import json
from dataclasses import replace
from email.message import EmailMessage
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

from whis.acoes import CANDIDATURA, CONTA, FEITO, INTENCAO, Registro
from whis.cacada import cacar
from whis.caixa import confirmacoes_seguras, interpretar, ler_caixa
from whis.cofre import Cofre
from whis.configuracao import Configuracao
from whis.contas import chave_no_cofre, cuidar_das_contas, dados_dele, montar_nota_das_contas
from whis.criterios_da_cacada import MODELO_DOS_CRITERIOS, interpretar_criterios
from whis.fakes_da_cacada import portas_fake
from whis.fontes_da_cacada import ColetaDaCacada
from whis.navegador_agente import FERRAMENTAS_DO_NAVEGADOR, AgenteDoNavegador, DadosDele, Desfecho
from whis.oportunidades import CHANCE_BOA, FREELA, TENTAR_A_SORTE, VAGA, Oportunidade, Veredito
from whis.politica import pode_enviar_sozinho


def _vaga(link: str, tipo: str = VAGA) -> Oportunidade:
    return Oportunidade.nova(tipo=tipo, fonte="F", titulo="Game Developer", link=link)


# -- a política ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "link, tipo, classe, golpe, ligado, pode",
    [
        ("https://acme.gupy.io/jobs/1", VAGA, TENTAR_A_SORTE, False, True, True),
        ("https://boards.greenhouse.io/acme/jobs/2", VAGA, TENTAR_A_SORTE, False, True, True),
        ("https://acme.gupy.io/jobs/1", VAGA, TENTAR_A_SORTE, False, False, False),
        ("https://acme.gupy.io/jobs/1", VAGA, CHANCE_BOA, False, True, False),
        ("https://acme.gupy.io/jobs/1", VAGA, TENTAR_A_SORTE, True, True, False),
        ("https://www.workana.com/job/x", FREELA, TENTAR_A_SORTE, False, True, False),
        ("https://br.linkedin.com/jobs/view/1", VAGA, TENTAR_A_SORTE, False, True, False),
        ("https://empresa.com.br/vagas/1", VAGA, TENTAR_A_SORTE, False, True, False),
    ],
)
def test_so_tentar_a_sorte_de_vaga_em_formulario_gratis_e_sem_limite(tmp_path, link, tipo, classe, golpe, ligado, pode):
    oportunidade = _vaga(link, tipo)
    veredito = Veredito(oportunidade.id, classe, "", 40, golpe)

    assert pode_enviar_sozinho(oportunidade, veredito, Registro(tmp_path), ligado=ligado)[0] is pode


def test_o_que_ja_foi_tentado_nunca_sai_de_novo(tmp_path: Path):
    registro = Registro(tmp_path)
    oportunidade = _vaga("https://acme.gupy.io/jobs/1?utm_source=x")
    registro.intencao(CANDIDATURA, "https://acme.gupy.io/jobs/1")

    pode, motivo = pode_enviar_sozinho(oportunidade, Veredito(oportunidade.id, TENTAR_A_SORTE, ""), registro, ligado=True)

    assert not pode and "já tentada" in motivo


def test_o_registro_so_acrescenta_e_guarda_a_intencao_sem_desfecho(tmp_path: Path):
    registro = Registro(tmp_path)
    a = registro.intencao(CONTA, "Workana", detalhe="https://www.workana.com")
    b = registro.intencao(CONTA, "99Freelas")
    registro.concluir(a, FEITO, "conta criada")

    acoes = {acao.alvo: acao for acao in registro.acoes()}

    assert acoes["workana"].estado == FEITO and acoes["workana"].detalhe == "conta criada"
    assert acoes["99freelas"].estado == INTENCAO and acoes["99freelas"].sem_desfecho
    assert len((tmp_path / "acoes.jsonl").read_text(encoding="utf-8").splitlines()) == 3
    assert b


# -- a caixa ------------------------------------------------------------------------------------------


def _email(remetente: str, assunto: str, corpo: str) -> bytes:
    mensagem = EmailMessage()
    mensagem["From"] = f"Site <{remetente}>"
    mensagem["Subject"] = assunto
    mensagem["Date"] = "Fri, 02 Oct 2026 22:00:00 -0300"
    mensagem.set_content(corpo)
    return mensagem.as_bytes()


def test_so_a_confirmacao_do_site_pedido_e_segura():
    boa = interpretar(_email("no-reply@workana.com", "Confirme seu e-mail", "Clique: https://www.workana.com/confirm?t=1 ."))
    estranha = interpretar(_email("no-reply@workana-premio.com", "Confirme", "https://workana-premio.com/confirm"))
    fora = interpretar(_email("no-reply@workana.com", "Verifique sua conta", "https://bit.ly/x"))
    outra = interpretar(_email("vagas@acme.com", "Entrevista", "https://acme.com/confirm"))

    seguras = confirmacoes_seguras([boa, estranha, fora, outra], ["workana.com"])

    assert seguras == [(boa, "https://www.workana.com/confirm?t=1")]


class ImapFake:
    def __init__(self, mensagens: list[bytes]) -> None:
        self.mensagens = mensagens
        self.so_leitura = None

    def login(self, usuario, senha):
        assert (usuario, senha) == ("eu@gmail.com", "abcdabcdabcdabcd")

    def select(self, caixa, readonly=False):
        self.so_leitura = readonly

    def search(self, _charset, *criterios):
        return "OK", [" ".join(str(i + 1) for i in range(len(self.mensagens))).encode()]

    def fetch(self, numero, partes):
        assert partes == "(BODY.PEEK[])", "nada pode ser marcado como lido"
        return "OK", [(b"1", self.mensagens[int(numero) - 1])]

    def logout(self):
        pass


def test_a_caixa_e_lida_so_para_leitura():
    imap = ImapFake([_email("a@b.com", "Olá", "texto")])

    mensagens = ler_caixa("eu@gmail.com", "abcdabcdabcdabcd", conectar=lambda _s: imap)

    assert [m.assunto for m in mensagens] == ["Olá"] and imap.so_leitura is True


# -- as contas -------------------------------------------------------------------------------------------


class AgenteFake:
    def __init__(self, cofre: Cofre | None = None, criar: str = FEITO) -> None:
        self.cofre = cofre
        self.criar = criar
        self.chamadas: list[tuple[str, str]] = []

    def criar_conta(self, site, endereco, senha, dados):
        if self.cofre is not None:
            assert self.cofre.obter(chave_no_cofre(site))["senha"] == senha, "a senha vai ao cofre antes do agente"
        self.chamadas.append(("criar", site))
        return Desfecho(self.criar, "ok", "confirmar o e-mail" if self.criar == FEITO else "resolver o CAPTCHA")

    def completar_perfil(self, site, endereco, perfil_texto, dados):
        self.chamadas.append(("perfil", site))
        return Desfecho(FEITO, "perfil preenchido")


def _cofre(tmp_path: Path) -> Cofre:
    return Cofre(tmp_path / "cofre.bin", cifrar=lambda b: b[::-1], decifrar=lambda b: b[::-1])


def test_contas_criam_confirmam_e_completam_e_nao_se_repetem(tmp_path: Path):
    configuracao = Configuracao(vault=tmp_path, cacada_email="eu@gmail.com")
    criterios = interpretar_criterios("## Contas\n- Workana: https://www.workana.com\n")
    cofre = _cofre(tmp_path)
    registro = Registro(tmp_path / "estado")
    agente = AgenteFake(cofre)
    caixa = [interpretar(_email("no-reply@workana.com", "Confirme seu e-mail", "https://www.workana.com/confirm?t=9"))]
    seguidos: list[str] = []

    resultado = cuidar_das_contas(
        configuracao, criterios, agente=agente, cofre=cofre, registro=registro, perfil_texto="perfil",
        ler_caixa=lambda: caixa, seguir=lambda link: seguidos.append(link) or True,
    )

    situacao = resultado.situacoes[0]
    assert (situacao.conta_feita, situacao.confirmada, situacao.perfil_feito, situacao.pendente) == (True, True, True, "")
    assert agente.chamadas == [("criar", "Workana"), ("perfil", "Workana")]
    assert seguidos == ["https://www.workana.com/confirm?t=9"]
    nota = montar_nota_das_contas(resultado, "eu@gmail.com", __import__("datetime").datetime(2026, 10, 3))
    assert cofre.obter("conta:workana")["senha"] not in nota

    de_novo = AgenteFake()
    cuidar_das_contas(configuracao, criterios, agente=de_novo, cofre=cofre, registro=registro, perfil_texto="p")
    assert de_novo.chamadas == [], "conta e perfil feitos não se refazem"


def test_captcha_fica_pendente_e_criacao_interrompida_nao_e_refeita(tmp_path: Path):
    configuracao = Configuracao(vault=tmp_path, cacada_email="eu@gmail.com")
    criterios = interpretar_criterios("## Contas\n- Upwork: https://www.upwork.com\n- Contra: https://contra.com\n")
    registro = Registro(tmp_path / "estado")
    registro.intencao(CONTA, "Contra")

    resultado = cuidar_das_contas(
        configuracao, criterios, agente=AgenteFake(criar="precisa_de_voce"), cofre=_cofre(tmp_path), registro=registro, perfil_texto=""
    )

    upwork, contra = resultado.situacoes
    assert upwork.pendente == "resolver o CAPTCHA" and not upwork.conta_feita
    assert "não terminou" in contra.pendente


def test_sem_email_dedicado_nao_comeca(tmp_path: Path):
    with pytest.raises(ValueError, match="email"):
        cuidar_das_contas(
            Configuracao(vault=tmp_path), interpretar_criterios(MODELO_DOS_CRITERIOS), agente=AgenteFake(),
            cofre=_cofre(tmp_path), registro=Registro(tmp_path), perfil_texto="",
        )


def test_dados_vem_do_config_e_de_sobre_mim():
    criterios = interpretar_criterios("## Sobre mim\n- GitHub público: https://github.com/eu\n- Currículo (caminho do PDF no PC): C:/cv.pdf\n")
    dados = dados_dele(Configuracao(vault=Path("/v"), cacada_email="e@g.com", cacada_cpf="123"), criterios)

    assert (dados.email, dados.cpf, dados.github, dados.curriculo) == ("e@g.com", "123", "https://github.com/eu", "C:/cv.pdf")
    assert MODELO_DOS_CRITERIOS.count("- ") and len(interpretar_criterios(MODELO_DOS_CRITERIOS).contas) == 9


# -- o envio na caçada ------------------------------------------------------------------------------------


class NavegadorFake:
    def __init__(self) -> None:
        self.ultimo_plano = None
        self.custo_usd = 0.0
        self.candidaturas: list[str] = []

    def candidatar(self, link, titulo, mensagem, dados):
        self.candidaturas.append(link)
        return Desfecho(FEITO, "candidatura enviada", "", "nome, e-mail, currículo")


def _portas_com_envio(tmp_path: Path):
    oportunidades = (
        Oportunidade.nova(tipo=VAGA, fonte="Gupy", titulo="Game Developer Júnior", link="https://estudio.gupy.io/jobs/7"),
        Oportunidade.nova(tipo=VAGA, fonte="LinkedIn", titulo="Unity Developer", link="https://br.linkedin.com/jobs/view/9"),
        Oportunidade.nova(tipo=FREELA, fonte="Workana", titulo="Game em Unity", link="https://www.workana.com/job/game"),
    )

    def coletar(*_a, **_k):
        coleta = ColetaDaCacada()
        coleta.por_fonte["exemplo"] = oportunidades
        return coleta

    navegador = NavegadorFake()
    portas = replace(portas_fake(), coletar=coletar, navegador=navegador, registro=Registro(tmp_path / "estado"))
    return portas, navegador


def test_com_envio_ligado_so_a_vaga_da_gupy_sai_e_o_relatorio_diz(configuracao: Configuracao, tmp_path: Path):
    portas, navegador = _portas_com_envio(tmp_path)
    ligado = replace(configuracao, cacada_enviar_sozinho=True)

    resultado = cacar(ligado, portas, pasta_do_estado=tmp_path / "estado")

    assert navegador.candidaturas == ["https://estudio.gupy.io/jobs/7"]
    assert resultado.enviadas == 1 and resultado.tentar_a_sorte == 3
    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    assert "O Whis enviou sozinho 1 candidatura(s)" in relatorio and "**Enviada pelo Whis.**" in relatorio
    acoes = portas.registro.acoes()
    assert [(a.tipo, a.estado) for a in acoes] == [(CANDIDATURA, FEITO)]


def test_com_envio_desligado_o_navegador_nem_e_chamado(configuracao: Configuracao, tmp_path: Path):
    portas, navegador = _portas_com_envio(tmp_path)

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado")

    assert navegador.candidaturas == [] and resultado.enviadas == 0
    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    assert "Nada foi enviado a ninguém" in relatorio


def test_a_caixa_vira_lista_no_relatorio(configuracao: Configuracao, tmp_path: Path):
    mensagem = interpretar(_email("recrutadora@acme.com", "Entrevista na quinta?", "Oi!"))
    portas = replace(portas_fake(), ler_caixa=lambda: [mensagem])

    resultado = cacar(configuracao, portas, pasta_do_estado=tmp_path / "estado")

    relatorio = (Path(configuracao.vault) / resultado.relatorio).read_text(encoding="utf-8")
    assert "## Caixa do Gmail dedicado" in relatorio and "recrutadora@acme.com — Entrevista na quinta?" in relatorio


# -- o agente do navegador ---------------------------------------------------------------------------------


def test_o_agente_usa_o_playwright_sem_linkedin_e_sem_codigo(tmp_path: Path):
    curriculo = tmp_path / "meu cv.pdf"
    curriculo.write_bytes(b"%PDF")

    class Gravado(AgenteDoNavegador):
        async def _mensagens(self, prompt, opcoes):
            self.prompt, self.opcoes = prompt, opcoes
            yield ResultMessage(
                subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=3, session_id="s",
                structured_output={"status": "precisa_de_voce", "motivo": "CAPTCHA", "o_que_falta": "resolver o CAPTCHA", "resumo_do_envio": ""},
            )

    agente = Gravado(npx="npx", perfil=tmp_path / "perfil", trabalho=tmp_path / "trabalho")
    desfecho = agente.candidatar("https://acme.gupy.io/jobs/1", "Dev", "Olá", DadosDele(email="e@g.com", curriculo=str(curriculo)))

    assert desfecho.status == "precisa_de_voce" and desfecho.o_que_falta == "resolver o CAPTCHA"
    servidor = agente.opcoes.mcp_servers["playwright"]
    assert "--blocked-origins" in servidor["args"] and "linkedin.com" in servidor["args"][servidor["args"].index("--blocked-origins") + 1]
    assert str(tmp_path / "perfil") in servidor["args"]
    assert agente.opcoes.tools == [] and not any("evaluate" in f or "run_code" in f for f in agente.opcoes.allowed_tools)
    assert agente.opcoes.allowed_tools == FERRAMENTAS_DO_NAVEGADOR
    assert (tmp_path / "trabalho" / "curriculo.pdf").read_bytes() == b"%PDF"
    assert json.loads(agente.prompt.split("DADOS DELE:\n", 1)[1].split("\nCURRÍCULO", 1)[0])["email"] == "e@g.com"
    assert "nunca" in agente.opcoes.system_prompt.lower()
