# O X entra no jornal por um navegador logado numa conta só do Whis

> Registro de 2026-09-30.

A seção *Dev com IA* do jornal lê o X: a aba Seguindo, a aba Para você e seis buscas por termo, de
uma conta criada só para o Whis. O Playwright abre o Chrome instalado num perfil próprio
(`%LOCALAPPDATA%\whis\navegador-x`), lê o que a página mostra (link, @autor, hora, texto, curtidas)
e fecha. O usuário faz o login uma vez com `python -m whis x-login`; o Whis nunca vê a senha.
Spec em `.scratch/jornal-dev-com-ia/spec.md`.

## Por quê

Para ele, o X é hoje a melhor fonte de dica prática de desenvolvimento com IA (harness, skills,
prompts, economia de token), e não existe leitura grátis: desde fevereiro de 2026 a API oficial é
paga por post lido (US$ 0,005), o plano gratuito acabou, não há RSS e os espelhos como o Nitter
morreram ([pricing](https://docs.x.com/x-api/getting-started/pricing)).

## Considered Options

- **API oficial paga por uso**, lendo uma lista de contas: estimada entre US$ 10 e 30 por mês. Ele
  preferiu não pagar.
- **Busca no X pelo Grok** (xAI, US$ 5 a cada 1.000 posts mais os tokens): mesma objeção, e mais uma
  conta paga.
- **Só fontes abertas** (blogs, newsletters, changelogs, Reddit, Hacker News): perde o que só
  aparece no X.
- **Agente do Claude navegando sozinho**: gasta a assinatura em cada tela, é lento e muda todo
  dia.

## Consequências

- **Risco aceito por ele**: os termos do X proíbem leitura automatizada sem autorização. A conta do
  Whis pode ser limitada, travada para verificação ou suspensa; é por isso que não é a conta dele.
- **Só leitura, uma vez por edição**: oito páginas, algumas rolagens com pausa. O Whis nunca curte,
  segue, posta nem abre post.
- **Frágil por natureza**: quando o X muda a página, a seção diz "X indisponível hoje" e o resto do
  jornal sai. A leitura do HTML é Python puro, testado com fixtures, e o leitor guarda amostras
  (`amostras=`) para mostrar o que mudou.
- **Login vencido** vira aviso na seção e toast com o comando que conserta.
