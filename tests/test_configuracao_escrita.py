"""O escritor de TOML: `configuracao.escrever`, provado por ida e volta.

`tomllib` só lê, e nenhum escritor entrou como dependência: o arquivo é
regenerado do modelo, com os comentários dele. O que se prova é que
`carregar → escrever → tomllib → carregar` devolve a mesma `Configuracao`
(inclusive com valores que precisam de escape), que o backup nasce com o nome
e o conteúdo certos, que um resultado inválido não substitui o arquivo, e que
o arquivo sai em UTF-8 sem BOM.
"""

from __future__ import annotations

import tomllib
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from whis import __main__ as cli
from whis.configuracao import (
    CHAVES,
    MODELO_DE_CONFIGURACAO,
    ConfiguracaoInvalida,
    carregar,
    escrever,
    gerar_toml,
    valores_de,
)

COMPLETO = """\
vault = "C:/Users/gabí/whis-vault"
gravacoes = "C:/Users/gabí/whis-gravacoes"
retencao_dias = 12

[deepgram]
api_key = "dg-#segredo\\"com aspas\\" e \\\\ barra"

[claude]
modelo = "claude-opus-5"

[audio]
dispositivo_microfone = "Microfone (Realtek)"
dispositivo_sistema = "Alto-falantes (Realtek)"

[diario]
inicio_do_dia = "05:00"
hora_da_tarefa = "18:30"

[daily]
referencias_pessoais = ["whis", "meu-blog"]
contexto_do_time = "Ele disse \\"ok\\".\\nSegunda linha com \\\\ e acento: ação"
horarios = { segunda = "13:55", quarta = "10:25", domingo = "09:00" }

[palheta]
atalho = "ctrl+shift+k"

[privacidade]
excluir = ["senha", "a\\"b", "c\\\\d"]
pastas_privadas = ["notas/pessoal", "notas/terapia"]

[busca]
maximo_de_notas = 25

[git]
raiz = "C:/Users/gabí/development"
profundidade = 2
excluir = ["node_modules"]
autores = ["gabi@x.com"]

[linear]
api_key = "lin_api_xxx"

[slack]
user_token = "xoxp-1"
conversas_excluidas = ["#random"]
so_com_mencao = ["#dev-codereview"]
bot_token = "xoxb-2"
app_token = "xapp-3"

[obsidian]
vault = "245833c11ad43e6e"
"""


def sem_origem(configuracao):
    return replace(configuracao, origem=None)


@pytest.fixture
def completo(tmp_path: Path):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(COMPLETO, encoding="utf-8")
    return carregar(arquivo)


# -- ida e volta ---------------------------------------------------------------


def test_ida_e_volta_devolve_a_mesma_configuracao(completo, tmp_path: Path):
    destino = tmp_path / "saida" / "config.toml"

    escrever(completo, destino)

    dados = tomllib.loads(destino.read_text(encoding="utf-8"))
    assert dados["deepgram"]["api_key"] == 'dg-#segredo"com aspas" e \\ barra'
    assert dados["daily"]["contexto_do_time"] == 'Ele disse "ok".\nSegunda linha com \\ e acento: ação'
    assert dados["privacidade"]["excluir"] == ["senha", 'a"b', "c\\d"]
    assert dados["daily"]["horarios"] == {"segunda": "13:55", "quarta": "10:25", "domingo": "09:00"}
    assert sem_origem(carregar(destino)) == sem_origem(completo)


def test_o_padrao_do_init_tambem_faz_ida_e_volta(tmp_path: Path):
    destino = tmp_path / "config.toml"
    assert cli.main(["init", "--config", str(destino)]) == 0
    original = carregar(destino)

    escrever(original, destino)

    assert sem_origem(carregar(destino)) == sem_origem(original)


def test_os_comentarios_do_modelo_sobrevivem_e_os_do_usuario_nao(completo, tmp_path: Path):
    destino = tmp_path / "config.toml"
    destino.write_text(COMPLETO + "\n# um lembrete meu\n", encoding="utf-8")

    escrever(completo, destino)

    texto = destino.read_text(encoding="utf-8")
    assert "# crédito de US$ 200; sem ela o STT real não roda" in texto
    assert "# o atalho global que abre a palheta" in texto
    assert "um lembrete meu" not in texto
    assert texto.startswith("# Configuração do Whis.")


