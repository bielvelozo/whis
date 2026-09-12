"""Sonda da camada 3, para rodar sob pythonw.exe (sem console).

Prova, no mesmo processo e no arranjo que a palheta vai usar:
- Tk no thread principal (mainloop);
- pystray por run_detached (thread secundario);
- RegisterHotKey num thread proprio com loop de mensagens proprio, e o
  WM_HOTKEY chegando quando outro processo simula a tecla.
Escreve tudo num log, porque nao ha console.
"""

import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

import win32api
import win32con
import win32gui
from PIL import Image

LOG = Path(sys.argv[1])
INICIO = time.monotonic()
VK_F9 = 0x78
ID_HOTKEY = 1


def registrar(linha: str) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{time.monotonic() - INICIO:6.2f}s  {linha}\n")


fila: "queue.Queue[str]" = queue.Queue()
thread_id_do_hotkey = {"id": None}


def loop_do_hotkey() -> None:
    thread_id_do_hotkey["id"] = win32api.GetCurrentThreadId()
    try:
        win32gui.RegisterHotKey(
            None,
            ID_HOTKEY,
            win32con.MOD_CONTROL | win32con.MOD_ALT | win32con.MOD_SHIFT | 0x4000,
            VK_F9,
        )
        registrar("hotkey registrado (Ctrl+Alt+Shift+F9) no thread do hotkey")
    except Exception as erro:  # noqa: BLE001
        registrar(f"FALHA ao registrar hotkey: {erro!r}")
        fila.put("falha-registro")
        return
    try:
        while True:
            msg = win32gui.GetMessage(None, 0, 0)
            if msg[0] == 0:
                break
            _hwnd, message, wparam, _lparam, _t, _pt = msg[1]
            if message == win32con.WM_HOTKEY and wparam == ID_HOTKEY:
                registrar("WM_HOTKEY recebido no thread do hotkey")
                fila.put("hotkey")
            elif message == win32con.WM_QUIT:
                break
    finally:
        try:
            win32gui.UnregisterHotKey(None, ID_HOTKEY)
            registrar("hotkey desregistrado")
        except Exception as erro:  # noqa: BLE001
            registrar(f"erro ao desregistrar: {erro!r}")


def main() -> None:
    LOG.write_text("", encoding="utf-8")
    registrar(f"processo {sys.executable} pid {win32api.GetCurrentProcessId()}")

    raiz = tk.Tk()
    raiz.withdraw()
    raiz.overrideredirect(True)
    raiz.attributes("-topmost", True)
    largura, altura = 420, 60
    x = (raiz.winfo_screenwidth() - largura) // 2
    y = (raiz.winfo_screenheight() - altura) // 3
    raiz.geometry(f"{largura}x{altura}+{x}+{y}")
    campo = tk.Entry(raiz, font=("Segoe UI", 16))
    campo.pack(fill="both", expand=True, padx=8, pady=8)
    registrar("Tk criado no thread principal")

    import pystray

    icone = pystray.Icon(
        "whis-sonda",
        icon=Image.new("RGBA", (64, 64), (200, 40, 40, 255)),
        title="Whis sonda",
        menu=pystray.Menu(pystray.MenuItem("Sair", lambda *_: None)),
    )
    icone.run_detached()
    registrar("pystray.run_detached chamado")

    t = threading.Thread(target=loop_do_hotkey, name="hotkey", daemon=True)
    t.start()

    estado = {"mostrou": False}

    def sondar_fila() -> None:
        try:
            while True:
                item = fila.get_nowait()
                if item == "hotkey":
                    raiz.deiconify()
                    raiz.lift()
                    campo.focus_force()
                    estado["mostrou"] = True
                    registrar("Tk mostrou a janela em resposta ao hotkey")
                    raiz.after(700, raiz.withdraw)
                elif item == "falha-registro":
                    registrar("encerrando por falha no registro")
                    encerrar()
                    return
        except queue.Empty:
            pass
        raiz.after(50, sondar_fila)

    def encerrar() -> None:
        registrar(f"encerrando: janela mostrada={estado['mostrou']}, icone visivel={icone.visible}")
        tid = thread_id_do_hotkey["id"]
        if tid:
            win32api.PostThreadMessage(tid, win32con.WM_QUIT, 0, 0)
        icone.stop()
        raiz.after(300, raiz.destroy)

    raiz.after(50, sondar_fila)
    raiz.after(9000, encerrar)
    raiz.mainloop()
    t.join(timeout=3)
    registrar(f"mainloop terminou; thread do hotkey vivo={t.is_alive()}; icone visivel={icone.visible}")


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:  # noqa: BLE001
        registrar(f"EXCECAO: {erro!r}")
        raise
