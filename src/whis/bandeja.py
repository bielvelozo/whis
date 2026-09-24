"""O ícone na bandeja do Windows: um clique grava, outro clique vira nota.

Esta é a casca fina da spec — pixels, cliques e balões — sobre o
`whis.coletor`, que é quem sabe gravar e processar. Regra que este
módulo respeita à risca: **nenhuma lógica de pipeline vive aqui**. A bandeja
desenha um estado e encaminha três gestos (gravar, parar, sair); tudo o mais é
do coletor e da costura `processar()`.

Como o usuário usa::

    python -m whis bandeja

- **Clique esquerdo** no ícone: começa a gravar; clicando de novo, para e o
  processamento dispara sozinho.
- **Clique direito**: menu com o mesmo gesto, o estado por extenso, "Abrir a
  palheta", atalhos para abrir a última nota e a pasta de gravações,
  "Configurar" e "Sair".
- O **ícone muda de cor** por estado — cinza parado, vermelho gravando, âmbar
  processando, vermelho escuro com risco quando falhou — e o tooltip diz a
  mesma coisa em português, porque cor sozinha é ambígua.

A bandeja também **hospeda a palheta**: quando ela está presente, o Tk roda no
thread principal (`mainloop`), o `pystray` vai para um thread secundário por
`run_detached`, e o atalho global tem thread e fila de mensagens próprios —
o arranjo provado pela sonda da camada 3. Sem palheta, `icone.run()` como
sempre. O gesto de gravar não muda em nada.

Falhas nunca somem: viram balão do Windows, item de menu, cor de ícone e linha
no log em `%APPDATA%\\whis\\bandeja.log`. A gravação que falhou fica
retida, e o menu diz o comando que a completa (`reprocessar`).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from . import avisos as _avisos
from . import obsidian as _obsidian
from . import registro as _registro
from .coletor import Coletor, Estado, Situacao
from .configuracao import Configuracao
from .instancia import OutraInstancia, Trava, caminho_da_trava
from .obsidian import Lancador, uri_da_nota

_log = logging.getLogger("whis.bandeja")

#: Diâmetro do ícone. 64 px cobre bem o tamanho que o Windows pede na bandeja.
TAMANHO = 64

#: Uma cor por estado, escolhidas para se distinguirem também no tema claro.
CORES = {
    Estado.PARADO: (150, 150, 150, 255),
    Estado.GRAVANDO: (220, 50, 50, 255),
    Estado.PROCESSANDO: (230, 160, 40, 255),
    Estado.ERRO: (140, 20, 20, 255),
}

TITULO = "Whis"

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


def alvo_para_abrir(caminho: Path, configuracao: Configuracao | None) -> str:
    """Uma nota do vault vira URI `obsidian://`; o resto continua caminho.

    `.md` não tem programa associado nesta máquina, então `os.startfile` de
    uma nota nunca abriu o Obsidian. A URI abre a nota certa, no vault certo,
    com o Obsidian aberto ou não.
    """
    if configuracao is None or caminho.suffix.lower() != ".md":
        return str(caminho)
    try:
        relativo = caminho.resolve().relative_to(Path(configuracao.vault).resolve())
    except ValueError:
        return str(caminho)
    return uri_da_nota(configuracao, relativo.as_posix())


def abrir_no_windows(
    caminho: Path, configuracao: Configuracao | None = None, *, lancar: Lancador | None = None
) -> str:
    """Abre uma nota no Obsidian, ou um arquivo/pasta no programa padrão.

    Devolve o que foi lançado (a URI ou o caminho) — é o que o teste confere.
    """
    alvo = alvo_para_abrir(caminho, configuracao)
    (lancar or _lancar)(alvo)
    return alvo


#: O lançador vive em `obsidian`, que a palheta também usa; o nome antigo fica
#: para quem o conhece por aqui.
_lancar = _obsidian.lancar


@dataclass(frozen=True)
class ItemDoMenu:
    """Uma linha do menu da bandeja, como dados — o `pystray` só a desenha.

    `rotulo` pode ser função, para o texto acompanhar o estado; `habilitado`
    idem. `acao` vazia com `separador` é a linha divisória.
    """

    rotulo: str | Callable[[], str]
    acao: Callable[..., object] | None = None
    padrao: bool = False
    habilitado: Callable[[], bool] | None = None
    separador: bool = False


SEPARADOR = ItemDoMenu("", separador=True)

ROTULO_DA_PALHETA = "Abrir a palheta"
ROTULO_DE_CONFIGURAR = "Configurar"


class Bandeja:
    """O ícone e o menu. Guarda o coletor, não o imita.

    `icone` é injetável para o teste montar a bandeja sem bandeja nenhuma: o
    que se prova aqui é que os gestos chegam ao coletor e que cada estado vira
    o desenho, o texto e o balão certos.

    `abrir_palheta`, `abrir_configuracao` e `ao_sair` são os ganchos de quem
    hospeda a palheta: sem eles, o menu é o de sempre.
    """

    def __init__(
        self,
        coletor: Coletor,
        *,
        icone=None,
        notificar: bool = True,
        abrir_palheta: Callable[[], None] | None = None,
        abrir_configuracao: Callable[[], None] | None = None,
        ao_sair: Callable[[], None] | None = None,
    ) -> None:
        self._coletor = coletor
        self._notificar = notificar
        self._abrir_palheta = abrir_palheta
        self._abrir_configuracao = abrir_configuracao
        self._ao_sair = ao_sair
        self._parar_pedido = threading.Event()
        self._nota_avisada: Path | None = None
        self._aviso_mostrado: str | None = None
        self._icone = icone if icone is not None else self._construir_icone()
        coletor.observar(self.atualizar)

    # -- ciclo de vida ------------------------------------------------------

    def executar(self, hospedeiro=None) -> None:
        """Mostra o ícone e devolve o controle só quando o usuário sai.

        Com `hospedeiro` (a janela da palheta, dona do `mainloop`), o ícone
        vai para um thread secundário e é o hospedeiro que segura o thread
        principal até `encerrar`.
        """
        self.atualizar(self._coletor.situacao())
        if hospedeiro is None:
            self._icone.run()
            return
        self._icone.run_detached()
        hospedeiro.executar()

    def sair(self, *_ignorado) -> None:
        """Encerra: uma reunião em andamento é parada e processada antes de sumir."""
        self._parar_pedido.set()
        situacao = self._coletor.situacao()
        if situacao.gravando:
            self._balao("Encerrando", "Parando a gravação e processando antes de sair.")
        self._coletor.encerrar()
        self._icone.visible = False
        self._icone.stop()
        if self._ao_sair is not None:
            self._ao_sair()

    def abrir_palheta(self, *_ignorado) -> None:
        if self._abrir_palheta is not None:
            self._abrir_palheta()

    def abrir_configuracao(self, *_ignorado) -> None:
        if self._abrir_configuracao is not None:
            self._abrir_configuracao()

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
            abrir_no_windows(nota, self._coletor.configuracao)

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
                f"'python -m whis reprocessar'.",
            )
        elif situacao.nota is not None and situacao.nota != self._nota_avisada:
            # Avisa uma vez por nota: voltar ao estado parado por outro motivo
            # (reconhecer um erro, por exemplo) não republica a reunião velha.
            self._nota_avisada = situacao.nota
            self._balao("Reunião no vault", situacao.nota.name)

    # -- bastidores ---------------------------------------------------------

    def itens_do_menu(self) -> tuple[ItemDoMenu, ...]:
        """O menu como dados, na ordem em que aparece.

        "Abrir a palheta" vem logo abaixo do gesto de gravar, e "Configurar"
        antes de "Sair" — só quando quem hospeda a bandeja os ligou.
        """
        itens: list[ItemDoMenu] = [
            ItemDoMenu(self._rotulo_do_gesto, self.alternar, padrao=True),
            ItemDoMenu(lambda: self._coletor.situacao().descricao(), None, habilitado=lambda: False),
        ]
        if self._abrir_palheta is not None:
            itens.append(ItemDoMenu(ROTULO_DA_PALHETA, self.abrir_palheta))
        itens += [
            SEPARADOR,
            ItemDoMenu(
                "Abrir a última nota",
                self.abrir_ultima_nota,
                habilitado=lambda: self._coletor.situacao().nota is not None,
            ),
            ItemDoMenu("Abrir a pasta de gravações", self.abrir_gravacoes),
            SEPARADOR,
        ]
        if self._abrir_configuracao is not None:
            itens.append(ItemDoMenu(ROTULO_DE_CONFIGURAR, self.abrir_configuracao))
        itens.append(ItemDoMenu("Sair", self.sair))
        return tuple(itens)

    def _construir_icone(self):
        import pystray  # importado aqui: o teste monta a bandeja sem tocar no Windows

        def desenhar(item: ItemDoMenu):
            if item.separador:
                return pystray.Menu.SEPARATOR
            rotulo = item.rotulo if isinstance(item.rotulo, str) else (lambda _i, r=item.rotulo: r())
            habilitado = True if item.habilitado is None else (lambda _i, h=item.habilitado: h())
            return pystray.MenuItem(rotulo, item.acao, default=item.padrao, enabled=habilitado)

        return pystray.Icon(
            "whis",
            icon=desenhar_icone(Estado.PARADO),
            title=TITULO,
            menu=pystray.Menu(*(desenhar(item) for item in self.itens_do_menu())),
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
    """Onde a bandeja escreve o log — ver `whis.registro`."""
    return _registro.arquivo_de_log(configuracao)


def configurar_logs(configuracao: Configuracao, *, verboso: bool = False) -> Path:
    """Manda os logs para o arquivo (e para o console, se houver um).

    Sem console — que é o caso do atalho de logon, com `pythonw.exe` — o
    arquivo é a única forma de diagnosticar a reunião de ontem (user story 18).
    """
    return _registro.acrescentar_arquivo(configuracao, verboso=verboso)


def executar(
    configuracao: Configuracao,
    *,
    portas,
    verboso: bool = False,
    palheta=None,
    atalho=None,
    painel: Callable[[object], object] | None = None,
) -> int:
    """Sobe a bandeja com o coletor de verdade. É o que o subcomando chama.

    A trava de instância única vem antes de qualquer coisa: duas bandejas
    disputando os mesmos dispositivos é como uma reunião acaba não sendo
    gravada por ninguém.

    Com `palheta`, a bandeja passa a hospedá-la: cria a janela Tk no thread
    principal, registra `atalho` (um `atalho_global.Atalho`) num thread
    próprio, e liga o menu e a palheta a ela. `painel(raiz)` abre o painel de
    configuração sobre o `Tk` da janela; sem ele, `configurar` avisa que não há
    painel. Um atalho que o Windows recusa (já tomado por outro programa) vira
    log e toast, e a bandeja sobe do mesmo jeito — o item de menu ainda abre
    a palheta.
    """
    trava = Trava(caminho_da_trava(configuracao))
    try:
        trava.adquirir()
    except OutraInstancia as erro:
        print(f"{erro}")
        return 1

    destino = configurar_logs(configuracao, verboso=verboso)
    _log.info("Bandeja iniciada. Log em %s", destino)
    print(f"Whis na bandeja. Log em {destino}", flush=True)
    print("Clique no ícone para gravar; clique de novo para parar e processar.", flush=True)

    coletor = Coletor(configuracao, portas=portas)
    if palheta is None:
        bandeja = Bandeja(coletor)
        try:
            bandeja.executar()
        except KeyboardInterrupt:
            bandeja.sair()
        finally:
            trava.liberar()
        return 0

    from .atalho_global import AtalhoGlobal
    from .janela_da_palheta import Acao, JanelaDaPalheta

    janela = JanelaDaPalheta()
    janela.ao_enviar(palheta.despachar)
    palheta.gravando = lambda: coletor.situacao().gravando
    def abre(comando):
        if comando.lista is None:
            return None
        return lambda: comando.lista(palheta.configuracao)

    def definir_acoes() -> None:
        janela.definir_acoes(
            [
                Acao(
                    comando.nome,
                    comando.icone,
                    comando.rotulo_atual,
                    comando.descricao,
                    bool(comando.parametro),
                    abre=abre(comando),
                )
                for comando in palheta.acoes()
            ]
        )

    definir_acoes()

    def abrir_palheta() -> None:
        janela.pedir(janela.mostrar)

    abrir_configuracao: Callable[[], None] | None = None
    if painel is not None:

        def abrir_configuracao() -> None:
            janela.pedir(lambda: painel(janela.raiz))

        palheta.abrir_painel = abrir_configuracao

    hotkey = AtalhoGlobal(atalho, abrir_palheta) if atalho is not None else None

    def encerrar() -> None:
        if hotkey is not None:
            hotkey.parar()
        janela.pedir(janela.encerrar)

    bandeja = Bandeja(
        coletor,
        abrir_palheta=abrir_palheta,
        abrir_configuracao=abrir_configuracao,
        ao_sair=encerrar,
    )
    palheta.gravar = bandeja.alternar
    if hotkey is not None:
        if hotkey.iniciar():
            print(f"Palheta no atalho {atalho.texto}.", flush=True)
        else:
            _log.error(
                "O atalho %s da palheta não foi registrado — outro programa deve estar "
                "usando a combinação. Troque [palheta].atalho na configuração; enquanto "
                "isso, a palheta abre pelo menu da bandeja.",
                atalho.texto,
            )
            _avisos.avisar(
                "O atalho da palheta não registrou",
                f"{atalho.texto} já está em uso por outro programa. A palheta abre pelo "
                f"menu da bandeja; troque [palheta].atalho para ter o atalho de volta.",
            )
    try:
        bandeja.executar(hospedeiro=janela)
    except KeyboardInterrupt:
        bandeja.sair()
    finally:
        if hotkey is not None:
            hotkey.parar()
        trava.liberar()
    return 0
