# Executáveis

Cada pasta tem o programa pronto para rodar, com as pastas `assets/` e `pets/` ao lado (o programa
lê o conteúdo delas para você poder editar; sem elas, usa a cópia que vai dentro do executável). A `memory/`
é criada na primeira execução, dentro da mesma pasta; se a pasta não aceita gravação (por exemplo, dentro de
Arquivos de Programas), ela vai para `%LOCALAPPDATA%\Claude Super Power\memory`.

| Pasta | Sistema | Como abrir |
|---|---|---|
| `windows/` | Windows 10 (1809+) ou 11; o de x64 também roda no Windows 11 ARM (há um nativo ARM64 no GitHub) | duplo clique em `Pestinha.exe` |
| `macos/` | macOS | no Terminal, dentro da pasta: `./Pestinha` (o macOS pede permissão de Acessibilidade para o atalho Ctrl+Alt+Shift+B) |
| `linux/` | Linux (X11) | no terminal, dentro da pasta: `./Pestinha` |

O executável de macOS e Linux não sai daqui: é gerado pelo GitHub (workflow `executáveis`, na aba Actions,
ou nos Releases quando houver uma tag `v...`). Baixe o artefato do sistema que você quer.

O executável não é assinado: o Windows e o macOS podem avisar na primeira execução.