def test_caminhos_saem_com_barra_normal_e_git_desligado_sai_vazio(completo, tmp_path: Path):
    configuracao = replace(completo, vault=Path(r"C:\Users\x\vault"), git_raiz=None)

    texto = gerar_toml(valores_de(configuracao))

    assert 'vault = "C:/Users/x/vault"' in texto
    assert 'raiz = ""' in texto
    assert "\\" not in texto.split("[deepgram]")[0]
    assert carregar_de(texto, tmp_path).git_raiz is None


def carregar_de(texto: str, tmp_path: Path):
    arquivo = tmp_path / "gerado.toml"
    arquivo.write_text(texto, encoding="utf-8")
    return carregar(arquivo)


def test_toda_chave_do_modelo_e_escrita_e_nenhuma_a_mais(completo):
    do_modelo = tomllib.loads(MODELO_DE_CONFIGURACAO.format(vault="V", gravacoes="G"))
    gerado = tomllib.loads(gerar_toml(valores_de(completo)))

    assert _achatar(gerado).keys() == _achatar(do_modelo).keys()
    assert len(CHAVES) == len(_achatar(do_modelo)) == 27


def _achatar(dados: dict) -> dict[str, object]:
    achatado: dict[str, object] = {}
    for nome, valor in dados.items():
        if isinstance(valor, dict) and nome != "horarios":
            for sub, v in valor.items():
                achatado[f"[{nome}].{sub}"] = v
        else:
            achatado[nome] = valor
    return achatado


# -- backup e substituição ------------------------------------------------------


def test_o_backup_nasce_com_o_nome_e_o_conteudo_de_antes(completo, tmp_path: Path):
    destino = tmp_path / "config.toml"
    destino.write_text(COMPLETO, encoding="utf-8")

    escrever(replace(completo, retencao_dias=3), destino, agora=datetime(2026, 9, 12, 14, 3, 7))

    backup = tmp_path / "config.toml.bak-20260912-140307"
    assert backup.read_text(encoding="utf-8") == COMPLETO
    assert carregar(destino).retencao_dias == 3
    assert sorted(p.name for p in tmp_path.iterdir()) == ["config.toml", "config.toml.bak-20260912-140307"]


def test_sem_arquivo_anterior_nao_ha_backup(completo, tmp_path: Path):
    destino = tmp_path / "nova" / "config.toml"

    escrever(completo, destino, agora=datetime(2026, 9, 12, 14, 3, 7))

    assert [p.name for p in destino.parent.iterdir()] == ["config.toml"]


def test_configuracao_que_nao_carrega_nao_substitui_o_arquivo(completo, tmp_path: Path):
    destino = tmp_path / "config.toml"
    destino.write_text(COMPLETO, encoding="utf-8")

    with pytest.raises(ConfiguracaoInvalida, match="retencao_dias"):
        escrever(replace(completo, retencao_dias=-1), destino)

    assert destino.read_text(encoding="utf-8") == COMPLETO
    assert [p.name for p in tmp_path.iterdir()] == ["config.toml"]


def test_o_arquivo_sai_em_utf8_sem_bom_e_com_quebra_de_linha_simples(completo, tmp_path: Path):
    destino = tmp_path / "config.toml"

    escrever(completo, destino)

    bytes_ = destino.read_bytes()
    assert not bytes_.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in bytes_
    assert "gabí".encode("utf-8") in bytes_


def test_escrever_nao_leva_segredo_nenhum_ao_log(completo, tmp_path: Path, caplog):
    with caplog.at_level("DEBUG", logger="whis"):
        escrever(completo, tmp_path / "config.toml")

    for segredo in ("dg-#segredo", "lin_api_xxx", "xoxp-1", "xoxb-2", "xapp-3"):
        assert segredo not in caplog.text
