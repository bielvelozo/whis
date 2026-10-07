"""Sonda descartável do ticket 01: o banco do artifact em headless, na montagem do jornal.

Uso: .venv\\Scripts\\python.exe sonda.py <passo>
Passos: publicar, listar-antes, declarar, listar-vazia, gravar-uma, gravar-cursor,
        republicar-sem, listar-depois, gravar-resposta, listar <colecao>
Cada passo grava saida/<passo>.json; a URL do rascunho fica em saida/estado.json.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ / "src"))

from claude_agent_sdk import SystemMessage  # noqa: E402

from whis.jornal_claude import (  # noqa: E402
    AMBIENTE_DA_PUBLICACAO,
    SISTEMA_PUBLICACAO,
    Conversa,
    _AdaptadorDoJornal,
)

import os  # noqa: E402

FERRAMENTAS_DO_BANCO = os.environ.get("SONDA_FERRAMENTAS", "Artifact,ArtifactData").split(",")

AQUI = Path(__file__).resolve().parent
SAIDA = AQUI / "saida"
ESTADO = SAIDA / "estado.json"


class Sonda(_AdaptadorDoJornal):
    etapa = "sonda"
    erro = RuntimeError

    def __init__(self) -> None:
        super().__init__(modelo="haiku", cli=None, timeout_s=300)
        self.init: dict = {}

    async def _mensagens(self, prompt, opcoes):
        async for mensagem in super()._mensagens(prompt, opcoes):
            if isinstance(mensagem, SystemMessage) and mensagem.subtype == "init":
                self.init = {
                    "tools": list(mensagem.data.get("tools", [])),
                    "claude_code_version": mensagem.data.get("claude_code_version"),
                    "model": mensagem.data.get("model"),
                    "permissionMode": mensagem.data.get("permissionMode"),
                }
            yield mensagem

    def rodar(self, prompt: str, ferramentas: list[str], cwd: Path) -> Conversa:
        opcoes = self._opcoes(
            sistema=SISTEMA_PUBLICACAO,
            ferramentas=ferramentas,
            max_turns=14,
            cwd=cwd,
            ambiente=AMBIENTE_DA_PUBLICACAO,
        )
        return self._conversar(prompt, opcoes)


def estado() -> dict:
    return json.loads(ESTADO.read_text("utf-8")) if ESTADO.is_file() else {}


def guardar_estado(**campos) -> None:
    atual = estado()
    atual.update(campos)
    ESTADO.write_text(json.dumps(atual, ensure_ascii=False, indent=2), "utf-8")


def pagina(versao: str) -> Path:
    destino = SAIDA / "pagina" / "sonda.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text((AQUI / "pagina.html").read_text("utf-8").replace("VERSAO_DA_PAGINA", versao), "utf-8")
    return destino


def registrar(passo: str, sonda: Sonda, conversa: Conversa | None, erro: str = "", extra: dict | None = None) -> None:
    dados = {
        "passo": passo,
        "quando": datetime.now().astimezone().isoformat(timespec="seconds"),
        "init": sonda.init,
        "ferramentas": conversa.ferramentas if conversa else [],
        "resultados_de_ferramenta": conversa.resultados_de_ferramenta if conversa else [],
        "texto_final": conversa.texto_final() if conversa else "",
        "custo_usd": conversa.medida.custo_usd if conversa else None,
        "segundos": conversa.medida.segundos if conversa else None,
        "erro": erro,
        **(extra or {}),
    }
    (SAIDA / f"{passo}.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({k: dados[k] for k in ("passo", "init", "ferramentas", "custo_usd", "segundos", "erro")}, ensure_ascii=False))
    for i, texto in enumerate(dados["resultados_de_ferramenta"]):
        print(f"--- resultado {i} ---\n{texto[:2500]}")
    print(f"--- texto final ---\n{dados['texto_final'][:800]}")


def arquivos_em(pasta: Path) -> dict[str, str]:
    if not pasta.exists():
        return {}
    return {p.relative_to(pasta).as_posix(): p.read_text("utf-8") for p in sorted(pasta.rglob("*")) if p.is_file()}


def executar(passo: str, prompt: str, ferramentas: list[str], cwd: Path, out_dir: Path | None = None) -> None:
    sonda = Sonda()
    try:
        conversa = sonda.rodar(prompt, ferramentas, cwd)
        erro = ""
    except Exception as e:  # noqa: BLE001
        conversa, erro = None, f"{type(e).__name__}: {e}"
    extra = {"arquivos_out_dir": arquivos_em(out_dir)} if out_dir else None
    registrar(passo, sonda, conversa, erro, extra)
    if extra:
        print(f"--- arquivos do out_dir ---\n{json.dumps(extra['arquivos_out_dir'], ensure_ascii=False, indent=2)[:3000]}")


def publicar() -> None:
    html = pagina("v1 sem banco")
    prompt = (
        f"Publique o arquivo {html.as_posix()} como um artifact privado com a ferramenta Artifact: "
        f"action publish, file_path={html.as_posix()}, icon 'flask', description 'Sonda descartável do Whis'. "
        "Não passe capabilities. Não edite nem crie arquivos. Responda SOMENTE com a URL publicada."
    )
    executar("publicar", prompt, ["Artifact", "Read"], html.parent)
    dados = json.loads((SAIDA / "publicar.json").read_text("utf-8"))
    import re

    achadas = re.findall(r"https://claude\.ai/(?:code/)?artifact/[\w-]+", "\n".join(dados["resultados_de_ferramenta"]) + dados["texto_final"])
    if achadas:
        guardar_estado(url=achadas[-1])
        print("URL:", achadas[-1])


def republicar(passo: str, versao: str, capacidades: dict | None) -> None:
    url = estado()["url"]
    html = pagina(versao)
    declaracao = (
        f"capabilities exatamente {json.dumps(capacidades)}" if capacidades is not None else "SEM capabilities"
    )
    prompt = (
        f"Outra sessão publicou o artifact {url}; hoje ele recebe uma versão nova no mesmo endereço.\n"
        f"Passo 1: ferramenta Artifact, action read, url={url}. Espere o resultado.\n"
        f"Passo 2 (só depois do resultado do passo 1): leia {html.as_posix()} com a ferramenta Read. Espere.\n"
        f"Passo 3: ferramenta Artifact, action publish, url={url}, file_path={html.as_posix()}, "
        f"label 'sonda {versao}', {declaracao}. SEM force.\n"
        "Não edite nem crie arquivos. Responda SOMENTE com a URL publicada."
    )
    executar(passo, prompt, ["Artifact", "Read"], html.parent)


def listar(passo: str, colecao: str, limite: int = 1000, cursor: str = "", com_out_dir: bool = True) -> None:
    url = estado()["url"]
    out_dir = SAIDA / f"out-{passo}" if com_out_dir else None
    consulta = {"limit": limite, **({"cursor": cursor} if cursor else {})}
    destino = f", out_dir {out_dir.as_posix()}" if out_dir else ""
    prompt = (
        f"Ferramenta ArtifactData, url={url}. Só leitura: não grave nada.\n"
        f"Faça exatamente UMA chamada: action list, collection {colecao}, query {json.dumps(consulta)}"
        f"{destino}. Não siga cursor. Responda SOMENTE OK."
    )
    executar(passo, prompt, FERRAMENTAS_DO_BANCO, SAIDA, out_dir)


def gravar(passo: str, escritas: list[tuple[str, str, dict]]) -> None:
    url = estado()["url"]
    linhas = "\n".join(
        f"- action set, collection {c}, doc_id {d}, data {json.dumps(dados, ensure_ascii=False)}" for c, d, dados in escritas
    )
    prompt = (
        f"Ferramenta ArtifactData, url={url}. Faça estas escritas, uma chamada por linha, na ordem "
        f"(documentos novos, sem if_version):\n{linhas}\nResponda SOMENTE OK."
    )
    executar(passo, prompt, FERRAMENTAS_DO_BANCO, SAIDA)


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    passo = sys.argv[1]
    agora = datetime.now().astimezone().isoformat(timespec="seconds")
    if passo == "publicar":
        publicar()
    elif passo == "listar-antes":
        listar(passo, "leituras")
    elif passo == "declarar":
        republicar(passo, "v2 com banco", {"db": {}})
    elif passo == "declarar-com-user":
        republicar(passo, "v2b com banco e user", {"db": {}, "user": {}})
    elif passo == "listar-vazia":
        listar(passo, "leituras")
    elif passo == "gravar-uma":
        gravar(passo, [("leituras", "2026-10-06-negocios", {"lida": True, "em": agora})])
    elif passo == "listar-uma":
        listar(passo, "leituras")
    elif passo == "gravar-cursor":
        gravar(passo, [
            ("leituras", "2026-10-06-carros-1", {"lida": True, "em": agora}),
            ("leituras", "2026-10-06-carros-2", {"lida": False, "em": agora}),
        ])
    elif passo == "listar-cursor":
        listar(passo, "leituras", limite=2)
    elif passo == "listar-ultima":
        listar(passo, "leituras", limite=2, cursor=sys.argv[2])
    elif passo == "republicar-sem":
        republicar(passo, "v3 sem declarar de novo", None)
    elif passo == "listar-depois":
        listar(passo, "leituras")
    elif passo == "gravar-resposta":
        gravar(passo, [("respostas", "2026-10-10-q1", {"escolha": 1, "certa": False, "quiz": "2026-10-10", "em": agora})])
    elif passo == "listar-respostas":
        listar(passo, "respostas")
    elif passo == "listar":
        listar(f"listar-{sys.argv[2]}", sys.argv[2])
    elif passo == "listar-sem-out":
        limite = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
        cursor = sys.argv[4] if len(sys.argv) > 4 else ""
        listar(f"listar-sem-out-{sys.argv[2]}-{limite}{'-cursor' if cursor else ''}", sys.argv[2], limite, cursor, com_out_dir=False)
    elif passo == "consultar":
        colecao, filtro = sys.argv[2], json.loads(sys.argv[3])
        url = estado()["url"]
        prompt = (
            f"Ferramenta ArtifactData, url={url}. Só leitura: não grave nada.\n"
            f"Faça exatamente UMA chamada: action query, collection {colecao}, "
            f"query {json.dumps({'where': filtro, 'limit': 1000})}. Responda SOMENTE OK."
        )
        executar(f"consultar-{colecao}", prompt, FERRAMENTAS_DO_BANCO, SAIDA)
    else:
        raise SystemExit(f"passo desconhecido: {passo}")


if __name__ == "__main__":
    main()
