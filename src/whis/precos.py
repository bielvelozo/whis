"""O piso de preço do freela (`[cacada].piso_freela`) conferido no texto que o Claude escreveu.

O preço sugerido vem em prosa ("Orçamento R$ 300 - 600; pedir R$ 150"), então a
conferência lê os valores com moeda, tira os que são do orçamento publicado e,
se algum dos que sobram fica abaixo do piso em reais, acrescenta o aviso no fim.
A conversão é a de bom senso que a triagem já usa (US$ 1 ≈ R$ 5,40).
"""

from __future__ import annotations

import re

EM_REAIS = {
    "R$": 1.0, "BRL": 1.0,
    "US$": 5.4, "USD": 5.4, "$": 5.4,
    "€": 6.0, "EUR": 6.0,
    "£": 7.0, "GBP": 7.0,
    "₹": 0.065, "INR": 0.065,
    "AUD": 3.5, "CAD": 3.9,
}

_VALOR = re.compile(r"(R\$|US\$|BRL|USD|EUR|GBP|INR|AUD|CAD|[$€£₹])\s?(\d[\d.,]*\d|\d)")


def _numero(texto: str) -> float | None:
    if "," in texto and "." in texto:
        decimal = "," if texto.rfind(",") > texto.rfind(".") else "."
    elif "," in texto:
        decimal = "," if re.search(r",\d{2}$", texto) else ""
    elif "." in texto:
        decimal = "" if re.search(r"\.\d{3}$", texto) else "."
    else:
        decimal = ""
    milhar = {",": ".", ".": ",", "": ".,"}[decimal]
    limpo = texto.translate(str.maketrans("", "", milhar))
    try:
        return float(limpo.replace(",", "."))
    except ValueError:
        return None


def pedido_do_piso(piso: int) -> str:
    """A linha que vai no fim de *O que eu procuro*: a triagem, o resumo, o pacote e as mensagens leem."""
    return (
        f"- Piso de freela: nunca sugira preço de freela abaixo de R$ {piso} (US$ 1 ≈ R$ 5,40), nem em projeto "
        f'pequeno. Freela cujo orçamento máximo fica abaixo do piso é no máximo "tentar_a_sorte", e o preço '
        "sugerido nele é o piso."
    )


def valores(texto: str) -> list[tuple[str, float]]:
    """Os valores com moeda do texto, na ordem, como (moeda, número)."""
    lidos = ((moeda, _numero(numero)) for moeda, numero in _VALOR.findall(texto))
    return [(moeda, numero) for moeda, numero in lidos if numero is not None]


def conferir_piso(preco: str, orcamento: str, piso: int) -> str:
    """`preco` com o aviso do piso no fim, se a sugestão (o que não é orçamento) fica abaixo dele."""
    if piso <= 0 or not preco.strip():
        return preco
    do_orcamento = {numero for _, numero in valores(orcamento)}
    sugeridos = [(moeda, numero) for moeda, numero in valores(preco) if numero not in do_orcamento]
    if not any(numero * EM_REAIS[moeda] < piso for moeda, numero in sugeridos):
        return preco
    return f"{preco.rstrip()} Abaixo do seu piso: peça pelo menos R$ {piso}."
