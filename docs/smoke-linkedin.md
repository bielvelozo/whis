# Smoke manual: o LinkedIn do Whis

Roteiro da primeira vez **na sua máquina**, no PowerShell 5.1, de dentro de
`C:\Users\gabri\development\whis` (`python` = `.venv\Scripts\python.exe`).
Spec em `.scratch/vagas-e-freelas/spec-linkedin.md`.

## A regra

**Nada vai para o LinkedIn sem o seu gesto.** O Whis analisa o perfil e
escreve rascunhos no vault; publicar é Enter na lista `posts` da palheta, ou
`whis linkedin-publicar` respondendo `s`. Mudar o perfil e se candidatar no
LinkedIn continuam com você: o Whis entrega o texto pronto para colar.

## Passo 1 — Sem Claude

```
python -m whis linkedin --fakes
```

**Sucesso:** três linhas "Rascunho: linkedin/posts/…" num vault temporário,
"Faltou: análise do perfil: sem [linkedin].exportacao" e "Nada foi publicado".

## Passo 2 — O export do seu perfil (para a análise)

1. No LinkedIn: *Eu → Configurações e privacidade → Privacidade dos dados →
   Obter uma cópia dos seus dados*. Escolha **o pacote menor** (perfil,
   cargos, formação, competências); chega por e-mail em uns 10 minutos.
2. Baixe o `.zip` para uma pasta do PC.
3. Na palheta, `settings`: `[linkedin].exportacao` com o caminho do `.zip`
   (barras normais: `C:/Users/gabri/Downloads/Basic_LinkedInDataExport.zip`).

## Passo 3 — A análise e os rascunhos

Na palheta: `linkedin` (uns 5 minutos), ou `python -m whis linkedin`.

**Sucesso:** o toast *Rascunhos do LinkedIn prontos*, que abre
`linkedin/perfil.md`:

- **Antes de mexer**: desligue "Compartilhar atualizações do perfil com a
  rede" antes de colar qualquer coisa — senão seus colegas veem cada mudança.
  Nunca ligue *Open to Work*.
- Título, *Sobre*, cada experiência e as competências, prontos para colar
  (blocos com botão de copiar).

E os rascunhos em `linkedin/posts/`. **Edite à vontade no Obsidian**: o corpo
da nota é o post, palavra por palavra. Rascunho que você não quer: apague a
nota.

## Passo 4 — O app do LinkedIn (uma vez, para publicar)

1. Em <https://www.linkedin.com/developers/apps> → *Create app*. Ele pede uma
   Página do LinkedIn associada; use a opção padrão para desenvolvedor, ou crie
   uma página simples.
2. Na aba *Products*, adicione **Share on LinkedIn** e **Sign In with LinkedIn
   using OpenID Connect** (os dois são liberados na hora, sem revisão).
3. Na aba *Auth*, em *Authorized redirect URLs*, acrescente exatamente
   `http://localhost:8765/linkedin`.
4. Copie *Client ID* e *Primary Client Secret* para `settings`:
   `[linkedin].client_id` e `[linkedin].client_secret`.
5. No terminal:

```
python -m whis linkedin-login
```

O navegador abre o consentimento do LinkedIn; autorize. **Sucesso:** "Login
guardado no cofre; vale por 60 dias." O LinkedIn não dá renovação a apps
self-serve: a cada ~60 dias, rode de novo.

## Passo 5 — Publicar (o seu aval)

Na palheta: `posts`. A lista mostra os rascunhos (✎) e os já publicados (✓);
o detalhe mostra o texto inteiro. **Enter publica o selecionado** — é o único
jeito de um post sair. `Ctrl E` abre a nota para editar antes.

**Sucesso:** a mensagem "Published: https://www.linkedin.com/feed/update/…" e a
nota com `status: publicado` e o link. O texto da nota não muda.

Pelo terminal, o mesmo com confirmação:

```
python -m whis linkedin-publicar linkedin/posts/AAAA-MM-DD-titulo.md
```

## Riscos declarados

- O cabeçalho `LinkedIn-Version` usa a versão de dois meses atrás; se o
  LinkedIn recusar com 426, é ele.
- Criar o app pede uma Página do LinkedIn; se a opção padrão não aparecer,
  uma página com o seu nome serve e ninguém precisa segui-la.
- Caracteres especiais (`#`, `@`, `(`…) saem como texto: hashtag vira texto
  com `#`, menção vira texto com `@`.
