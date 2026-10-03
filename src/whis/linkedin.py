"""O LinkedIn (entrega 3 de vagas e freelas): analisar o perfil, escrever posts e publicar com o aval dele.

Nada aqui é automático no LinkedIn (ticket 06: *"os colegas me seguem"*) e
nada usa navegador logado na conta dele (research 08):

- **analisar**: ele baixa o export de dados (*Configurações → Privacidade dos
  dados → Baixar seus dados*), aponta `[linkedin].exportacao` para o `.zip` ou
  a pasta, e o Whis lê os CSV (Profile, Positions, Education, Skills…). A
  análise vira `linkedin/perfil.md`: o título, o *Sobre*, as experiências e as
  competências reescritos para colar, e o que fazer antes de mexer (desligar o
  aviso de mudanças para a rede; nunca *Open to Work*). Quem cola é ele.
- **escrever**: rascunhos em `linkedin/posts/AAAA-MM-DD-<slug>.md`, com
  `status: rascunho`. O corpo da nota é o post, palavra por palavra: ele edita
  à vontade no Obsidian. O método é o da skill `li-post` que ele indicou
  (gancho que sobrevive ao corte, parágrafos curtos, uma ideia por post, fecho
  com uma pergunta), portado para português; o humanizador dela estraga
  português (medido, research 08), então as regras de voz vão no prompt.
- **publicar**: só pelo gesto dele — Enter na lista `posts` da palheta, ou
  `whis linkedin-publicar <nota>` respondendo "s". Pela API oficial (*Share on
  LinkedIn*, `w_member_social`, self-serve), com o login OAuth guardado no
  cofre (`whis linkedin-login`). Publicado, a nota ganha `status: publicado` e
  o link — o texto dela não é tocado.

Mudar o perfil e se candidatar no LinkedIn continuam com ele: não há API, e
o navegador logado fere o User Agreement (seção 8.2).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import secrets
import threading
import time
import webbrowser
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

from . import vault as _vault
from .cacada_claude import REGRAS_DE_DISCRICAO, _ChamadaDoClaude
from .cofre import Cofre

_log = logging.getLogger("whis.linkedin")

PASTA_LINKEDIN = "linkedin"
PASTA_DOS_POSTS = f"{PASTA_LINKEDIN}/posts"
CAMINHO_DA_ANALISE = f"{PASTA_LINKEDIN}/perfil.md"
ZONAS_DO_LINKEDIN = (PASTA_LINKEDIN,)

RASCUNHO = "rascunho"
PUBLICADO = "publicado"

AUTORIZAR = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO = "https://api.linkedin.com/v2/userinfo"
POSTS = "https://api.linkedin.com/rest/posts"
ESCOPOS = "openid profile w_member_social"
PORTA_DO_RETORNO = 8765
RETORNO = f"http://localhost:{PORTA_DO_RETORNO}/linkedin"
CHAVE_NO_COFRE = "linkedin"
ESPERA_DO_LOGIN_S = 600
LIMITE_DO_POST = 3000

ARQUIVOS_DO_EXPORT = (
    "Profile.csv",
    "Profile Summary.csv",
    "Positions.csv",
    "Education.csv",
    "Skills.csv",
    "Languages.csv",
    "Certifications.csv",
    "Projects.csv",
    "Honors.csv",
    "Courses.csv",
)


class ErroDoLinkedIn(RuntimeError):
    """Sem login, login vencido, API recusou, export ilegível."""


# -- o export de dados --------------------------------------------------------------------------


def ler_exportacao(caminho: Path) -> str:
    """Os CSV do perfil, do `.zip` ou da pasta do export, como texto para o Claude ler."""
    caminho = Path(caminho)
    arquivos: dict[str, str] = {}
    if caminho.is_file() and caminho.suffix.lower() == ".zip":
        with zipfile.ZipFile(caminho) as pacote:
            for nome in pacote.namelist():
                base = Path(nome).name
                if base in ARQUIVOS_DO_EXPORT:
                    arquivos[base] = pacote.read(nome).decode("utf-8-sig", errors="replace")
    elif caminho.is_dir():
        for base in ARQUIVOS_DO_EXPORT:
            achado = next(iter(caminho.rglob(base)), None)
            if achado is not None:
                arquivos[base] = achado.read_text(encoding="utf-8-sig", errors="replace")
    else:
        raise ErroDoLinkedIn(f"o export do LinkedIn não está em {caminho} (aponte [linkedin].exportacao para o .zip ou a pasta)")
    if not arquivos:
        raise ErroDoLinkedIn(f"{caminho} não tem os CSV do perfil (Profile.csv, Positions.csv…)")
    partes = []
    for base in ARQUIVOS_DO_EXPORT:
        if base in arquivos:
            partes.append(f"== {base} ==\n{_csv_legivel(arquivos[base])}")
    return "\n\n".join(partes)


def _csv_legivel(texto: str) -> str:
    """Cada linha do CSV como `coluna: valor`; o export às vezes traz notas antes do cabeçalho."""
    linhas = texto.splitlines()
    inicio = next((i for i, linha in enumerate(linhas) if "," in linha and not linha.lower().startswith("notes")), 0)
    leitor = csv.DictReader(io.StringIO("\n".join(linhas[inicio:])))
    saida = []
    for registro in leitor:
        campos = [f"{chave}: {valor}" for chave, valor in registro.items() if chave and valor and valor.strip()]
        if campos:
            saida.append("- " + " | ".join(campos))
    return "\n".join(saida) or "(vazio)"


# -- a análise do perfil ------------------------------------------------------------------------

SISTEMA_DA_ANALISE = f"""\
Você revisa o perfil do LinkedIn de um desenvolvedor brasileiro para que RECRUTADORES e CLIENTES DE \
FREELA o achem e o chamem. Você recebe o export do perfil (CSV), o perfil que o Whis montou do trabalho \
dele e as regras e fatos dele. Devolva em português (o perfil é em português, salvo se o export mostrar \
outro idioma):
- "nota": 0 a 100, o quanto o perfil hoje ajuda a ser achado e chamado.
- "diagnostico": 4 a 8 frases: o que mais perde ponto, na ordem.
- "titulo": o título (headline) pronto para colar, até 220 caracteres, com cargo, stack principal e o \
que ele entrega; sem "open to work", sem "buscando oportunidades".
- "sobre": o "Sobre" pronto para colar, 800 a 1.600 caracteres, primeira pessoa, parágrafos curtos, \
termina dizendo como falar com ele pelo LinkedIn (sem telefone, sem e-mail).
- "experiencias": cada experiência do export reescrita: {{cargo, empresa, texto}} com 3 a 5 linhas de \
conquistas concretas, só com fatos do export ou do perfil — nada inventado.
- "competencias": as 15 competências que ele deve ter fixadas, das mais buscadas às menos.
- "antes_de_mexer": os passos de discrição ANTES de editar (desligar "Compartilhar atualizações do \
perfil com a rede", nunca ligar Open to Work, espalhar mudanças em semanas).
- "ajustes": outros ajustes curtos (foto, banner, URL personalizada, recomendações), até 6.
Ninguém do trabalho dele pode perceber que ele está procurando: nada de "novos desafios".
{REGRAS_DE_DISCRICAO}"""

ESQUEMA_DA_ANALISE = {
    "type": "object",
    "properties": {
        "nota": {"type": "integer"},
        "diagnostico": {"type": "string"},
        "titulo": {"type": "string"},
        "sobre": {"type": "string"},
        "experiencias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"cargo": {"type": "string"}, "empresa": {"type": "string"}, "texto": {"type": "string"}},
                "required": ["cargo", "empresa", "texto"],
                "additionalProperties": False,
            },
        },
        "competencias": {"type": "array", "items": {"type": "string"}},
        "antes_de_mexer": {"type": "array", "items": {"type": "string"}},
        "ajustes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["nota", "diagnostico", "titulo", "sobre", "experiencias", "competencias", "antes_de_mexer", "ajustes"],
    "additionalProperties": False,
}


class AnaliseDoPerfilClaude(_ChamadaDoClaude):
    etapa = "análise do perfil do LinkedIn"

    def __init__(self, **opcoes: Any) -> None:
        opcoes.setdefault("timeout_s", 900.0)
        super().__init__(**opcoes)

    def analisar(self, exportacao: str, perfil_do_whis: str, procuro: str, sobre_mim: str) -> dict[str, Any]:
        prompt = (
            f"EXPORT DO PERFIL DO LINKEDIN:\n{exportacao}\n\n"
            f"PERFIL QUE O WHIS MONTOU:\n{perfil_do_whis or '(ainda não há)'}\n\n"
            f"O QUE ELE PROCURA:\n{procuro}\n\nSOBRE MIM:\n{sobre_mim or '(em branco)'}"
        )
        chamada = self._chamar(prompt, self._opcoes(sistema=SISTEMA_DA_ANALISE, esquema=ESQUEMA_DA_ANALISE))
        return chamada.dados() or {}


def montar_analise(dados: dict[str, Any], quando: date) -> str:
    def lista(chave: str) -> list[str]:
        return [f"- {item}" for item in dados.get(chave) or []] or ["- —"]

    linhas = [
        "---",
        "tipo: linkedin-perfil",
        f"nota: {int(dados.get('nota', 0) or 0)}",
        f"analisado: {quando.isoformat()}",
        "---",
        "",
        "# O seu perfil do LinkedIn",
        "",
        "Tudo aqui é para **você** colar no LinkedIn; o Whis nunca mexe no perfil. Regenerada a cada `linkedin`.",
        "",
        f"**Nota de hoje: {int(dados.get('nota', 0) or 0)}/100**",
        "",
        str(dados.get("diagnostico", "")).strip(),
        "",
        "## Antes de mexer",
        "",
        *lista("antes_de_mexer"),
        "",
        "## Título",
        "",
        "```text",
        str(dados.get("titulo", "")).strip(),
        "```",
        "",
        "## Sobre",
        "",
        "```text",
        str(dados.get("sobre", "")).strip(),
        "```",
        "",
        "## Experiências",
        "",
    ]
    for experiencia in dados.get("experiencias") or []:
        if isinstance(experiencia, dict):
            linhas += [
                f"### {experiencia.get('cargo', '')} — {experiencia.get('empresa', '')}",
                "",
                "```text",
                str(experiencia.get("texto", "")).strip(),
                "```",
                "",
            ]
    linhas += ["## Competências para fixar", "", ", ".join(dados.get("competencias") or []) or "—", ""]
    linhas += ["## Outros ajustes", "", *lista("ajustes"), ""]
    return "\n".join(linhas)


# -- os posts -------------------------------------------------------------------------------------

SISTEMA_DOS_POSTS = f"""\
Você escreve posts de LinkedIn em PORTUGUÊS DO BRASIL para um desenvolvedor web brasileiro, na voz dele, \
para que recrutadores e clientes de freela o notem — sem que os colegas de trabalho percebam que ele \
procura emprego. Você recebe o perfil, o que ele fez nas últimas semanas (vault e git) e os posts que \
ele já publicou. Escreva os posts pedidos, cada um com UMA ideia, uma coisa verdadeira e específica do \
trabalho ou do aprendizado dele (técnica, ferramenta, erro e conserto, fluxo com IA, projeto pessoal).
Forma (método li-post): a primeira linha é o gancho e sobrevive sozinha ao corte de ~140 caracteres; a \
segunda paga o gancho; parágrafos de 1 a 3 linhas com linha em branco entre eles; uma virada; fecha com \
UMA pergunta específica. 600 a 1.300 caracteres. Números em vez de adjetivos.
Voz: direta, de quem faz; sem "Estou animado em anunciar", sem "Que jornada!", sem "Neste post", sem \
"Vamos juntos", sem "No mundo de hoje", sem emoji em excesso (no máximo 1), no máximo 3 hashtags no fim, \
sem travessão longo em toda frase, sem listas de três adjetivos.
Nunca: "novos desafios", "open to work", "em busca de oportunidades", nada sobre sair do emprego; nome \
do empregador, de clientes, de colegas ou de projetos internos; código, números ou métricas internas; \
algo que não aconteceu. Não repita assunto dos posts já publicados.
Para cada post: "titulo" (5 a 8 palavras, só para ele achar o rascunho), "texto" (o post, pronto) e \
"por_que" (uma frase: por que esse post ajuda a ser chamado).
{REGRAS_DE_DISCRICAO}"""

ESQUEMA_DOS_POSTS = {
    "type": "object",
    "properties": {
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"titulo": {"type": "string"}, "texto": {"type": "string"}, "por_que": {"type": "string"}},
                "required": ["titulo", "texto", "por_que"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["posts"],
    "additionalProperties": False,
}


class PostsClaude(_ChamadaDoClaude):
    etapa = "rascunhos de post do LinkedIn"

    def __init__(self, **opcoes: Any) -> None:
        opcoes.setdefault("timeout_s", 900.0)
        super().__init__(**opcoes)

    def escrever(self, quantos: int, evidencias: str, perfil_do_whis: str, publicados: Sequence[str]) -> list[dict[str, str]]:
        anteriores = "\n---\n".join(publicados[-10:]) or "(nenhum)"
        prompt = (
            f"ESCREVA {quantos} POST(S).\n\nPERFIL:\n{perfil_do_whis or '(ainda não há)'}\n\n"
            f"O QUE ELE FEZ (vault e git):\n{evidencias}\n\nPOSTS JÁ PUBLICADOS:\n{anteriores}"
        )
        chamada = self._chamar(prompt, self._opcoes(sistema=SISTEMA_DOS_POSTS, esquema=ESQUEMA_DOS_POSTS))
        posts = []
        for bruto in (chamada.dados() or {}).get("posts") or []:
            if isinstance(bruto, dict) and str(bruto.get("texto", "")).strip():
                posts.append({chave: str(bruto.get(chave, "")).strip() for chave in ("titulo", "texto", "por_que")})
        return posts[:quantos]


@dataclass(frozen=True)
class Post:
    """Um rascunho ou post publicado em `linkedin/posts/`."""

    caminho: str
    titulo: str
    status: str
    texto: str
    url: str = ""
    por_que: str = ""

    @property
    def rascunho(self) -> bool:
        return self.status == RASCUNHO


_FRONTMATTER = re.compile(r"\A---\n(?P<campos>.*?)\n---\n(?P<corpo>.*)\Z", re.S)


def escrever_rascunhos(vault: Path, posts: Sequence[dict[str, str]], quando: date) -> list[str]:
    raiz = Path(vault)
    caminhos = []
    for post in posts:
        base = f"{PASTA_DOS_POSTS}/{quando.isoformat()}-{_vault._slug(post['titulo'], 'post')[:50]}"
        caminho, numero = f"{base}.md", 2
        while (raiz / caminho).exists():
            caminho, numero = f"{base}-{numero}.md", numero + 1
        conteudo = "\n".join(
            [
                "---",
                "tipo: linkedin-post",
                f"status: {RASCUNHO}",
                f"titulo: {_vault._texto_yaml(post['titulo'])}",
                f"por_que: {_vault._texto_yaml(post.get('por_que', ''))}",
                "---",
                post["texto"].strip(),
                "",
            ]
        )
        _vault.escrever(raiz, caminho, conteudo, zonas=ZONAS_DO_LINKEDIN, literal=True)
        caminhos.append(caminho)
    return caminhos


def listar_posts(vault: Path) -> list[Post]:
    pasta = Path(vault) / PASTA_DOS_POSTS
    posts = []
    for arquivo in sorted(pasta.glob("*.md"), reverse=True) if pasta.is_dir() else ():
        post = ler_post(Path(vault), arquivo.relative_to(vault).as_posix())
        if post is not None:
            posts.append(post)
    return posts


def ler_post(vault: Path, caminho: str) -> Post | None:
    arquivo = Path(vault) / caminho
    try:
        texto = arquivo.read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError:
        return None
    casou = _FRONTMATTER.match(texto)
    if casou is None:
        return None
    campos = _campos(casou["campos"])
    return Post(
        caminho=caminho,
        titulo=campos.get("titulo", arquivo.stem),
        status=campos.get("status", RASCUNHO),
        texto=casou["corpo"].strip(),
        url=campos.get("url", ""),
        por_que=campos.get("por_que", ""),
    )


def marcar_publicado(vault: Path, caminho: str, url: str, quando: datetime) -> None:
    """Troca só o frontmatter: o corpo — o texto que ele editou — fica byte a byte."""
    arquivo = Path(vault) / caminho
    bruto = arquivo.read_bytes().decode("utf-8")
    quebra = "\r\n" if "\r\n" in bruto else "\n"
    texto = bruto.replace("\r\n", "\n")
    casou = _FRONTMATTER.match(texto)
    if casou is None:
        raise ErroDoLinkedIn(f"{caminho} perdeu o frontmatter")
    campos = [linha for linha in casou["campos"].split("\n") if not linha.startswith(("status:", "url:", "publicado:"))]
    campos += [f"status: {PUBLICADO}", f'url: "{url}"', f"publicado: {quando.isoformat(timespec='minutes')}"]
    novo = "---\n" + "\n".join(campos) + "\n---\n" + casou["corpo"]
    _vault.escrever(Path(vault), caminho, novo.replace("\n", quebra), zonas=ZONAS_DO_LINKEDIN, literal=True)


def _campos(bloco: str) -> dict[str, str]:
    campos = {}
    for linha in bloco.split("\n"):
        chave, _, valor = linha.partition(":")
        if chave.strip():
            valor = valor.strip()
            if len(valor) >= 2 and valor[0] == valor[-1] == '"':
                valor = valor[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            campos[chave.strip()] = valor
    return campos


# -- a API oficial ---------------------------------------------------------------------------------


def escapar_commentary(texto: str) -> str:
    """O `commentary` da Posts API é *little text*: estes caracteres precisam de barra invertida."""
    return re.sub(r"([\\|{}@\[\]()<>#*_~])", r"\\\1", texto)


def versao_da_api(hoje: date | None = None) -> str:
    """`LinkedIn-Version` é AAAAMM; uma versão de dois meses atrás está sempre no ar."""
    hoje = hoje or date.today()
    mes = hoje.month - 2
    ano = hoje.year + (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    return f"{ano}{mes:02d}"


class LinkedInAPI:
    """O login OAuth (código + `localhost`) e a publicação, com o token no cofre."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        cofre: Cofre,
        *,
        rede: httpx.BaseTransport | None = None,
        agora: Callable[[], float] = time.time,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.cofre = cofre
        self._rede = rede
        self._agora = agora

    def configurado(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def logado(self) -> bool:
        guardado = self.cofre.obter(CHAVE_NO_COFRE) or {}
        return bool(guardado.get("token")) and self._agora() < float(guardado.get("expira_em", 0))

    def dias_restantes(self) -> int | None:
        guardado = self.cofre.obter(CHAVE_NO_COFRE) or {}
        if not guardado.get("expira_em"):
            return None
        return max(0, int((float(guardado["expira_em"]) - self._agora()) // 86_400))

    def endereco_de_login(self, estado: str) -> str:
        return AUTORIZAR + "?" + urlencode(
            {"response_type": "code", "client_id": self.client_id, "redirect_uri": RETORNO, "state": estado, "scope": ESCOPOS}
        )

    def login(self, *, abrir: Callable[[str], Any] = webbrowser.open, esperar_s: float = ESPERA_DO_LOGIN_S) -> None:
        """Abre o navegador no consentimento, espera o retorno em `localhost` e guarda o token."""
        if not self.configurado():
            raise ErroDoLinkedIn("preencha [linkedin].client_id e [linkedin].client_secret (o app do LinkedIn Developers)")
        estado = secrets.token_urlsafe(16)
        recebido: dict[str, str] = {}
        servidor = HTTPServer(("127.0.0.1", PORTA_DO_RETORNO), _retorno(recebido))
        servidor.timeout = 1
        fio = threading.Thread(target=lambda: _atender_ate(servidor, recebido, esperar_s), daemon=True)
        fio.start()
        abrir(self.endereco_de_login(estado))
        fio.join(esperar_s + 2)
        servidor.server_close()
        if recebido.get("error"):
            raise ErroDoLinkedIn(f"o LinkedIn recusou o login: {recebido.get('error_description') or recebido['error']}")
        if recebido.get("state") != estado or not recebido.get("code"):
            raise ErroDoLinkedIn("o login não voltou do LinkedIn a tempo (ou voltou de outra tentativa)")
        self.trocar_codigo(recebido["code"])

    def trocar_codigo(self, codigo: str) -> None:
        with self._cliente() as cliente:
            resposta = cliente.post(
                TOKEN,
                data={
                    "grant_type": "authorization_code",
                    "code": codigo,
                    "redirect_uri": RETORNO,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            if resposta.status_code >= 400:
                raise ErroDoLinkedIn(f"o LinkedIn recusou o código (HTTP {resposta.status_code}): {resposta.text[:200]}")
            token = resposta.json()
            acesso = token.get("access_token")
            usuario = cliente.get(USERINFO, headers={"Authorization": f"Bearer {acesso}"})
            if usuario.status_code >= 400:
                raise ErroDoLinkedIn(f"o LinkedIn não disse quem é você (HTTP {usuario.status_code})")
        self.cofre.guardar(
            CHAVE_NO_COFRE,
            {
                "token": acesso,
                "expira_em": self._agora() + float(token.get("expires_in", 0)),
                "pessoa": f"urn:li:person:{usuario.json().get('sub')}",
                "nome": usuario.json().get("name", ""),
            },
        )

    def publicar(self, texto: str) -> str:
        """Publica no perfil dele e devolve o link do post. Levanta `ErroDoLinkedIn` em qualquer recusa."""
        texto = texto.strip()
        if not texto:
            raise ErroDoLinkedIn("o post está vazio")
        if len(texto) > LIMITE_DO_POST:
            raise ErroDoLinkedIn(f"o post tem {len(texto)} caracteres; o LinkedIn aceita até {LIMITE_DO_POST}")
        guardado = self.cofre.obter(CHAVE_NO_COFRE) or {}
        if not self.logado():
            raise ErroDoLinkedIn("sem login no LinkedIn (ou venceu, a cada 60 dias): rode 'whis linkedin-login'")
        corpo = {
            "author": guardado["pessoa"],
            "commentary": escapar_commentary(texto),
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        cabecalhos = {
            "Authorization": f"Bearer {guardado['token']}",
            "LinkedIn-Version": versao_da_api(),
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        with self._cliente() as cliente:
            resposta = cliente.post(POSTS, content=json.dumps(corpo, ensure_ascii=False).encode("utf-8"), headers=cabecalhos)
        if resposta.status_code == 401:
            raise ErroDoLinkedIn("o login do LinkedIn venceu: rode 'whis linkedin-login'")
        if resposta.status_code >= 400:
            raise ErroDoLinkedIn(f"o LinkedIn recusou o post (HTTP {resposta.status_code}): {resposta.text[:300]}")
        urn = resposta.headers.get("x-restli-id") or resposta.headers.get("x-linkedin-id") or ""
        return f"https://www.linkedin.com/feed/update/{urn}/" if urn else "https://www.linkedin.com/feed/"

    def _cliente(self) -> httpx.Client:
        return httpx.Client(transport=self._rede, timeout=30)


def _retorno(recebido: dict[str, str]):
    class Retorno(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 — nome da biblioteca
            partes = urlsplit(self.path)
            if partes.path != "/linkedin":
                self.send_response(404)
                self.end_headers()
                return
            recebido.update({chave: valores[0] for chave, valores in parse_qs(partes.query).items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<p>Pronto: pode fechar esta aba e voltar ao Whis.</p>".encode("utf-8"))

        def log_message(self, *_argumentos) -> None:
            return

    return Retorno


def _atender_ate(servidor: HTTPServer, recebido: dict[str, str], esperar_s: float) -> None:
    limite = time.monotonic() + esperar_s
    while not recebido and time.monotonic() < limite:
        servidor.handle_request()


# -- a costura ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ResultadoDoLinkedIn:
    analise: str | None
    rascunhos: tuple[str, ...]
    falhas: tuple[str, ...] = ()


def preparar_linkedin(
    vault: Path,
    *,
    exportacao: Path | None,
    analise: AnaliseDoPerfilClaude | Any,
    posts: PostsClaude | Any,
    quantos: int,
    evidencias: str,
    perfil_do_whis: str,
    procuro: str,
    sobre_mim: str,
    hoje: date,
) -> ResultadoDoLinkedIn:
    """`linkedin` na palheta: a análise (se o export existe) e os rascunhos. Nada é publicado."""
    raiz = _vault.preparar(vault)
    falhas: list[str] = []
    caminho_da_analise = None
    if exportacao is not None:
        try:
            dados = analise.analisar(ler_exportacao(exportacao), perfil_do_whis, procuro, sobre_mim)
            _vault.escrever(raiz, CAMINHO_DA_ANALISE, montar_analise(dados, hoje), zonas=ZONAS_DO_LINKEDIN)
            caminho_da_analise = CAMINHO_DA_ANALISE
        except Exception as erro:  # noqa: BLE001 — a análise não impede os rascunhos
            _log.warning("A análise do perfil do LinkedIn não saiu: %s", erro)
            falhas.append(f"análise do perfil: {erro}")
    else:
        falhas.append("análise do perfil: sem [linkedin].exportacao (baixe 'Baixar seus dados' no LinkedIn)")
    publicados = [post.texto for post in listar_posts(raiz) if post.status == PUBLICADO]
    rascunhos: list[str] = []
    try:
        novos = posts.escrever(quantos, evidencias, perfil_do_whis, publicados)
        rascunhos = escrever_rascunhos(raiz, novos, hoje)
    except Exception as erro:  # noqa: BLE001
        _log.warning("Os rascunhos do LinkedIn não saíram: %s", erro)
        falhas.append(f"rascunhos: {erro}")
    return ResultadoDoLinkedIn(caminho_da_analise, tuple(rascunhos), tuple(falhas))


def publicar_post(vault: Path, caminho: str, api: LinkedInAPI, *, agora: datetime | None = None) -> str:
    """O gesto dele: publica o rascunho como ele está na nota e marca a nota."""
    post = ler_post(Path(vault), caminho)
    if post is None:
        raise ErroDoLinkedIn(f"{caminho} não é um post do Whis")
    if post.status == PUBLICADO:
        raise ErroDoLinkedIn(f"{post.titulo} já foi publicado: {post.url}")
    url = api.publicar(post.texto)
    marcar_publicado(Path(vault), caminho, url, agora or datetime.now().astimezone())
    _log.info("LinkedIn: publicado %s → %s", caminho, url)
    return url
