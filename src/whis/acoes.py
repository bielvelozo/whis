r"""O registro de ações externas: tudo o que o Whis fez fora do PC em nome dele.

Só acrescenta (JSON Lines em `%LOCALAPPDATA%\whis\cacada\acoes.jsonl`), nunca
reescreve. Cada ação nasce como **intenção**, gravada *antes* de agir, e ganha
uma segunda linha com o desfecho: `feito`, `precisa_de_voce` ou `falhou`
(research 07). Uma intenção sem desfecho — o processo morreu no meio — **nunca
é refeita sozinha**: vira "conferir" no relatório, porque não dá para saber se
a candidatura saiu. E qualquer linha para o mesmo tipo e alvo impede repetir:
o Whis não se candidata duas vezes à mesma vaga, em semana nenhuma.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .oportunidades import link_canonico

NOME_DO_REGISTRO = "acoes.jsonl"

INTENCAO = "intencao"
FEITO = "feito"
PRECISA_DE_VOCE = "precisa_de_voce"
FALHOU = "falhou"

CANDIDATURA = "candidatura"
CONTA = "conta"
PERFIL = "perfil"
CONFIRMACAO = "confirmacao"
POST = "post"


@dataclass(frozen=True)
class Acao:
    id: str
    tipo: str
    alvo: str
    estado: str
    quando: str
    detalhe: str = ""
    texto: str = ""
    rotulo: str = ""

    @property
    def sem_desfecho(self) -> bool:
        return self.estado == INTENCAO


class Registro:
    def __init__(self, pasta: Path) -> None:
        self.arquivo = Path(pasta) / NOME_DO_REGISTRO

    def intencao(self, tipo: str, alvo: str, *, texto: str = "", detalhe: str = "") -> str:
        id_ = secrets.token_hex(6)
        self._acrescentar({"id": id_, "tipo": tipo, "alvo": _alvo(alvo), "estado": INTENCAO, "texto": texto, "detalhe": detalhe})
        return id_

    def concluir(self, id_: str, estado: str, detalhe: str = "") -> None:
        anterior = next((a for a in self._linhas() if a.get("id") == id_), {})
        self._acrescentar(
            {"id": id_, "tipo": anterior.get("tipo", ""), "alvo": anterior.get("alvo", ""), "estado": estado, "detalhe": detalhe}
        )

    def ja_tentado(self, tipo: str, alvo: str) -> bool:
        alvo = _alvo(alvo)
        return any(linha.get("tipo") == tipo and linha.get("alvo") == alvo for linha in self._linhas())

    def acoes(self) -> list[Acao]:
        """O estado mais recente de cada ação, na ordem em que nasceram."""
        ultimas: dict[str, dict] = {}
        primeiras: dict[str, dict] = {}
        for linha in self._linhas():
            id_ = str(linha.get("id", ""))
            primeiras.setdefault(id_, linha)
            ultimas[id_] = linha
        return [
            Acao(
                id=id_,
                tipo=str(primeiras[id_].get("tipo", "")),
                alvo=str(primeiras[id_].get("alvo", "")),
                estado=str(ultima.get("estado", "")),
                quando=str(primeiras[id_].get("quando", "")),
                detalhe=str(ultima.get("detalhe", "")),
                texto=str(primeiras[id_].get("texto", "")),
                rotulo=str(primeiras[id_].get("detalhe", "")),
            )
            for id_, ultima in ultimas.items()
        ]

    def _acrescentar(self, dados: dict) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        dados = {"quando": datetime.now().astimezone().isoformat(timespec="seconds"), **dados}
        with self.arquivo.open("a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(dados, ensure_ascii=False) + "\n")
            arquivo.flush()

    def _linhas(self) -> list[dict]:
        if not self.arquivo.is_file():
            return []
        linhas = []
        for texto in self.arquivo.read_text(encoding="utf-8").splitlines():
            try:
                dados = json.loads(texto)
            except ValueError:
                continue
            if isinstance(dados, dict):
                linhas.append(dados)
        return linhas


def _alvo(alvo: str) -> str:
    return link_canonico(alvo) if alvo.startswith(("http://", "https://")) else alvo.strip().casefold()
