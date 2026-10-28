"""Confere, no note-biel, se o Whis já manda pela caixa nova e com o código de 28/10.

Roda num terminal dele, no note-biel: python .rota-teste-caixa-nova.py
Manda um e-mail de teste de gabriel@velozo.dev para soares.velozog@gmail.com e escreve o resultado em
.rota-teste-caixa-nova-log.txt, na raiz do repositório. Não mostra senha nem chave.
"""

import inspect
import os
import subprocess
import sys
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))
LOG = RAIZ / ".rota-teste-caixa-nova-log.txt"
PARA = "soares.velozog@gmail.com"


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True)
    return (r.stdout or r.stderr).strip()


saida = [
    f"máquina: {os.environ.get('COMPUTERNAME')}",
    f"branch: {git('branch', '--show-current')} | commit: {git('log', '--oneline', '-1')[:90]}",
    f"tem a correção do tema de fábrica (b47058d): {git('cat-file', '-t', 'b47058d') == 'commit'}",
    f"mudanças não commitadas: {len(git('status', '--porcelain', '--untracked-files=no').splitlines())} arquivos",
]
try:
    from whis import agencias_email
    from whis.configuracao import carregar

    c = carregar(Path(os.environ["APPDATA"]) / "whis" / "config.toml")
    remetente = getattr(c, "cacada_remetente", "")
    resend = getattr(c, "cacada_resend_chave", "")
    saida += [
        f"[cacada].email: {c.cacada_email}",
        f"[cacada].remetente: {remetente or '(vazio)'}",
        f"senha_de_app preenchida: {bool(c.cacada_senha_de_app)}",
        f"resend_chave preenchida: {bool(resend)} (precisa ser False para a Resend ficar pausada)",
    ]
    params = list(inspect.signature(agencias_email.gmail).parameters)
    extras = {"remetente": remetente, "resend_chave": ""}
    enviar = agencias_email.gmail(c.cacada_email, c.cacada_senha_de_app, *[extras[p] for p in params[2:] if p in extras])
    corpo = "Oi, Gabriel, tudo certo?\n\nEste é o teste da caixa nova pelo Whis, pelo SMTP do Google.\n\nAbraço,\nGabriel"
    envio = inspect.signature(enviar).parameters
    if len(envio) >= 4:
        enviar(PARA, "Teste do Whis: caixa nova", corpo, None)
    else:
        enviar(PARA, "Teste do Whis: caixa nova", corpo)
    saida.append(f"ENVIADO de {c.cacada_email} para {PARA}. Confira a caixa e o remetente.")
except Exception:
    saida.append("ERRO:\n" + traceback.format_exc())

print("\n".join(saida))
LOG.write_text("\n".join(saida) + "\n", encoding="utf-8")
