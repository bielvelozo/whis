"""Prova de tela do ticket 17: a janela de verdade com o comando `do` na lista.

Uso: pythonw sonda-do.py <pasta-de-saida>

Abre a janela real (sem bandeja, sem atalho global), captura a lista inteira,
digita `do ` para ver o filtro e a linha selecionada, captura de novo, e sai.
O que se olha nas capturas: a linha **To-do** com o ícone (se sair tofu, trocar
o glifo) e o nome `do` em roxo à direita.
"""

import sys
from pathlib import Path

from PIL import ImageGrab

from whis.janela_da_palheta import Acao, JanelaDaPalheta

PASTA = Path(sys.argv[1])
PASTA.mkdir(parents=True, exist_ok=True)

ACOES = (
    Acao("open", "▤", "Open note", "daily/atual.md in Obsidian"),
    Acao("daily", "☀", "Generate daily", "Update daily/atual.md from git, Linear and Slack (~40 s)"),
    Acao("record", "●", lambda: "Start recording", "Toggle the meeting recorder in the tray"),
    Acao("ask", "?", "Ask", "Ask the vault; the answer becomes a note in respostas/ (~60 s)", True),
    Acao("note", "✎", "Note", "Add a line to Pontos in daily/atual.md", True),
    Acao("doubt", "¿", "Doubt", "Add a line to Dúvidas in daily/atual.md", True),
    Acao("do", "☐", "To-do", "Add a to-do to Fazer in daily/atual.md; you tick it yourself", True),
    Acao("settings", "⚙", "Settings", "Open the settings panel (all config keys)"),
)


def capturar(janela: JanelaDaPalheta, nome: str) -> None:
    janela.raiz.update()
    janela.raiz.after(150, lambda: None)
    janela.raiz.update()
    x, y = janela.raiz.winfo_rootx(), janela.raiz.winfo_rooty()
    largura, altura = janela.raiz.winfo_width(), janela.raiz.winfo_height()
    escala = ImageGrab.grab().width / janela.raiz.winfo_screenwidth()
    caixa = (int(x * escala), int(y * escala), int((x + largura) * escala), int((y + altura) * escala))
    ImageGrab.grab(caixa).save(PASTA / nome)


janela = JanelaDaPalheta()
janela.definir_acoes(ACOES)
janela.ao_enviar(lambda texto: None)
janela.mostrar()
capturar(janela, "lista-inteira.png")

janela.digitar("do ")
capturar(janela, "filtrado-do.png")

janela.esconder()
janela.raiz.update()
janela.raiz.destroy()
