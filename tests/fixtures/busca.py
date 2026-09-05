"""O cenário da busca: um vault habitado e uma configuração com pasta privada.

O vault tem nota pública, nota privada, uma vizinha de nome parecido com a
pasta privada (para pegar comparação por prefixo de texto) e as pastas do
Obsidian. Todas as notas falam da mesma retenção de 180 dias, de propósito: o
teste da fronteira é "o termo casa em todas, mas só as visíveis aparecem".
"""

from __future__ import annotations

from pathlib import Path

from second_brain.configuracao import Configuracao, carregar

PASTA_PRIVADA = "notas/pessoal"

NOTA_PUBLICA = "daily/2026-09-04.md"
NOTA_PUBLICA_ANTIGA = "daily/2026-09-01.md"
NOTA_DE_REUNIAO = "reunioes/2026-09-03-1403-reuniao.md"
NOTA_DO_USUARIO = "notas/ideias.md"
NOTA_VIZINHA_DA_PRIVADA = "notas/pessoal-trabalho.md"
NOTA_PRIVADA = "notas/pessoal/terapia.md"
NOTA_PRIVADA_FUNDA = "notas/pessoal/2026/consulta.md"
NOTA_NA_LIXEIRA = ".trash/velha.md"

CONTEUDO_PRIVADO = "Sessão de terapia: a retenção de 180 dias me tirou o sono."

NOTAS = {
    NOTA_PUBLICA: "# Daily\n\nRetenção de 180 dias ficou decidida com o Luan.\n",
    NOTA_PUBLICA_ANTIGA: "# Daily\n\nAinda sem decisão sobre a retenção de 180 dias.\n",
    NOTA_DE_REUNIAO: "# Reunião\n\n- Decidido: retenção de 180 dias para os logs\n",
    NOTA_DO_USUARIO: "# Ideias\n\numa ideia solta\n",
    NOTA_VIZINHA_DA_PRIVADA: "retenção de 180 dias também aparece aqui, fora da pasta privada\n",
    NOTA_PRIVADA: CONTEUDO_PRIVADO + "\n",
    NOTA_PRIVADA_FUNDA: "Consulta: retenção de 180 dias, de novo.\n",
    NOTA_NA_LIXEIRA: "retenção de 180 dias numa nota apagada\n",
}


def habitar_vault(vault: Path) -> Path:
    """Cria o vault do cenário e devolve a raiz."""
    for relativo, conteudo in NOTAS.items():
        arquivo = vault / relativo
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(conteudo, encoding="utf-8")
    (vault / ".obsidian").mkdir(exist_ok=True)
    (vault / ".obsidian" / "app.json").write_text("{}\n", encoding="utf-8")
    (vault / "anexos").mkdir(exist_ok=True)
    (vault / "anexos" / "foto.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return vault


def configuracao_da_busca(
    tmp_path: Path,
    vault: Path,
    gravacoes: Path,
    *,
    pastas_privadas: tuple[str, ...] = (),
    maximo_de_notas: int = 40,
) -> Configuracao:
    """Escreve um `config.toml` com as chaves da busca e o carrega do disco."""
    linhas = [
        f'vault = "{vault.as_posix()}"',
        f'gravacoes = "{gravacoes.as_posix()}"',
        "",
        "[privacidade]",
        "pastas_privadas = [" + ", ".join(f'"{pasta}"' for pasta in pastas_privadas) + "]",
        "",
        "[busca]",
        f"maximo_de_notas = {maximo_de_notas}",
        "",
    ]
    arquivo = tmp_path / "config-da-busca.toml"
    arquivo.write_text("\n".join(linhas), encoding="utf-8")
    return carregar(arquivo)
