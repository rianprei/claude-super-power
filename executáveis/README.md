# Executáveis

Cada pasta tem o programa pronto para rodar, com as pastas `assets/` e `pets/` ao lado (o programa
lê o conteúdo delas para você poder editar; sem elas, usa a cópia que vai dentro do executável). A `memory/`
é criada na primeira execução, dentro da mesma pasta; se a pasta não aceita gravação (por exemplo, dentro de
Arquivos de Programas), ela vai para `%LOCALAPPDATA%\Claude Super Power\memory`.

| Pasta / artefato | Sistema | Como abrir |
|---|---|---|
| `windows/` (`windows-x64`, `windows-arm64`) | Windows 10 (1809+) ou 11; o x64 também roda no Windows 11 ARM | duplo clique em `Pestinha.exe` |
| `windows-legado-32bits` | Windows 7 SP1, 8, 8.1, 10 e 11, de 32 ou 64 bits | duplo clique em `Pestinha.exe` |
| `macos-apple-silicon`, `macos-intel` | macOS 15 ou mais novo | descompacte e abra `Pestinha.app` (na primeira vez: botão direito > Abrir) |
| `macos-compativel` | macOS 10.14 a 14 (no Apple Silicon, pelo Rosetta) | idem |
| `macos-legado` | macOS 10.13 | idem |
| `linux-x64`, `linux-arm64` | glibc 2.35+ (x64) ou 2.39+ (ARM64): Debian 12+, Ubuntu 22.04+, Mint 21+, Fedora, Arch, Kali... | `tar -xzf` e `./Pestinha/Pestinha` |
| `linux-compativel` | glibc 2.28 a 2.34: Debian 10/11, Ubuntu 20.04, RHEL 8/9, openSUSE Leap 15 | idem |
| `linux-legado` | glibc 2.17 a 2.27: CentOS 7, Ubuntu 16.04 e 18.04 | idem |
| `android-aarch64` (workflow `android`) | Android 10 ou mais novo (celular); `android-x86_64` para emulador | instale o `.apk` (permitir fontes desconhecidas) |

No macOS a memória fica em `~/Library/Application Support/Claude Super Power/`; no Android, na pasta privada do app.

Só o de Windows x64 fica aqui; os outros são gerados pelo GitHub (workflows `executáveis` e `android`, na aba
Actions, ou nos Releases quando houver uma tag `v...`). Baixe o artefato do sistema que você quer.

O executável não é assinado: o Windows e o macOS podem avisar na primeira execução.
