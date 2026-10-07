"""O Quiz da semana como notas do vault: `noticias/quiz/AAAA-MM-DD.md`.

Uma pergunta nova por aula lida desde o último quiz, mais as que ele errou ou
deixou em branco antes, até acertar. A pergunta que volta ganha id novo e leva
em `origem` o id da primeira vez; ela sai da fila quando qualquer versão dela é
acertada. O que `montar_nota_do_quiz` escreve, `ler_nota_do_quiz` lê igual.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from . import vault as _vault
from .aulas import LIDA, NotaDeAula
from .portas import PerguntaNova, Resposta

PASTA_DOS_QUIZZES = "noticias/quiz"

CERTA = "certa"
ERRADA = "errada"
SEM_RESPOSTA = "sem resposta"

LIMITE_DAS_ATRASADAS = 10

_VISTO = " ✓"
_FRONTMATTER = re.compile(r"\A---\n(?P<campos>.*?)\n---[ \t]*(?:\n|\Z)", re.S)
_TITULO_DA_PERGUNTA = re.compile(r"## \d+\. ?(?P<texto>.*)")
_COMENTARIO = re.compile(r"<!-- (?P<campos>id:.*) -->")
_ALTERNATIVA = re.compile(r"- \S\)(?: (?P<texto>.*))?")


@dataclass(frozen=True)
class Pergunta:
    """Uma pergunta de múltipla escolha; `certa` é o índice em `alternativas`.

    `origem` é o id da primeira vez que a pergunta apareceu (vazio se é a
    primeira); `resultado` é `certa`, `errada`, `sem resposta` ou vazio.
    """

    id: str
    aula: str
    pergunta: str
    alternativas: tuple[str, ...]
    certa: int
    explicacao: str
    origem: str = ""
    resultado: str = ""


@dataclass(frozen=True)
class QuizDaSemana:
    data: date
    perguntas: tuple[Pergunta, ...]
    aviso: str = ""


def montar_nota_do_quiz(quiz: QuizDaSemana) -> str:
    linhas = [f"# Quiz da semana — {quiz.data.strftime('%d/%m/%Y')}", ""]
    if quiz.aviso:
        linhas += [f"> {linha}" for linha in quiz.aviso.split("\n")] + [""]
    for numero, pergunta in enumerate(quiz.perguntas, start=1):
        linhas += [
            f"## {numero}. {pergunta.pergunta}",
            f"<!-- id: {pergunta.id} · aula: {pergunta.aula} · origem: {pergunta.origem} · certa: {pergunta.certa} -->",
            "",
        ]
        for i, alternativa in enumerate(pergunta.alternativas):
            visto = _VISTO if i == pergunta.certa else ""
            linhas.append(f"- {chr(ord('a') + i)}) {alternativa}{visto}")
        linhas += ["", f"Explicação: {pergunta.explicacao}", f"Resultado: {pergunta.resultado}", ""]
    campos = {"tipo": "quiz", "data": quiz.data.isoformat()}
    return _vault._frontmatter(campos) + "\n".join(linhas).rstrip("\n") + "\n"


def ler_nota_do_quiz(texto: str) -> QuizDaSemana | None:
    """O quiz escrito por `montar_nota_do_quiz`; `None` se não for uma nota de quiz.

    A alternativa certa vem do comentário de cada pergunta; o visto só vale
    quando o comentário não diz. Pergunta que não dá para ler é pulada.
    """
    texto = texto.removeprefix("﻿").replace("\r\n", "\n")
    cabecalho = _FRONTMATTER.match(texto)
    if cabecalho is None:
        return None
    campos = _campos(cabecalho["campos"])
    if campos.get("tipo") != "quiz":
        return None
    try:
        data = date.fromisoformat(campos.get("data", ""))
    except ValueError:
        return None

    aviso: list[str] = []
    blocos: list[list[str]] = []
    for linha in texto[cabecalho.end():].split("\n"):
        if (titulo := _TITULO_DA_PERGUNTA.fullmatch(linha)) is not None:
            blocos.append([titulo["texto"]])
        elif blocos:
            blocos[-1].append(linha)
        elif linha.startswith(">"):
            aviso.append(linha[2:] if linha.startswith("> ") else linha[1:])
    perguntas = tuple(p for p in (_ler_pergunta(bloco) for bloco in blocos) if p is not None)
    return QuizDaSemana(data, perguntas, aviso="\n".join(aviso))


def ler_quizzes(vault: Path) -> list[QuizDaSemana]:
    """Todos os quizzes do vault, do mais antigo para o mais novo."""
    pasta = Path(vault) / PASTA_DOS_QUIZZES
    quizzes = []
    for arquivo in pasta.glob("*.md") if pasta.is_dir() else ():
        try:
            texto = arquivo.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        quiz = ler_nota_do_quiz(texto)
        if quiz is not None:
            quizzes.append(quiz)
    return sorted(quizzes, key=lambda quiz: quiz.data)


def escrever_quiz(vault: Path, quiz: QuizDaSemana) -> Path:
    return _vault.escrever(
        vault,
        f"{PASTA_DOS_QUIZZES}/{quiz.data.isoformat()}.md",
        montar_nota_do_quiz(quiz),
        zonas=_vault.ZONAS_DO_JORNAL,
    )


def aplicar_respostas(
    quizzes: Sequence[QuizDaSemana], respostas: Mapping[str, Resposta], hoje: date
) -> list[QuizDaSemana]:
    """A resposta marcada vira `certa` ou `errada`; sem resposta, o quiz que já passou vira `sem resposta`.

    O quiz de hoje ainda pode ser respondido, então o que está vazio fica vazio.
    O que não muda volta como a mesma instância.
    """
    novos = []
    for quiz in quizzes:
        perguntas = tuple(
            _com_resultado(pergunta, respostas.get(pergunta.id), passou=quiz.data < hoje)
            for pergunta in quiz.perguntas
        )
        novos.append(quiz if perguntas == tuple(quiz.perguntas) else replace(quiz, perguntas=perguntas))
    return novos


def atrasadas(
    quizzes: Sequence[QuizDaSemana], hoje: date, limite: int = LIMITE_DAS_ATRASADAS
) -> list[Pergunta]:
    """As perguntas de quizzes anteriores que ele ainda não acertou, prontas para voltar.

    As versões de uma mesma pergunta se juntam pela raiz (`origem`, ou o
    próprio id na primeira vez); basta uma versão certa para a pergunta sair.
    Volta o texto da versão mais recente, sem id nem resultado e com a raiz em
    `origem`, na ordem em que as perguntas apareceram pela primeira vez.
    """
    versoes: dict[str, list[Pergunta]] = {}
    for quiz in sorted((quiz for quiz in quizzes if quiz.data < hoje), key=lambda quiz: quiz.data):
        for pergunta in quiz.perguntas:
            versoes.setdefault(pergunta.origem or pergunta.id, []).append(pergunta)
    em_aberto = [(raiz, lista[-1]) for raiz, lista in versoes.items() if all(p.resultado != CERTA for p in lista)]
    return [replace(pergunta, id="", resultado="", origem=raiz) for raiz, pergunta in em_aberto[: max(0, limite)]]


def aulas_do_quiz(notas: Sequence[NotaDeAula]) -> list[NotaDeAula]:
    """As aulas lidas que ainda não entraram em nenhum quiz, pelo id."""
    return sorted((nota for nota in notas if nota.status == LIDA and not nota.quiz), key=lambda nota: nota.id)


def novo_quiz(hoje: date, novas: Sequence[PerguntaNova], atrasadas: Sequence[Pergunta]) -> QuizDaSemana:
    """As perguntas novas e depois as atrasadas, numeradas `AAAA-MM-DD-q1`, `-q2`…"""
    perguntas = [
        Pergunta(
            id="",
            aula=nova.aula,
            pergunta=nova.pergunta,
            alternativas=tuple(nova.alternativas),
            certa=nova.certa,
            explicacao=nova.explicacao,
        )
        for nova in novas
    ] + [replace(antiga, resultado="", origem=antiga.origem or antiga.id) for antiga in atrasadas]
    numeradas = tuple(replace(pergunta, id=f"{hoje.isoformat()}-q{n}") for n, pergunta in enumerate(perguntas, start=1))
    return QuizDaSemana(hoje, numeradas)


def _com_resultado(pergunta: Pergunta, resposta: Resposta | None, *, passou: bool) -> Pergunta:
    if resposta is not None:
        resultado = CERTA if resposta.certa else ERRADA
    elif passou and not pergunta.resultado:
        resultado = SEM_RESPOSTA
    else:
        return pergunta
    return pergunta if resultado == pergunta.resultado else replace(pergunta, resultado=resultado)


def _ler_pergunta(bloco: list[str]) -> Pergunta | None:
    """Um bloco `## N. …`: a primeira linha já sem o título, e as seguintes até a próxima pergunta."""
    comentario = next((i for i, linha in enumerate(bloco) if i and _COMENTARIO.fullmatch(linha)), None)
    if comentario is None:
        return None
    dados = _campos_do_comentario(_COMENTARIO.fullmatch(bloco[comentario])["campos"])
    if not dados.get("id"):
        return None

    resto = bloco[comentario + 1:]
    alternativas: list[str] = []
    fim_das_alternativas = 0
    for i, linha in enumerate(resto):
        casou = _ALTERNATIVA.fullmatch(linha)
        if casou is not None:
            alternativas.append(casou["texto"] or "")
            fim_das_alternativas = i + 1
        elif linha.strip():
            break
    vistos = [i for i, alternativa in enumerate(alternativas) if alternativa.endswith(_VISTO)]
    try:
        certa = int(dados["certa"]) if "certa" in dados else vistos[0]
    except (ValueError, IndexError):
        return None
    if not 0 <= certa < len(alternativas):
        return None
    if alternativas[certa].endswith(_VISTO):
        alternativas[certa] = alternativas[certa][: -len(_VISTO)]

    explicacao, resultado = _explicacao_e_resultado(resto[fim_das_alternativas:])
    return Pergunta(
        id=dados["id"],
        aula=dados.get("aula", ""),
        pergunta="\n".join([bloco[0], *bloco[1:comentario]]),
        alternativas=tuple(alternativas),
        certa=certa,
        explicacao=explicacao,
        origem=dados.get("origem", ""),
        resultado=resultado,
    )


def _explicacao_e_resultado(linhas: list[str]) -> tuple[str, str]:
    """`Explicação:` pode ter várias linhas; `Resultado:` é a última linha com esse começo."""
    resultado = next((i for i in range(len(linhas) - 1, -1, -1) if linhas[i].startswith("Resultado:")), None)
    inicio = next((i for i, linha in enumerate(linhas) if linha.startswith("Explicação:")), None)
    texto_do_resultado = linhas[resultado][len("Resultado:"):].strip() if resultado is not None else ""
    if inicio is None:
        return "", texto_do_resultado
    fim = resultado if resultado is not None and resultado > inicio else len(linhas)
    primeira = linhas[inicio][len("Explicação:"):].removeprefix(" ")
    explicacao = "\n".join([primeira, *linhas[inicio + 1:fim]])
    if resultado is None:
        explicacao = explicacao.rstrip("\n")
    return explicacao, texto_do_resultado


def _campos_do_comentario(texto: str) -> dict[str, str]:
    campos = {}
    for parte in texto.split(" · "):
        chave, separador, valor = parte.partition(":")
        if separador:
            campos[chave.strip()] = valor.strip()
    return campos


def _campos(bloco: str) -> dict[str, str]:
    campos = {}
    for linha in bloco.splitlines():
        chave, separador, valor = linha.partition(":")
        if separador:
            campos[chave.strip()] = valor.strip().strip('"').strip("'")
    return campos
