"""As ferramentas que o agente recebe no lugar do vault cru.

O agente **não** recebe `cwd` no vault, nem shell, nem leitura de arquivo.
Recebe este objeto, e é aqui que a fronteira mora: nenhuma ferramenta abre
nada fora do vault, nenhuma abre nada sob `[privacidade].pastas_privadas`, e
nenhuma escreve. A checagem é uma função só, `_visivel`, no caminho
**resolvido** — como `vault.escrever` já faz para a zona de propriedade —, então
`..` no meio do caminho não escapa e um link simbólico não atravessa.

Um arquivo privado **não existe** para o agente. A recusa é a mesma para o que
está fora do vault, para o que está sob pasta privada e para o que simplesmente
não está lá: dizer "isso é privado" já contaria que há algo escondido, que é
metade do que a pasta promete esconder.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .configuracao import Configuracao

_log = logging.getLogger("whis.ferramentas")

#: O que a busca varre: as notas do vault. Anexos e imagens ficam de fora.
EXTENSAO_DE_NOTA = ".md"

#: Quantos caracteres de uma linha um `Achado` carrega — o bastante para o
#: agente decidir se abre a nota, sem mandar a nota inteira a cada busca.
TAMANHO_DO_TRECHO = 200


@dataclass(frozen=True)
class Achado:
    """Uma linha do vault que casou com o termo buscado."""

    caminho: str
    linha: int
    trecho: str


class ForaDaFronteira(RuntimeError):
    """O caminho não existe para o agente.

    Fora do vault, sob pasta privada ou simplesmente inexistente: a mensagem é
    a mesma nos três casos, de propósito.
    """


class LimiteDeNotas(RuntimeError):
    """A pergunta já leu `[busca].maximo_de_notas` notas distintas.

    É o freio de uma pergunta varrer o vault inteiro. O adaptador traduz para o
    modelo como "responda com o que já leu"; reler uma nota já aberta não conta.
    """


class Ferramentas:
    """O vault como o agente o enxerga: busca, leitura e listagem, nada mais.

    Nasce por pergunta: o contador de notas lidas vale para uma pergunta só.
    """

    def __init__(self, configuracao: Configuracao) -> None:
        self._raiz = Path(configuracao.vault).resolve()
        self._privadas = tuple(
            (self._raiz / pasta).resolve() for pasta in configuracao.privacidade_pastas_privadas
        )
        self._maximo_de_notas = configuracao.busca_maximo_de_notas
        self._lidas: set[Path] = set()

    @property
    def notas_lidas(self) -> int:
        """Quantas notas distintas esta pergunta já abriu."""
        return len(self._lidas)

    def buscar_no_vault(self, termo: str, *, limite: int = 30) -> tuple[Achado, ...]:
        """As linhas do vault em que todas as palavras de `termo` aparecem.

        Sem diferenciar maiúsculas nem acento — "retencao" acha "retenção".
        Dentro de cada pasta a nota mais recente vem primeiro, porque os nomes
        datados do vault ordenam por data e o que aconteceu ontem costuma ser a
        resposta.
        """
        palavras = _normalizar(termo).split()
        if not palavras:
            return ()
        achados: list[Achado] = []
        for nota in self._notas():
            try:
                linhas = nota.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for numero, linha in enumerate(linhas, 1):
                if _casa(palavras, linha):
                    achados.append(Achado(self._relativo(nota), numero, _trecho(linha)))
                    if len(achados) >= limite:
                        return tuple(achados)
        return tuple(achados)

    def ler_nota(self, caminho: str) -> str:
        """O conteúdo de uma nota, contado no teto da pergunta."""
        alvo = self._dentro_da_fronteira(caminho)
        if not alvo.is_file():
            raise ForaDaFronteira(_inexistente(caminho))
        if alvo not in self._lidas and len(self._lidas) >= self._maximo_de_notas:
            raise LimiteDeNotas(
                f"Esta pergunta já leu {self._maximo_de_notas} notas, o máximo "
                f"configurado em [busca].maximo_de_notas. Responda com o que já leu."
            )
        texto = alvo.read_text(encoding="utf-8", errors="replace")
        self._lidas.add(alvo)
        return texto

    def listar(self, pasta: str = "") -> tuple[str, ...]:
        """As entradas de uma pasta do vault, com `/` no fim das subpastas."""
        alvo = self._dentro_da_fronteira(pasta, raiz_permitida=True)
        if not alvo.is_dir():
            raise ForaDaFronteira(_inexistente(pasta))
        entradas: list[str] = []
        for filho in sorted(alvo.iterdir()):
            if _oculto(filho.name) or not self._visivel(filho):
                continue
            relativo = self._relativo(filho)
            entradas.append(f"{relativo}/" if filho.is_dir() else relativo)
        return tuple(entradas)

    def _dentro_da_fronteira(self, caminho: str, *, raiz_permitida: bool = False) -> Path:
        texto = str(caminho).strip().replace("\\", "/")
        relativo = Path(texto) if texto else Path()
        if relativo.is_absolute() or texto.startswith("/"):
            raise ForaDaFronteira(_inexistente(caminho))
        alvo = (self._raiz / relativo).resolve()
        if alvo == self._raiz:
            if raiz_permitida:
                return alvo
            raise ForaDaFronteira(_inexistente(caminho))
        if not self._visivel(alvo):
            _log.debug("Fora da fronteira: %r", caminho)
            raise ForaDaFronteira(_inexistente(caminho))
        return alvo

    def _visivel(self, alvo: Path) -> bool:
        """A checagem única: dentro do vault e fora de toda pasta privada."""
        resolvido = alvo.resolve()
        if resolvido != self._raiz and not resolvido.is_relative_to(self._raiz):
            return False
        return not any(
            resolvido == privada or resolvido.is_relative_to(privada)
            for privada in self._privadas
        )

    def _notas(self) -> list[Path]:
        notas = [
            nota
            for nota in self._raiz.rglob(f"*{EXTENSAO_DE_NOTA}")
            if nota.is_file()
            and not any(_oculto(parte) for parte in nota.relative_to(self._raiz).parts)
            and self._visivel(nota)
        ]
        return sorted(notas, key=self._relativo, reverse=True)

    def _relativo(self, alvo: Path) -> str:
        return alvo.resolve().relative_to(self._raiz).as_posix()


def _inexistente(caminho: str) -> str:
    return f"Não existe no vault: {str(caminho).strip()!r}"


def _oculto(nome: str) -> bool:
    """`.obsidian/`, `.trash/` e afins são do Obsidian, não notas."""
    return nome.startswith(".")


def _normalizar(texto: str) -> str:
    sem_acento = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caractere)
    )
    return sem_acento.casefold()


def _casa(palavras: list[str], linha: str) -> bool:
    normalizada = _normalizar(linha)
    return all(palavra in normalizada for palavra in palavras)


def _trecho(linha: str) -> str:
    limpa = linha.strip()
    if len(limpa) <= TAMANHO_DO_TRECHO:
        return limpa
    return limpa[: TAMANHO_DO_TRECHO - 1] + "…"
