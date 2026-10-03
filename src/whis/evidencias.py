"""As evidências do perfil: o que a máquina dele já sabe, lido em Python e de graça.

O vault guarda o trabalho do dia, não o profissional (research 03): dá o tipo
de problema e o domínio, mas mal a stack e nada da senioridade. Por isso o
perfil relê as fontes passivas — os repositórios de `[git].raiz` dão as
linguagens (pelas extensões), os frameworks (pelos manifestos), os anos de
histórico e quantos commits são dele — e junta o diário, as reuniões e as
cópias da daily mais recentes. Tudo vira um texto que só o adaptador do
perfil lê; o resumo que sai dele abstrai o empregador.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import tomllib
from collections import Counter
from pathlib import Path

from .configuracao import Configuracao

_log = logging.getLogger("whis.evidencias")

TETO_DE_CARACTERES = 45_000
NOTAS_DO_DIARIO = 15
COPIAS_DA_DAILY = 6
TITULOS_DE_REUNIAO = 40
TAMANHO_POR_NOTA = 1_800
_SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

#: Extensão → linguagem, só o que diz algo de stack.
LINGUAGENS = {
    ".ts": "TypeScript", ".tsx": "TypeScript (React)", ".js": "JavaScript", ".jsx": "JavaScript (React)",
    ".vue": "Vue", ".svelte": "Svelte", ".py": "Python", ".php": "PHP", ".rb": "Ruby", ".go": "Go",
    ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".cs": "C#", ".cpp": "C++", ".c": "C", ".swift": "Swift",
    ".dart": "Dart", ".sql": "SQL", ".css": "CSS", ".scss": "SCSS", ".html": "HTML", ".gd": "GDScript",
    ".lua": "Lua", ".ex": "Elixir", ".tf": "Terraform", ".sh": "Shell", ".ps1": "PowerShell",
}
MANIFESTOS = ("package.json", "pyproject.toml", "requirements.txt", "composer.json", "go.mod", "Cargo.toml", "Gemfile")


def montar_evidencias(configuracao: Configuracao, *, claude_code: Path | None = None) -> str:
    """O texto inteiro das evidências, cortado no teto. Nunca levanta: o que falhar vira uma linha."""
    partes = [_do_git(configuracao), _do_claude_code(claude_code), _do_vault(Path(configuracao.vault))]
    texto = "\n\n".join(parte for parte in partes if parte.strip())
    return texto[:TETO_DE_CARACTERES] or "(nenhuma evidência: git desligado e vault vazio)"


# -- git ------------------------------------------------------------------------------------


def _do_git(configuracao: Configuracao) -> str:
    if configuracao.git_raiz is None:
        return "GIT: desligado ([git].raiz vazio)."
    from .fonte_git import de_configuracao

    try:
        repositorios = de_configuracao(configuracao).repositorios()
    except Exception as erro:  # noqa: BLE001
        return f"GIT: não deu para varrer ({erro})."
    linhas = [f"GIT: {len(repositorios)} repositório(s) em [git].raiz."]
    linguagens_dele: Counter[str] = Counter()
    for repositorio in repositorios:
        try:
            linhas.append(_repositorio(repositorio, configuracao.git_autores, linguagens_dele))
        except Exception as erro:  # noqa: BLE001 — um repositório não derruba o perfil
            linhas.append(f"- {repositorio.name}: não lido ({erro})")
    if linguagens_dele:
        total = sum(linguagens_dele.values())
        linhas.insert(
            1,
            "Linguagens nos repositórios em que ele commitou (arquivos versionados): "
            + ", ".join(f"{nome} {100 * n // total}%" for nome, n in linguagens_dele.most_common(12)),
        )
    return "\n".join(linhas)


def _repositorio(repositorio: Path, autores: tuple[str, ...], linguagens_dele: Counter[str]) -> str:
    emails = autores or tuple(e for e in (_git(repositorio, "config", "user.email").strip(),) if e)
    datas: list[str] = []
    if emails:
        argumentos = ["log", "--all", "--no-merges", "--fixed-strings", "--regexp-ignore-case", "--pretty=format:%aI"]
        argumentos += [f"--author={email}" for email in emails]
        datas = [linha for linha in _git(repositorio, *argumentos).splitlines() if linha.strip()]
    arquivos = _git(repositorio, "ls-files").splitlines()
    extensoes = Counter(LINGUAGENS[Path(a).suffix.lower()] for a in arquivos if Path(a).suffix.lower() in LINGUAGENS)
    if datas:
        linguagens_dele.update(extensoes)
    remoto = _git(repositorio, "remote", "get-url", "origin").strip()
    host = re.sub(r"^(?:https?://|git@)([^/:]+).*$", r"\1", remoto) if remoto else "sem remote"
    dominio = emails[0].split("@")[-1] if emails else "?"
    periodo = f"{min(datas)[:10]} a {max(datas)[:10]}" if datas else "nenhum commit dele"
    principais = ", ".join(nome for nome, _ in extensoes.most_common(5)) or "?"
    frameworks = _frameworks(repositorio)
    return (
        f"- {repositorio.name}: {len(datas)} commit(s) dele ({periodo}); e-mail do autor em @{dominio}; "
        f"remote em {host}; linguagens: {principais}"
        + (f"; dependências: {frameworks}" if frameworks else "")
    )


def _frameworks(repositorio: Path) -> str:
    nomes: list[str] = []
    for manifesto in MANIFESTOS:
        arquivo = repositorio / manifesto
        if not arquivo.is_file():
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if manifesto == "package.json":
            try:
                dados = json.loads(texto)
            except ValueError:
                continue
            for chave in ("dependencies", "devDependencies"):
                nomes += list((dados.get(chave) or {}).keys())
        elif manifesto == "pyproject.toml":
            try:
                dados = tomllib.loads(texto)
            except tomllib.TOMLDecodeError:
                continue
            for dependencia in (dados.get("project") or {}).get("dependencies") or []:
                nomes.append(re.split(r"[<>=!~\[ ;]", str(dependencia), maxsplit=1)[0])
        elif manifesto == "requirements.txt":
            nomes += [re.split(r"[<>=!~\[ ;]", linha, maxsplit=1)[0] for linha in texto.splitlines() if linha.strip() and not linha.startswith("#")]
        elif manifesto == "composer.json":
            try:
                nomes += list((json.loads(texto).get("require") or {}).keys())
            except ValueError:
                continue
        else:
            nomes.append(manifesto)
    unicos = list(dict.fromkeys(n.strip() for n in nomes if n.strip()))
    return ", ".join(unicos[:25])


def _git(repositorio: Path, *argumentos: str) -> str:
    try:
        concluido = subprocess.run(
            ["git", "-C", str(repositorio), *argumentos],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            creationflags=_SEM_JANELA,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return concluido.stdout or "" if concluido.returncode == 0 else ""


# -- Claude Code ----------------------------------------------------------------------------

DIAS_DO_CLAUDE_CODE = 30


def _do_claude_code(pasta: Path | None = None, *, agora: float | None = None) -> str:
    """Como ele trabalha com IA, só em contagens (research 03): nada de texto, código ou nome de projeto.

    Os transcripts (`~/.claude/projects/<projeto>/<sessão>.jsonl`) carregam o
    código do empregador; daqui só saem números — sessões, projetos, as
    ferramentas mais usadas, as extensões dos arquivos editados e as skills.
    """
    import time

    pasta = pasta or Path.home() / ".claude" / "projects"
    if not pasta.is_dir():
        return ""
    limite = (agora or time.time()) - DIAS_DO_CLAUDE_CODE * 86_400
    sessoes, projetos = 0, set()
    ferramentas: Counter[str] = Counter()
    extensoes: Counter[str] = Counter()
    skills: Counter[str] = Counter()
    for arquivo in pasta.glob("*/*.jsonl"):
        try:
            if arquivo.stat().st_mtime < limite:
                continue
            linhas = arquivo.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        sessoes += 1
        projetos.add(arquivo.parent.name)
        for linha in linhas:
            if '"tool_use"' not in linha:
                continue
            try:
                registro = json.loads(linha)
            except ValueError:
                continue
            conteudo = ((registro.get("message") or {}).get("content")) if isinstance(registro, dict) else None
            for bloco in conteudo if isinstance(conteudo, list) else ():
                if not isinstance(bloco, dict) or bloco.get("type") != "tool_use":
                    continue
                nome = str(bloco.get("name", ""))
                entrada = bloco.get("input") if isinstance(bloco.get("input"), dict) else {}
                ferramentas["MCP" if nome.startswith("mcp__") else nome] += 1
                caminho = str(entrada.get("file_path") or "")
                if nome in ("Edit", "Write", "MultiEdit", "NotebookEdit") and caminho:
                    extensoes[Path(caminho).suffix.lower() or "(sem extensão)"] += 1
                if nome == "Skill" and entrada.get("skill"):
                    skills[str(entrada["skill"]).split(":")[-1]] += 1
    if not sessoes:
        return ""
    def top(contador: Counter[str], n: int) -> str:
        return ", ".join(f"{nome} {quantos}" for nome, quantos in contador.most_common(n)) or "—"

    return (
        f"CLAUDE CODE (últimos {DIAS_DO_CLAUDE_CODE} dias, só contagens): {sessoes} sessão(ões) em "
        f"{len(projetos)} projeto(s). Ferramentas: {top(ferramentas, 10)}. Extensões editadas: "
        f"{top(extensoes, 10)}. Skills: {top(skills, 8)}."
    )


# -- vault ----------------------------------------------------------------------------------


def _do_vault(vault: Path) -> str:
    partes = []
    diario = _mais_recentes(vault / "diario", NOTAS_DO_DIARIO)
    if diario:
        partes.append("DIÁRIO (mais recentes primeiro):\n" + "\n\n".join(_trecho(nota) for nota in diario))
    daily = [nota for nota in _mais_recentes(vault / "daily", COPIAS_DA_DAILY + 1) if nota.name != "atual.md"]
    atual = vault / "daily" / "atual.md"
    if atual.is_file():
        daily.insert(0, atual)
    if daily:
        partes.append("DAILY (o que ele mesmo escreveu):\n" + "\n\n".join(_trecho(nota) for nota in daily[:COPIAS_DA_DAILY]))
    reunioes = _mais_recentes(vault / "reunioes", TITULOS_DE_REUNIAO)
    if reunioes:
        partes.append("REUNIÕES (só os títulos): " + "; ".join(_titulo(nota) for nota in reunioes))
    if not partes:
        return "VAULT: nada de diário, daily ou reuniões ainda."
    return "\n\n".join(partes)


def _mais_recentes(pasta: Path, quantas: int) -> list[Path]:
    if not pasta.is_dir():
        return []
    notas = [nota for nota in pasta.glob("*.md") if nota.is_file()]
    return sorted(notas, key=lambda nota: nota.name, reverse=True)[:quantas]


def _trecho(nota: Path) -> str:
    try:
        texto = nota.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return f"[{nota.name}: ilegível]"
    texto = re.sub(r"^---\n.*?\n---\n", "", texto, flags=re.S).strip()
    return f"[{nota.stem}]\n{texto[:TAMANHO_POR_NOTA]}"


def _titulo(nota: Path) -> str:
    try:
        for linha in nota.read_text(encoding="utf-8", errors="replace").splitlines():
            if linha.startswith("# "):
                return linha[2:].strip()
    except OSError:
        pass
    return nota.stem
