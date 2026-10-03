"""A regra de quem envia, escrita em código e não em prompt (ticket 06 e research 02b).

O Whis só manda sozinho o que é **tentar a sorte**, e só onde mandar é **grátis e
sem limite**. A pesquisa 02b achou que nenhum site de freela passa nessa régua
(Workana e 99Freelas limitam, Upwork e Freelancer cobram), então **freela nunca
sai sozinho**. Vaga sai pelos formulários que não cobram nem limitam: a Gupy e os
ATS das empresas. **LinkedIn nunca** — os colegas dele o seguem. Golpe nunca. O
que já foi tentado uma vez, nunca de novo.

A chance boa não passa por aqui: ela é dele, sempre.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from .acoes import CANDIDATURA, Registro
from .oportunidades import FREELA, TENTAR_A_SORTE, Oportunidade, Veredito

#: Onde candidatar é grátis e sem limite: a Gupy (conta única dele) e os ATS das empresas.
DOMINIOS_GRATIS_E_SEM_LIMITE = (
    "gupy.io",
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workable.com",
    "breezy.hr",
    "recruitee.com",
    "teamtailor.com",
)

#: Nunca, por regra dele.
DOMINIOS_PROIBIDOS = ("linkedin.com",)


def dominio(link: str) -> str:
    return (urlsplit(link).hostname or "").lower().removeprefix("www.")


def casa(host: str, dominios: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith("." + d) for d in dominios)


def pode_enviar_sozinho(
    oportunidade: Oportunidade, veredito: Veredito, registro: Registro, *, ligado: bool
) -> tuple[bool, str]:
    """`(True, "")` ou `(False, motivo)`. O motivo vai para o relatório."""
    host = dominio(oportunidade.link)
    if not ligado:
        return False, "envio sozinho desligado ([cacada].enviar_sozinho = false)"
    if casa(host, DOMINIOS_PROIBIDOS):
        return False, "LinkedIn: nunca automático"
    if veredito.classe != TENTAR_A_SORTE:
        return False, "só tentar a sorte sai sozinho"
    if veredito.golpe:
        return False, "sinal de golpe"
    if oportunidade.tipo == FREELA:
        return False, "freela: nenhum site é grátis e sem limite"
    if not casa(host, DOMINIOS_GRATIS_E_SEM_LIMITE):
        return False, f"{host or 'sem link'}: não é um formulário grátis e sem limite conhecido"
    if registro.ja_tentado(CANDIDATURA, oportunidade.link):
        return False, "já tentada antes"
    return True, ""
