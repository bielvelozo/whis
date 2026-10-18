"""O lembrete às agências: 7 dias depois do primeiro e-mail, uma mensagem no celular com o texto curto."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from whis.lembrete_das_agencias import lembrar

FUSO = timezone(timedelta(hours=-3))

PROGRAMADOS = """\
---
tipo: rascunhos
criado: 2026-10-17
estado: programados no Gmail (gabrielvelozodev@gmail.com) em 18/10, para 19, 20 e 21/10 às 9h
---

# E-mails para as 10 primeiras agências

| Dia | Agências |
|---|---|
| Segunda, 19/10 | Aloft, DABS |
| Terça, 20/10 | HAUTE |

---

## 1. Aloft (Criciúma/SC) · peça: tema

**Para:** contato@aloftagencia.com (site). Alternativa: WhatsApp +55 48 99161-2650.
**Assunto:** Dev Shopify para seções sob medida

Oi, pessoal da Aloft,

---

## 2. DABS Design (Curitiba/PR) · peça: tema

**Para:** contato@dabsdesign.com.br (perfil de parceiro da Shopify).
**Assunto:** Dev Shopify para tema e suporte mensal

---

## 4. HAUTE Ecommerce (Florianópolis/SC) · peça: tema

**Para:** contato@hautecommerce.com.br (site).
**Assunto:** Dev Shopify para as lojas da HAUTE
"""


def _vault(tmp_path: Path, programados: str = PROGRAMADOS) -> Path:
    vault = tmp_path / "vault"
    (vault / "cacada").mkdir(parents=True)
    (vault / "cacada" / "emails-agencias.md").write_text(programados, encoding="utf-8")
    return vault


def _rodar(tmp_path: Path, vault: Path, dia: datetime, *, celular_responde: bool = True, emails: dict | None = None):
    mensagens: list[str] = []
    estado_dos_emails = tmp_path / "agencias-emails.json"
    if emails is not None:
        estado_dos_emails.write_text(json.dumps({"emails": emails}), encoding="utf-8")
    lembradas = lembrar(
        vault,
        estado=tmp_path / "lembretes-agencias.json",
        estado_dos_emails=estado_dos_emails,
        celular=lambda texto: mensagens.append(texto) or celular_responde,
        agora=dia,
    )
    return lembradas, mensagens


def test_sete_dias_depois_do_email_programado_chega_o_lembrete_uma_vez(tmp_path: Path):
    vault = _vault(tmp_path)

    antes, nada = _rodar(tmp_path, vault, datetime(2026, 10, 25, 22, 0, tzinfo=FUSO))
    lembradas, mensagens = _rodar(tmp_path, vault, datetime(2026, 10, 26, 7, 0, tzinfo=FUSO))
    de_novo, mais_nada = _rodar(tmp_path, vault, datetime(2026, 10, 26, 8, 0, tzinfo=FUSO))

    assert antes == [] and nada == []
    assert [l.nome for l in lembradas] == ["Aloft", "DABS Design"]
    aloft = mensagens[0]
    assert aloft.splitlines()[0] == "Lembrete de follow-up: faz 7 dias do e-mail para a Aloft"
    assert "contato@aloftagencia.com" in aloft and "19/10" in aloft
    assert "Dev Shopify para seções sob medida" in aloft
    assert "Oi, pessoal da Aloft," in aloft and "Gabriel Velozo" in aloft
    assert "Se já responderam, ignore" in aloft and "não insista" in aloft
    assert "contato@dabsdesign.com.br" in mensagens[1] and "Dev Shopify para tema e suporte mensal" in mensagens[1]
    assert de_novo == [] and mais_nada == []


def test_o_do_dia_seguinte_espera_o_proprio_setimo_dia(tmp_path: Path):
    vault = _vault(tmp_path)

    _rodar(tmp_path, vault, datetime(2026, 10, 26, 7, 0, tzinfo=FUSO))
    lembradas, mensagens = _rodar(tmp_path, vault, datetime(2026, 10, 27, 7, 0, tzinfo=FUSO))

    assert [l.email for l in lembradas] == ["contato@hautecommerce.com.br"]
    assert "Oi, pessoal da HAUTE Ecommerce," in mensagens[0]


def test_o_email_mandado_pelo_botao_tambem_ganha_lembrete(tmp_path: Path):
    vault = _vault(tmp_path, "---\ncriado: 2026-10-17\n---\n")
    emails = {
        "contato@econverse.com.br": {
            "nome": "Econverse", "situacao": "enviado", "assunto": "Dev Shopify para os picos", "enviado": "2026-10-22T10:05-03:00",
        },
        "comercial@checkcommerce.com.br": {"nome": "Check Commerce", "situacao": "para_aprovar", "quando": "2026-10-22T10:00-03:00"},
    }

    cedo, _ = _rodar(tmp_path, vault, datetime(2026, 10, 28, 23, 0, tzinfo=FUSO), emails=emails)
    lembradas, [mensagem] = _rodar(tmp_path, vault, datetime(2026, 10, 29, 7, 0, tzinfo=FUSO), emails=emails)

    assert cedo == []
    assert [l.nome for l in lembradas] == ["Econverse"]
    assert "Dev Shopify para os picos" in mensagem and "22/10" in mensagem


def test_sem_celular_o_lembrete_fica_para_a_proxima_rodada(tmp_path: Path):
    vault = _vault(tmp_path)

    sem_telegram, tentadas = _rodar(tmp_path, vault, datetime(2026, 10, 26, 7, 0, tzinfo=FUSO), celular_responde=False)
    depois, mensagens = _rodar(tmp_path, vault, datetime(2026, 10, 26, 8, 0, tzinfo=FUSO))

    assert sem_telegram == [] and len(tentadas) == 2
    assert len(depois) == 2 and len(mensagens) == 2


def test_lembrete_atrasado_demais_nao_chega(tmp_path: Path):
    vault = _vault(tmp_path)

    lembradas, mensagens = _rodar(tmp_path, vault, datetime(2026, 11, 5, 7, 0, tzinfo=FUSO))

    assert lembradas == [] and mensagens == []


def test_sem_nota_e_sem_estado_nao_ha_lembrete_nem_erro(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()

    assert _rodar(tmp_path, vault, datetime(2026, 10, 26, 7, 0, tzinfo=FUSO)) == ([], [])
