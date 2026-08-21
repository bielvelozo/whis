"""Fakes das portas: implementações de verdade que devolvem dados fixos.

Não são mocks — não gravam chamadas nem se deixam interrogar sobre elas. São
os adaptadores que os testes (e a demo da camada 01) injetam no lugar da
Deepgram e do Claude. Os testes verificam só o que aparece no vault.
"""

from __future__ import annotations

from .portas import EU, OUTROS, CanaisDaGravacao, Fala, Resumo, Transcricao

#: Transcrição de exemplo — pt-BR com termos em inglês, como as reuniões reais.
TRANSCRICAO_PADRAO = Transcricao(
    falas=(
        Fala(EU, "Bom dia, pessoal. Vamos começar pela daily?", 0.0),
        Fala(OUTROS, "Bom dia! Ontem terminei o deploy do pipeline novo.", 3.2),
        Fala(EU, "Fechado. Então o rollback fica pra depois do review.", 9.8),
        Fala(OUTROS, "Combinado, eu abro a issue ainda hoje.", 14.1),
    ),
)

#: Resumo de exemplo, na estrutura que a nota de reunião espera.
RESUMO_PADRAO = Resumo(
    decisoes=("O rollback fica para depois do review.",),
    acoes=("Abrir a issue do rollback ainda hoje.",),
    topicos=("Deploy do pipeline novo", "Planejamento do rollback"),
)


class STTFake:
    """Porta de STT que devolve sempre a mesma transcrição.

    `erro` faz a transcrição falhar — é a costura de que as camadas 03 e 06
    precisam para os casos de falha; a camada 01 não os exercita.
    """

    def __init__(
        self,
        transcricao: Transcricao = TRANSCRICAO_PADRAO,
        erro: Exception | None = None,
    ) -> None:
        self._transcricao = transcricao
        self._erro = erro

    def transcrever(self, canais: CanaisDaGravacao) -> Transcricao:
        if self._erro is not None:
            raise self._erro
        return self._transcricao


class ResumoFake:
    """Porta de resumo que devolve sempre o mesmo resumo em português."""

    def __init__(self, resumo: Resumo = RESUMO_PADRAO, erro: Exception | None = None) -> None:
        self._resumo = resumo
        self._erro = erro

    def resumir(self, transcricao: Transcricao, titulo: str | None = None) -> Resumo:
        if self._erro is not None:
            raise self._erro
        return self._resumo
