"""O acompanhamento das candidaturas: `cacada/candidaturas.md`, regenerada a cada caçada.

Três fontes, nenhuma nova:

- **os pacotes** das chances boas: ele troca `status: preparada` por `enviada`,
  `entrevista`, `proposta`, `recusada` ou `fechado` no frontmatter da nota, no
  Obsidian — é o único dado que só ele tem;
- **o registro de ações**: as candidaturas que o Whis mandou sozinho;
- **a caixa do Gmail dedicado**: um e-mail cujo remetente é do domínio da
  empresa, ou que cita o nome dela, vira "respondeu" naquela linha.

A nota é do agente e é reescrita inteira; o que ele decide fica nos pacotes.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import vault as _vault
from .criterios_da_cacada import PASTA_CACADA
from .politica import DOMINIOS_GRATIS_E_SEM_LIMITE, casa, dominio

CAMINHO_DAS_CANDIDATURAS = f"{PASTA_CACADA}/candidaturas.md"

PREPARADA = "preparada"
ABERTOS = ("enviada", "entrevista", "proposta")
ENCERRADOS = ("recusada", "fechado")

#: Domínios que não identificam a empresa: sites de vaga, ATS e provedores de e-mail.
_GENERICOS = DOMINIOS_GRATIS_E_SEM_LIMITE + (
    "linkedin.com", "workana.com", "99freelas.com.br", "freelancer.com", "upwork.com", "himalayas.app",
    "remotive.com", "remoteok.com", "jobicy.com", "weworkremotely.com", "getonbrd.com", "github.com",
    "ycombinator.com", "gmail.com", "outlook.com", "hotmail.com", "yahoo.com",
)
_FRONTMATTER = re.compile(r"\A---\r?\n(?P<campos>.*?)\r?\n---", re.S)


@dataclass(frozen=True)
class Candidatura:
    titulo: str
    empresa: str
    link: str
    status: str
    origem: str
    quando: str = ""
    nota: str = ""


def ler_pacotes(vault: Path) -> list[Candidatura]:
    pasta = Path(vault) / PASTA_CACADA
    saida = []
    for arquivo in sorted(pasta.glob("*/*.md")) if pasta.is_dir() else ():
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        casou = _FRONTMATTER.match(texto)
        if casou is None:
            continue
        campos = {}
        for linha in casou["campos"].splitlines():
            chave, _, valor = linha.partition(":")
            campos[chave.strip()] = valor.strip().strip('"')
        if campos.get("tipo") != "pacote":
            continue
        saida.append(
            Candidatura(
                titulo=campos.get("titulo") or arquivo.stem,
                empresa=campos.get("empresa", ""),
                link=campos.get("link", ""),
                status=(campos.get("status") or PREPARADA).casefold(),
                origem="você",
                quando=arquivo.parent.name[:10],
                nota=arquivo.relative_to(vault).as_posix(),
            )
        )
    return saida


def ler_enviadas_pelo_whis(registro) -> list[Candidatura]:
    from .acoes import CANDIDATURA, FEITO

    return [
        Candidatura(titulo=acao.rotulo or acao.alvo, empresa="", link=acao.alvo, status="enviada", origem="Whis", quando=acao.quando[:10])
        for acao in registro.acoes()
        if acao.tipo == CANDIDATURA and acao.estado == FEITO
    ]


def respostas_de(candidatura: Candidatura, mensagens: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    """Os e-mails que parecem ser da empresa: domínio próprio igual ao da vaga, ou o nome dela citado."""
    host = dominio(candidatura.link)
    proprio = "" if casa(host, _GENERICOS) else ".".join(host.split(".")[-2:])
    nome = candidatura.empresa.strip().casefold()
    achadas = []
    for mensagem in mensagens:
        remetente = str(mensagem.get("remetente", "")).casefold()
        assunto = str(mensagem.get("assunto", "")).casefold()
        if proprio and remetente.endswith("@" + proprio) or (proprio and remetente.endswith("." + proprio)):
            achadas.append(mensagem)
        elif len(nome) >= 4 and (nome in assunto or nome.replace(" ", "") in remetente):
            achadas.append(mensagem)
    return achadas


def montar_candidaturas(
    candidaturas: Iterable[Candidatura], mensagens: Sequence[dict[str, str]], quando: datetime
) -> str:
    lista = list(candidaturas)
    grupos = {
        "Em andamento": [c for c in lista if c.status in ABERTOS],
        "Preparadas, esperando você enviar": [c for c in lista if c.status == PREPARADA],
        "Encerradas": [c for c in lista if c.status in ENCERRADOS],
    }
    linhas = [
        "---",
        "tipo: candidaturas",
        f"atualizada: {quando.isoformat(timespec='minutes')}",
        "---",
        "",
        "# Candidaturas",
        "",
        "Regenerada a cada caçada. Para mudar o andamento de uma chance boa, troque o `status:` no pacote "
        "(`preparada` → `enviada` → `entrevista` / `proposta` → `recusada` / `fechado`).",
        "",
    ]
    for titulo, itens in grupos.items():
        linhas += [f"## {titulo} ({len(itens)})", ""]
        if not itens:
            linhas += ["_Nenhuma._", ""]
            continue
        linhas += ["| Quando | Vaga ou freela | Por | Status | Resposta no Gmail |", "|---|---|---|---|---|"]
        for c in sorted(itens, key=lambda c: c.quando, reverse=True):
            respostas = respostas_de(c, mensagens)
            resposta = "; ".join(f"{r.get('quando', '')[:10]} {r.get('assunto', '')}" for r in respostas[:2]) or "—"
            nome = f"[[{c.nota.removesuffix('.md')}\\|{_seguro(c.titulo)}]]" if c.nota else f"[{_seguro(c.titulo)}]({c.link})"
            empresa = f" — {_seguro(c.empresa)}" if c.empresa else ""
            linhas.append(f"| {c.quando} | {nome}{empresa} | {c.origem} | {c.status} | {_seguro(resposta)} |")
        linhas.append("")
    return "\n".join(linhas)


def atualizar(vault: Path, *, registro=None, mensagens: Sequence[dict[str, str]] = (), quando: datetime | None = None) -> str:
    candidaturas = ler_pacotes(vault) + (ler_enviadas_pelo_whis(registro) if registro is not None else [])
    texto = montar_candidaturas(candidaturas, mensagens, quando or datetime.now().astimezone())
    _vault.escrever(Path(vault), CAMINHO_DAS_CANDIDATURAS, texto, zonas=(PASTA_CACADA,))
    return CAMINHO_DAS_CANDIDATURAS


def _seguro(texto: str) -> str:
    return texto.replace("|", "/").replace("\n", " ")
