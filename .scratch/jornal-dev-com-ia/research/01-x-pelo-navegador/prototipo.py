"""Protótipo da camada 0: o X aceita o Chrome do Whis, e quanto cada página traz.

Rode da raiz do repositório, no PowerShell dele, com a conta do Whis já criada:

    .venv\\Scripts\\python.exe .scratch\\jornal-dev-com-ia\\research\\01-x-pelo-navegador\\prototipo.py --login
    .venv\\Scripts\\python.exe .scratch\\jornal-dev-com-ia\\research\\01-x-pelo-navegador\\prototipo.py
    .venv\\Scripts\\python.exe .scratch\\jornal-dev-com-ia\\research\\01-x-pelo-navegador\\prototipo.py --com-janela

Cada página é lida sozinha, para medir o tempo de cada uma. O resultado vai em
`medidas.json` e o HTML de cada post em `amostras/`, ao lado deste arquivo.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from whis.fonte_x import ErroDoX, LeitorDoX, abrir_login
from whis.fontes_do_jornal import MODELO_DAS_FONTES, interpretar_fontes

AQUI = Path(__file__).parent


def main() -> int:
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument("--login", action="store_true", help="abre o Chrome com janela para entrar na conta")
    argumentos.add_argument("--com-janela", action="store_true", help="lê com o Chrome visível em vez de sem janela")
    opcoes = argumentos.parse_args()

    if opcoes.login:
        print("Sessão salva." if abrir_login() else "Login não concluído.")
        return 0

    fontes = next(secao for secao in interpretar_fontes(MODELO_DAS_FONTES).secoes if secao.id == "ia").x
    leitor = LeitorDoX(sem_janela=not opcoes.com_janela, amostras=AQUI / "amostras")
    agora = datetime.now(UTC)
    medidas = []
    for fonte in fontes:
        inicio = time.monotonic()
        try:
            leitura = leitor.ler((fonte,), agora.date())
            posts = leitura.posts.get(fonte.nome, ())
            falha = leitura.falhas.get(fonte.nome)
        except ErroDoX as erro:
            posts, falha = (), f"{type(erro).__name__}: {erro}"
        recentes = [post for post in posts if post.data >= agora - timedelta(hours=24)]
        medida = {
            "pagina": fonte.nome,
            "consulta": fonte.consulta,
            "segundos": round(time.monotonic() - inicio, 1),
            "posts": len(posts),
            "ultimas_24h": len(recentes),
            "curtidas": sorted((post.curtidas or 0 for post in recentes), reverse=True)[:10],
            "falha": falha,
        }
        medidas.append(medida)
        print(json.dumps(medida, ensure_ascii=False))

    (AQUI / "medidas.json").write_text(
        json.dumps({"quando": agora.isoformat(), "sem_janela": not opcoes.com_janela, "paginas": medidas}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Medidas em {AQUI / 'medidas.json'}; amostras em {AQUI / 'amostras'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
