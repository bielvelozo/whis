Status: resolved
Blocked by: 00

# Leitor logado (Playwright no perfil da caçada)

Módulo novo que abre o perfil `navegador-cacada` com Playwright (persistente, channel chrome, janela fora da tela), lê páginas, diz por site se está logado, trata perfil em uso e Chrome ausente, e tem um fake para os testes. Nada de agente do Claude.

## Answer

Módulo novo `src/whis/navegador_logado.py`. `NavegadorLogado().abrir()` devolve uma `SessaoLogada` com `html(url)`, `logado(site)` e `fechar()`, que também funciona como gerenciador de contexto. O Chrome só liga na primeira página pedida: Playwright Python, `launch_persistent_context` no perfil `navegador_agente.pasta_do_perfil()`, `channel="chrome"`, `headless=False` e janela em `--window-position=-32000,-32000`. Chrome ausente, perfil em uso (ProcessSingleton/"already in use"), Playwright ausente ou timeout viram `sessao.motivo`; `logado()` responde False e a caçada segue sem login. O login de cada site é conferido uma vez por sessão, pelos marcadores de research/marcadores.md, numa página de conferência por site.

Os leitores são funções puras sobre o HTML: `ler_freelancer`, `ler_99freelas`, `ler_proposta_da_99freelas`, `ler_listagem_da_vintepila`, `ler_projeto_da_vintepila` e `logado_no_html`. Estão testados com as 19 fixtures reais em `tests/test_cacada_logada.py`. Porta nova `PortasDaCacada.navegador_logado` (None nos fakes, `NavegadorLogado()` em `montar_portas_da_cacada`), e o fake `NavegadorLogadoFake` em `fakes_da_cacada.py` devolve o HTML por URL. O `conftest` tranca o `_playwright` do módulo novo. O Playwright de verdade não roda na suíte: o lançamento é testado com um gerente fake.

A sessão abre e fecha dentro de cada bloco de leitura (coleta, conferência antes do preparo, cada rodada extra) e nunca fica aberta durante uma chamada ao Claude.
