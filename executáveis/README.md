# Executáveis

Cada pasta tem o programa pronto para rodar, com as pastas `assets/` e `pets/` ao lado (o programa
lê o conteúdo delas para você poder editar; sem elas, usa a cópia que vai dentro do executável). A `memory/`
é criada na primeira execução, dentro da mesma pasta; se a pasta não aceita gravação (por exemplo, dentro de
Arquivos de Programas), ela vai para `%LOCALAPPDATA%\Claude Super Power\memory`.

| Pasta | Sistema | Como abrir |
|---|---|---|
| `windows/` | Windows 10 (1809+) ou 11; o de x64 também roda no Windows 11 ARM (há um nativo ARM64 no GitHub) | duplo clique em `Pestinha.exe` |
| `macos-*` (artefato do GitHub) | macOS 15+ (`macos-apple-silicon` ou `macos-intel`) ou 10.14 a 14 (`macos-compativel`; no Apple Silicon roda pelo Rosetta) | descompacte e abra `Pestinha.app` (na primeira vez: botão direito > Abrir); a memória fica em `~/Library/Application Support/Claude Super Power/` |
| `linux/` | Linux (X11) | no terminal, dentro da pasta: `./Pestinha` |

O executável de macOS e Linux não sai daqui: é gerado pelo GitHub (workflow `executáveis`, na aba Actions,
ou nos Releases quando houver uma tag `v...`). Baixe o artefato do sistema que você quer.

O executável não é assinado: o Windows e o macOS podem avisar na primeira execução.
