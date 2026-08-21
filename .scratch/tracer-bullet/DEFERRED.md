# Trabalho deferido — tracer bullet

Achados fora do escopo do ticket em que apareceram. Uma linha por achado:
o quê, onde, por que ficou de fora.

- **Caminho Windows com barra invertida quebra o TOML** — `src/second_brain/configuracao.py`: `vault = "C:\Users\..."` falha com "Invalid hex value" e a mensagem não ensina a usar barra normal ou escapar. Fora do 01 (nenhum critério de aceite cobre ergonomia de setup); cabe na camada 05, junto da CLI unificada. (camada 01)
- **Não há comando que crie o `config.toml` inicial** — hoje o usuário escreve o arquivo à mão em `%APPDATA%\second-brain\`. Um `second-brain init` seria a hora certa; fora do 01, que só precisa ler a configuração. (camada 01)
- **Frontmatter é montado à mão, sem YAML de verdade** — `src/second_brain/vault.py`: escalares e listas inline bastam para os campos do contrato, e o ADR 0001 pede projeto fino (PyYAML seria dependência nova). Só vira problema se algum campo futuro precisar de bloco multilinha. (camada 01)
