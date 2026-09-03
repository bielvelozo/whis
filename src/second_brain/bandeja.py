"""O ícone na bandeja do Windows: um clique grava, outro clique vira nota.

Esta é a casca fina da spec — pixels, cliques e balões — sobre o
`second_brain.coletor`, que é quem sabe gravar e processar. Regra que este
módulo respeita à risca: **nenhuma lógica de pipeline vive aqui**. A bandeja
desenha um estado e encaminha três gestos (gravar, parar, sair); tudo o mais é
do coletor e da costura `processar()`.

Como o usuário usa::

    python -m second_brain bandeja

- **Clique esquerdo** no ícone: começa a gravar; clicando de novo, para e o
  processamento dispara sozinho.
- **Clique direito**: menu com o mesmo gesto, o estado por extenso, atalhos
  para abrir a última nota e a pasta de gravações, e "Sair".
- O **ícone muda de cor** por estado — cinza parado, vermelho gravando, âmbar
  processando, vermelho escuro com risco quando falhou — e o tooltip diz a
  mesma coisa em português, porque cor sozinha é ambígua.

Falhas nunca somem: viram balão do Windows, item de menu, cor de ícone e linha
no log em `%APPDATA%\\second-brain\\bandeja.log`. A gravação que falhou fica
retida, e o menu diz o comando que a completa (`reprocessar`).
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from pathlib import Path

from PIL import Image, ImageDraw

from . import registro as _registro
from .coletor import Coletor, Estado, Situacao
from .configuracao import Configuracao
from .instancia import OutraInstancia, Trava, caminho_da_trava

_log = logging.getLogger("second_brain.bandeja")

#: Diâmetro do ícone. 64 px cobre bem o tamanho que o Windows pede na bandeja.
TAMANHO = 64

#: Uma cor por estado, escolhidas para se distinguirem também no tema claro.
CORES = {
    Estado.PARADO: (150, 150, 150, 255),
    Estado.GRAVANDO: (220, 50, 50, 255),
    Estado.PROCESSANDO: (230, 160, 40, 255),
    Estado.ERRO: (140, 20, 20, 255),
}

TITULO = "Second Brain"

#: Limites do próprio Windows, não escolha nossa: o tooltip do ícone
#: (`szTip`) cabe 128 caracteres, o corpo do balão (`szInfo`) 256 e o título
#: dele (`szInfoTitle`) 64 — e o pystray levanta `ValueError` ao estourar. Uma
#: mensagem de erro longa da Deepgram passa fácil dos 128, e sem corte a
#: exceção derrubava a atualização inteira: o ícone virava vermelho e o balão
#: que explicava o motivo nunca aparecia.
LIMITE_DO_TOOLTIP = 127
LIMITE_DO_BALAO = 255
LIMITE_DO_TITULO_DO_BALAO = 63


def encurtar(texto: str, limite: int) -> str:
    """Corta no limite do Windows preservando o começo, que é o que importa."""
    texto = " ".join(texto.split())
    if len(texto) <= limite:
        return texto
    return texto[: max(1, limite - 1)].rstrip() + "…"


def desenhar_icone(estado: Estado) -> Image.Image:
    """Um círculo cheio na cor do estado — com marca própria quando é erro.

    Cor sozinha não basta (monitor, tema, daltonismo): parado é um círculo
    vazado, gravando é um círculo cheio, processando é um anel grosso e erro
    leva um risco atravessado. O tooltip repete tudo por escrito.
    """
    imagem = Image.new("RGBA", (TAMANHO, TAMANHO), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    cor = CORES[estado]
    caixa = (8, 8, TAMANHO - 8, TAMANHO - 8)

    if estado is Estado.PARADO:
        desenho.ellipse(caixa, outline=cor, width=6)
    elif estado is Estado.PROCESSANDO:
        desenho.ellipse(caixa, outline=cor, width=12)
    else:
        desenho.ellipse(caixa, fill=cor)

    if estado is Estado.ERRO:
        desenho.line((18, 18, TAMANHO - 18, TAMANHO - 18), fill=(255, 255, 255, 255), width=7)
    return imagem


def abrir_no_windows(caminho: Path) -> None:
    """Abre um arquivo ou pasta no programa padrão (Obsidian, Explorer...)."""
    try:
        os.startfile(str(caminho))  # type: ignore[attr-defined]  # Windows
    except AttributeError:  # outro sistema operacional — só no desenvolvimento
        subprocess.run(["xdg-open", str(caminho)], check=False)
    except OSError as erro:
        _log.error("Não foi possível abrir %s: %s", caminho, erro)


class Bandeja:
    """O ícone e o menu. Guarda o coletor, não o imita.

    `icone` é injetável para o teste montar a bandeja sem bandeja nenhuma: o
    que se prova aqui é que os gestos chegam ao coletor e que cada estado vira
    o desenho, o texto e o balão certos.
    """

    def __init__(self, coletor: Coletor, *, icone=None, notificar: bool = True) -> None:
        self._coletor = coletor
        self._notificar = notificar
        self._parar_pedido = threading.Event()
        self._nota_avisada: Path | None = None
        self._aviso_mostrado: str | None = None
        self._icone = icone if icone is not None else self._construir_icone()
        coletor.observar(self.atualizar)

    # -- ciclo de vida ------------------------------------------------------

    def executar(self) -> None:
        """Mostra o ícone e devolve o controle só quando o usuário sai."""
        self.atualizar(self._coletor.situacao())
        self._icone.run()

    def sair(self, *_ignorado) -> None:
        """Encerra: uma reunião em andamento é parada e processada antes de sumir."""
        self._parar_pedido.set()
        situacao = self._coletor.situacao()
        if situacao.gravando:
            self._balao("Encerrando", "Parando a gravação e processando antes de sair.")
        self._coletor.encerrar()
        self._icone.visible = False
        self._icone.stop()

    # -- gestos -------------------------------------------------------------

    def alternar(self, *_ignorado) -> None:
        """O clique único: grava ou para, conforme o estado."""
        situacao = self._coletor.situacao()
        try:
            if situacao.gravando:
                self._coletor.parar()
            else:
                self._coletor.iniciar()
        except Exception as erro:  # noqa: BLE001 — o clique não pode derrubar a bandeja
            _log.error("Gesto recusado: %s", erro)
            self._balao("Não deu para começar", str(erro))

    def abrir_ultima_nota(self, *_ignorado) -> None:
        nota = self._coletor.situacao().nota
        if nota is not None:
            abrir_no_windows(nota)

    def abrir_gravacoes(self, *_ignorado) -> None:
        pasta = Path(self._coletor.configuracao.gravacoes)
        if pasta.is_dir():
            abrir_no_windows(pasta)

    # -- reação ao coletor --------------------------------------------------

    def atualizar(self, situacao: Situacao) -> None:
        """Repinta o ícone e o tooltip; avisa por balão quando há o que avisar.

        É o `ao_mudar` do coletor — a única ponte entre a máquina de estados e
        a interface.
        """
        # Desenhar e avisar são independentes de propósito: numa execução real
        # o tooltip estourou o limite do Windows e a exceção levou junto o balão
        # que explicava o erro — o usuário ficou com um ícone vermelho e nenhum
        # motivo. Falhar em pintar não pode calar a mensagem.
        try:
            self._icone.icon = desenhar_icone(situacao.estado)
            self._icone.title = encurtar(
                f"{TITULO} — {situacao.descricao()}", LIMITE_DO_TOOLTIP
            )
            if hasattr(self._icone, "update_menu"):
                self._icone.update_menu()
        except Exception as erro:  # noqa: BLE001
            _log.error("Não foi possível repintar o ícone: %s", erro)

        if situacao.aviso and situacao.aviso != self._aviso_mostrado:
            # Reunião gravando torta ainda dá tempo de consertar — mas só se o
            # usuário souber agora, e não ao abrir a nota amanhã.
            self._aviso_mostrado = situacao.aviso
            self._balao(
                "A gravação está saindo incompleta",
                f"{situacao.aviso.capitalize()}.\n\nCom fone, o canal do sistema "
                f"precisa ser a saída que está tocando o som. Ajuste "
                f"[audio].dispositivo_sistema na configuração e grave de novo.",
            )
        elif not situacao.aviso:
            self._aviso_mostrado = None

        if situacao.estado is Estado.ERRO:
            self._balao(
                "A reunião não virou nota",
                f"{situacao.erro}\n\nA gravação está salva. Complete com "
                f"'python -m second_brain reprocessar'.",
            )
        elif situacao.nota is not None and situacao.nota != self._nota_avisada:
            # Avisa uma vez por nota: voltar ao estado parado por outro motivo
            # (reconhecer um erro, por exemplo) não republica a reunião velha.
            self._nota_avisada = situacao.nota
            self._balao("Reunião no vault", situacao.nota.name)

    # -- bastidores ---------------------------------------------------------

    def _construir_icone(self):
        import pystray  # importado aqui: o teste monta a bandeja sem tocar no Windows

        return pystray.Icon(
            "second-brain",
            icon=desenhar_icone(Estado.PARADO),
            title=TITULO,
            menu=pystray.Menu(
                pystray.MenuItem(
                    self._rotulo_do_gesto, self.alternar, default=True
                ),
                pystray.MenuItem(lambda _: self._coletor.situacao().descricao(), None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Abrir a última nota",
                    self.abrir_ultima_nota,
                    enabled=lambda _: self._coletor.situacao().nota is not None,
                ),
                pystray.MenuItem("Abrir a pasta de gravações", self.abrir_gravacoes),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sair", self.sair),
            ),
        )

    def _rotulo_do_gesto(self, _item=None) -> str:
        return (
            "Parar e processar"
            if self._coletor.situacao().gravando
            else "Gravar reunião"
        )

    def _balao(self, titulo: str, mensagem: str) -> None:
        if not self._notificar:
            return
        _log.info("Aviso ao usuário — %s: %s", titulo, mensagem)
        try:
            self._icone.notify(
                encurtar(mensagem, LIMITE_DO_BALAO),
                encurtar(titulo, LIMITE_DO_TITULO_DO_BALAO),
            )
        except Exception as erro:  # noqa: BLE001 — sem balão o log ainda conta a história
            _log.debug("Notificação indisponível: %s", erro)


def arquivo_de_log(configuracao: Configuracao) -> Path:
    """Onde a bandeja escreve o log — ver `second_brain.registro`."""
    return _registro.arquivo_de_log(configuracao)


def configurar_logs(configuracao: Configuracao, *, verboso: bool = False) -> Path:
    """Manda os logs para o arquivo (e para o console, se houver um).

    Sem console — que é o caso do atalho de logon, com `pythonw.exe` — o
    arquivo é a única forma de diagnosticar a reunião de ontem (user story 18).
    """
    return _registro.acrescentar_arquivo(configuracao, verboso=verboso)


def executar(configuracao: Configuracao, *, portas, verboso: bool = False) -> int:
    """Sobe a bandeja com o coletor de verdade. É o que o subcomando chama.

    A trava de instância única vem antes de qualquer coisa: duas bandejas
    disputando os mesmos dispositivos é como uma reunião acaba não sendo
    gravada por ninguém.
    """
    trava = Trava(caminho_da_trava(configuracao))
    try:
        trava.adquirir()
    except OutraInstancia as erro:
        print(f"{erro}")
        return 1

    destino = configurar_logs(configuracao, verboso=verboso)
    _log.info("Bandeja iniciada. Log em %s", destino)
    print(f"Second Brain na bandeja. Log em {destino}", flush=True)
    print("Clique no ícone para gravar; clique de novo para parar e processar.", flush=True)

    bandeja = Bandeja(Coletor(configuracao, portas=portas))
    try:
        bandeja.executar()
    except KeyboardInterrupt:
        bandeja.sair()
    finally:
        trava.liberar()
    return 0
