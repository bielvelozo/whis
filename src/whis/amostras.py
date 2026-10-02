r"""A amostra para o cliente: a página de conceito no vault, o print e, se configurado, o link público.

Research 09: a amostra é **um conceito, não o trabalho** — uma página só,
estática, sem nome nem contato dele, com `noindex` e o aviso de demonstração.
Ela nasce sempre no vault (`cacada/<data>/amostras/<slug>/index.html`), com um
print ao lado (`amostra.png`) — é o print que vai como anexo na Workana, que
suspende proposta com link externo.

O link público é opcional: com `[cacada].cloudflare_token` e
`[cacada].cloudflare_conta` preenchidos, as amostras dos últimos 30 dias sobem
juntas para um projeto do Cloudflare Pages de nome neutro, pelo `wrangler`
(direct upload, plano grátis com uso comercial permitido). Sem as chaves, ou se
a publicação falhar, a amostra fica só no vault e o pacote diz isso.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .configuracao import Configuracao
from .corrida import pasta_da_cacada

_log = logging.getLogger("whis.amostras")

VALIDADE_DIAS = 30
PASTA_NO_AR = "amostras-no-ar"
ARQUIVO_DO_PROJETO = "projeto-cloudflare.txt"
TEMPO_DO_WRANGLER_S = 300
AVISO = "Conceito de demonstração — não é o site final"
_SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass(frozen=True)
class AmostraPronta:
    """Onde a amostra ficou: o HTML e o print no vault, e o link público quando subiu."""

    html: str
    print_: str | None = None
    url: str | None = None
    motivo_sem_link: str = ""


def gravar(vault: Path, relativo_da_pasta: str, html: str) -> Path:
    """Grava `index.html` na pasta da amostra, com `noindex` e o aviso garantidos."""
    pasta = Path(vault) / relativo_da_pasta
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / "index.html"
    arquivo.write_text(_com_garantias(html), encoding="utf-8")
    return arquivo


def _com_garantias(html: str) -> str:
    if 'name="robots"' not in html:
        html = re.sub(r"(<head[^>]*>)", r'\1<meta name="robots" content="noindex">', html, count=1, flags=re.I)
    if AVISO.split(" —")[0] not in html:
        rodape = f'<p style="text-align:center;font:12px sans-serif;opacity:.6;margin:24px">{AVISO}</p>'
        html = re.sub(r"(</body>)", rodape + r"\1", html, count=1, flags=re.I) if "</body>" in html.lower() else html + rodape
    return html


def tirar_print(arquivo: Path) -> Path | None:
    """O print da página inteira, pelo Chrome instalado sem janela. Falhar não é erro."""
    from .fonte_x import _playwright

    destino = arquivo.with_name("amostra.png")
    try:
        with _playwright() as playwright:
            navegador = playwright.chromium.launch(channel="chrome", headless=True)
            try:
                pagina = navegador.new_page(viewport={"width": 1280, "height": 800})
                pagina.goto(arquivo.resolve().as_uri(), wait_until="load")
                pagina.screenshot(path=str(destino), full_page=True)
            finally:
                navegador.close()
    except Exception as erro:  # noqa: BLE001 — sem print, a amostra continua valendo
        _log.info("Print da amostra não saiu: %s", erro)
        return None
    return destino


# -- o link público ------------------------------------------------------------------------


Executor = Callable[[list[str], dict[str, str]], subprocess.CompletedProcess]


def _rodar(comando: list[str], ambiente: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        comando,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TEMPO_DO_WRANGLER_S,
        env={**os.environ, **ambiente},
        creationflags=_SEM_JANELA,
        check=False,
    )


def publicacao_configurada(configuracao: Configuracao) -> bool:
    return bool(configuracao.cacada_cloudflare_token and configuracao.cacada_cloudflare_conta)


def publicar(
    configuracao: Configuracao,
    arquivo: Path,
    slug: str,
    *,
    executar: Executor = _rodar,
    pasta: Path | None = None,
    agora: float | None = None,
) -> AmostraPronta | str:
    """Sobe a amostra com as outras ainda válidas; devolve a URL ou o motivo de não ter subido."""
    if not publicacao_configurada(configuracao):
        return "sem [cacada].cloudflare_token e [cacada].cloudflare_conta: a amostra ficou só no vault"
    npx = shutil.which("npx")
    if npx is None:
        return "o npx (Node.js) não foi encontrado no PATH"
    base = Path(pasta) if pasta else pasta_da_cacada()
    no_ar = base / PASTA_NO_AR
    destino = no_ar / slug
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy2(arquivo, destino / "index.html")
    _vencer(no_ar, agora if agora is not None else time.time())
    projeto = projeto_cloudflare(configuracao, base)
    ambiente = {
        "CLOUDFLARE_API_TOKEN": configuracao.cacada_cloudflare_token,
        "CLOUDFLARE_ACCOUNT_ID": configuracao.cacada_cloudflare_conta,
    }
    executar([npx, "--yes", "wrangler@3", "pages", "project", "create", projeto, "--production-branch=main"], ambiente)
    feito = executar(
        [npx, "--yes", "wrangler@3", "pages", "deploy", str(no_ar), f"--project-name={projeto}", "--branch=main", "--commit-dirty=true"],
        ambiente,
    )
    if feito.returncode != 0:
        motivo = (feito.stderr or feito.stdout or "").strip().splitlines()
        return f"o wrangler falhou: {motivo[-1][:200] if motivo else f'código {feito.returncode}'}"
    return AmostraPronta(html="", url=f"https://{projeto}.pages.dev/{slug}/")


def projeto_cloudflare(configuracao: Configuracao, base: Path) -> str:
    """O nome do projeto: o do config, ou um neutro sorteado uma vez e guardado."""
    if configuracao.cacada_cloudflare_projeto:
        return configuracao.cacada_cloudflare_projeto
    arquivo = Path(base) / ARQUIVO_DO_PROJETO
    if arquivo.is_file():
        nome = arquivo.read_text(encoding="utf-8").strip()
        if nome:
            return nome
    nome = f"conceitos-{secrets.token_hex(3)}"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(nome, encoding="utf-8")
    return nome


def _vencer(no_ar: Path, agora: float) -> None:
    """Tira da pasta publicada as amostras com mais de `VALIDADE_DIAS`: o próximo deploy as derruba."""
    for pasta in no_ar.iterdir() if no_ar.is_dir() else ():
        indice = pasta / "index.html"
        if pasta.is_dir() and indice.is_file() and agora - indice.stat().st_mtime > VALIDADE_DIAS * 86_400:
            shutil.rmtree(pasta, ignore_errors=True)
            _log.info("Amostra vencida tirada do ar: %s", pasta.name)
