# Histórico de versões

## Claude Super Power

- Windows:
  - No Super Saiyajin, a aura semitransparente não bloqueia mais o clique no que está atrás dela.
    Com o cursor fora do corpo, o clique atravessa a janela (WS_EX_TRANSPARENT).
  - Com DPI misto (notebook a 150% e monitor a 100%), o pouso nas barras de título e o olhar para a janela
    ativa erravam a posição nas outras telas. Agora cada tela usa a própria escala.
  - Salvar não falha mais quando o antivírus, o indexador ou o OneDrive estão com o arquivo aberto: a troca
    tenta de novo por até meio segundo.
  - Numa pasta sem permissão de gravação (Arquivos de Programas), a memória vai para
    `%LOCALAPPDATA%\Claude Super Power\memory`. Antes, nada era salvo.
  - O executável leva `assets/` e `pets/` dentro dele: baixado sozinho, ele já tem todos os pets. As pastas ao
    lado continuam valendo e têm prioridade.
  - CI no Windows mais novo, no 2022 e no Windows 11 ARM64, com um teste que abre uma janela de verdade.
    O executável agora também sai em ARM64.
- macOS (10.14 ou mais novo, Intel e Apple Silicon):
  - O pet, a bolinha, os cartazes e os painéis sumiam sempre que outro app ficava ativo. O Qt esconde janelas
    do tipo ferramenta quando o app perde o foco, e o pet nunca pega o foco. Agora ficam visíveis
    (WA_MacAlwaysShowToolWindow).
  - Sem sombra nas janelas transparentes: ela ficava para trás como um fantasma a cada quadro.
  - O clique atravessa a aura do Super Saiyajin (ignoresMouseEvents com o cursor fora do corpo), como no
    Windows.
  - O executável é um `Pestinha.app`, com a memória em `~/Library/Application Support/Claude Super Power/`
    (gravar dentro do .app quebra a assinatura). Sai em três versões: Apple Silicon e Intel (macOS 15+) e
    uma compatível (10.14 a 14; Apple Silicon pelo Rosetta).
  - O PySide6 fica no 6.11.3 nos três sistemas. A etiqueta da roda dele diz macOS 13, mas os módulos pedem
    o 15 (medido binário por binário); o 6.12.0 pede o 26.
  - `requirements-compativel.txt` (PySide6 6.4.3 e numpy 1.26, com Python 3.11) para o macOS 10.14 a 14.
    A suíte inteira passa com essa combinação, e o CI roda com ela num Mac Intel.
  - `ferramentas/minimo_macos.py` lê o macOS mínimo de cada binário do app; o build falha se algum passar do
    alvo. A roda do numpy é forçada para a do macOS mínimo (a padrão pede o macOS 14).
  - O zip do macOS e o tar.gz do Linux mantêm as permissões e os links (o artefato do GitHub perdia).
  - Teste com janelas de verdade no Mac do CI; os testes de Windows e macOS não leem mais a área de trabalho
    de quem roda.
- Linux (qualquer distro com glibc 2.28 ou mais nova, x64 e ARM64):
  - Sem programas extras: as janelas, a janela ativa e o tempo ocioso vêm direto do X11 (python-xlib), no
    lugar de xdotool, wmctrl e xprintidle, que a maioria das distros não instala (sem eles o pet não via
    nada). O `wmctrl` também somava a posição da janela duas vezes (medido: y=734 virava 1468).
  - Wayland (padrão no Ubuntu, Fedora, Debian, KDE): o pet abre pelo XWayland. No Wayland nativo a janela
    não escolhe a posição nem fica por cima, e ele não andaria. O tempo ocioso vem do GNOME (Mutter) quando o
    X não informa.
  - Executáveis: x64 (glibc 2.35+), ARM64 (2.39+) e um compatível feito no AlmaLinux 8 com PySide6 6.4.3
    (glibc 2.28+: Debian 10/11, Ubuntu 20.04, RHEL 8/9, Leap 15). Em pasta, não em arquivo único (que se
    extrai no /tmp, às vezes noexec). As bibliotecas do xcb que muitas distros não instalam (libxcb-cursor...)
    vão dentro; as que precisam ser as do sistema (fontconfig, libstdc++, glib, X11, GL) saem
    (`ferramentas/podar_linux.py`); a fontconfig antiga dava erro de configuração no Fedora novo.
  - `ferramentas/minimo_glibc.py` confere a glibc de cada binário; o job `distros` abre o app num X de
    verdade em Debian 11/12/13, Ubuntu 20.04/22.04/24.04, Mint 22, Kali, Fedora, Arch, openSUSE Leap e
    Tumbleweed, AlmaLinux 8 e Rocky 9.
  - Teste do leitor do X11 com uma janela de verdade (Xvfb e openbox no CI).
- Rajadas de Ki: na revolução, o Clawd em Super Saiyajin atira Ki no lugar das bolinhas de papel
  (`world/ki.py`). Cada rajada:
  - é uma esfera pequena e redonda: núcleo branco, borda amarelo-dourada, brilho e arcos elétricos azul-ciano
    que piscam;
  - nasce na pata do lado do cursor e carrega por 0,18 s, com faíscas entrando; acompanha a pata se ele se
    mexe;
  - sai acelerando até 1700 px/s, com uma cauda de energia que afina e apaga e solta faíscas;
  - explode num flash curto (núcleo, anel e estilhaços) no alvo, num post-it ou na borda da tela.

  A própria rede decide quando atirar. O canal sensorial PODER fica ligado enquanto ele está transformado e
  habitua devagar. O motor de decisão KI recebe PODER, brincadeira e raiva; calma, tristeza e cansaço seguram;
  a taxa dele vira a chance de atirar (`GANHO_KI`), e o alvo é sempre o cursor. Medido na rede: uns 13 tiros por minuto logo
  depois de transformar, caindo para 2 ou 3 por minuto em 10 min; cansado, menos de 1 por minuto. A rede
  passa a ter 486 neurônios, 31 canais e 16 motores, e o aprendizado salvo continua valendo.
  Às vezes sai uma rajada forte e teleguiada:
  - maior, carrega 0,55 s e tem coroa de labaredas e 4 arcos elétricos;
  - persegue o cursor em curva (até 5,5 rad/s) e atravessa os post-its;
  - explode ao alcançá-lo, numa bola de fogo branca com duas ondas de choque;
  - dá um coice 2,5 vezes maior;
  - a chance cresce com a vontade da rede, de 5% até 35%, e só sai uma por vez.
  Na revolução, o intervalo continua vindo do neurônio PAPEL. Às vezes vem um segundo tiro da outra pata, e cada tiro dá um
  coice no pet. A física é por tempo, sem depender da taxa de quadros. Fora do Super Saiyajin, continua o
  papel.
- Android 10 ou mais novo (arm64-v8a e x86_64): o pet mora dentro do app, num palco preto (o Android não deixa
  um app Qt flutuar sobre os outros nem ler as janelas deles, e no Android as janelas do Qt não ficam
  transparentes). `plataforma/android.py` devolve tudo neutro (sem ocioso, janelas nem atalho global); o menu
  abre com um toque longo no pet (vale para tela de toque em qualquer sistema); a memória fica na pasta privada
  do app; abre direto no pet. APK pelo `pyside6-android-deploy` (PySide6 6.12, Python 3.14 no aparelho, NDK
  r28c), com o numpy e o conteúdo dos pets (`ferramentas/gerar_android.py`), e aberto num emulador de verdade
  (`ferramentas/fumaca_android.sh`). O Android 9 fica de fora: a libshiboken6 das rodas usa TLS nativo do ELF e
  não carrega nele ("unknown reloc type 16", visto no emulador).
- Conjunto legado, com Python 3.8 e Qt 5.15 (PySide2): Windows 7 SP1, 8 e 8.1, Windows de 32 bits, macOS 10.13
  e Linux com glibc 2.17 (CentOS 7, Ubuntu 16.04 e 18.04). O código continua escrevendo PySide6: o pacote
  `qt5compat` faz a ponte (exec, position/globalPosition, QAction no QtGui, DPI automático) e `qt_legado.ativar()`
  o registra como PySide6 quando o PySide6 não está instalado. O código ficou compatível com o Python 3.8
  (`from __future__ import annotations`, sem pairwise, zip strict e removesuffix). A suíte inteira passa no
  PySide6 6.11.3, no 6.4.3 e no PySide2 5.15.
- Executáveis modernos (Windows, macOS 15+, Linux x64/ARM64) com Python 3.13: no 3.11 o PySide6 6.11.3 abortava
  ao fechar ("none_dealloc", visto no Linux ARM64 do CI). Os compatíveis seguem no 3.11 (o PySide6 6.4.3 pede)
  e não têm o problema.
- O programa aparece como **Claude Super Power** (janelas, bandeja, menus e textos). Por dentro nada muda:
  o pacote continua `pestinha/`, o log `memory/logs/pestinha.log` e a memória no mesmo lugar.
- Novo personagem: **Claude**, o mascote do Claude Code em blocos 3D (`pets/clawd.json`,
  `"corpo": "clawd3d"`), desenhado só com o QPainter. Gira para o lado do olhar, mantém todas as
  expressões e faz `> <` no carinho.
- Super Saiyajin 1 (só o Claude), pelo menu do botão direito ou em Configurações › Brincadeira; fica
  salvo. Juba alta no estilo dos animes de luta: mechas grossas que sobem como labaredas, abrem um pouco
  no meio e voltam a ponta para dentro (a juba fecha em chama em cima), em três camadas, com franja na
  testa e sombreamento de anime, girando junto com a cabeça; aura SSJ2 dourada e intensa, com labaredas
  altas, pontudas e irregulares por cima e pelos lados, borda luminosa, brilho amarelo-branco no centro e
  pulso rápido (3 por segundo); seis micro-raios em volta da aura, cada um com o seu relógio (um a cada
  0,5 s): zigue-zague de 3 a 5 dobras afiadas (45° a 70°), pontas afiladas, núcleo branco, contorno
  azul-ciano, brilho e faíscas, com clarão, oscilação e sumindo; olhos turquesa (mesma forma de cada
  emoção) com contorno e reflexo. A janela cresce
  (272x300) só enquanto ele está
  transformado. Juba e aura ficam guardadas prontas (por ângulo, e a aura a 12 quadros por segundo):
  custa menos de 1 ms por quadro.
- Tema do Claude Code em todas as janelas, menus e painéis: fundo escuro quente, texto creme, letra de
  terminal e o laranja do Claude; a tela de configurações abre com a caixa "✻ Welcome to ...".
- O ícone das janelas e da bandeja é o desenho do pet escolhido; o passo a passo se apresenta conforme o pet.
- Painel de protesto: os nomes dos estágios não se encavalam mais e a legenda de baixo quebra a linha.
- Os painéis (monitor neural e de protesto) não abrem mais sozinhos no modo teste, que só encurta os
  tempos; antes eles abriam e o item do menu não conseguia fechá-los. Cada painel tem um × no canto e
  a bandeja tem "Fechar painéis".

## Correções da auditoria (2026-11)

- Um `cartazes.txt` salvo em ANSI (Bloco de Notas antigo) derrubava o app na abertura; com BOM, a primeira
  seção era ignorada. Os textos agora aceitam UTF-8, UTF-8 com BOM e ANSI.
- Um `pets/<pet>.json` com erro de sintaxe era renomeado para `.corrompido` e o personagem sumia. Agora o
  arquivo fica onde está e o pet usa o padrão (com aviso no log).
- O estado salvo que não serve para a rede (outra semente, outra versão) era sobrescrito 30 s depois, sem
  cópia. Agora fica uma cópia `.descartado` (o mesmo vale para homeostase e protesto).
- Gravação com `fsync` e temporário único; um `.corrompido` antigo não é mais sobrescrito pelo novo.
- Linux: os comandos do sistema rodam numa thread própria (antes travavam a tela ~100 ms por segundo); as
  janelas vêm na ordem de empilhamento real do X11, sem as minimizadas e sem as de outra área de trabalho;
  tela cheia vale para qualquer monitor; o pet só recebe o clique em cima do corpo (antes, um quadrado
  invisível de 200x200 bloqueava o que estava embaixo); bytes inválidos na saída dos comandos não derrubam.
- Rede neural ~25% mais leve (só os neurônios que dispararam entram na conta; resultado idêntico).
- "Fechar" no menu do pet fecha o programa (antes só escondia). Esconder o notebook fica salvo e também
  aparece em Configurações.
- O primeiro uso só grava as permissões ao clicar em Começar; o atalho de pânico avisa quando, no Wayland,
  só funciona com janelas X11; `quit` fecha mesmo se algo falhar no caminho.
- Fontes com reserva no Linux e no macOS (Consolas, Segoe Print e Arial Black são do Windows).
- Gate de qualidade: ruff, mypy e bandit com zero achados, e testes com avisos tratados como erro.

## Suporte a macOS e Linux

- Toda a leitura do sistema (programa em primeiro plano, tempo ocioso, janelas, tela cheia, foco e o atalho
  de pânico) passa para `pestinha/plataforma/`, com um módulo por sistema. O resto do código não sabe
  qual sistema está rodando.
- O Windows continua com o mesmo comportamento: o código foi movido, não reescrito.
- macOS: Quartz e AppKit (pyobjc), tempo ocioso pelo `ioreg` se não houver pyobjc. Atalho via pynput.
- Linux (X11): xdotool, wmctrl e xprintidle; atalho via pynput. Em Wayland, o pet não enxerga janelas
  nem o tempo ocioso, e o atalho não funciona.
- A checagem de atividade reconhece os nomes de programa dos três sistemas (com ou sem `.exe`).

## Renomeação para Pestinha

- O programa e o pacote Python passam a se chamar `pestinha/` (antes `bryan/`); a classe principal é
  `PestinhaApp`; o executável, o log e a documentação usam Pestinha.
- Bryan continua sendo o nome do primeiro personagem: `pets/bryan.json`, `pets/bryan/`, a memória
  `memory/pets/bryan/` e os arquivos de conteúdo dele não mudaram.
- Os comentários e textos que falavam do pet em geral passam a dizer "o pet".

## 0.7.0 — primeira versão pública (em preparação)

### O que ele faz
- Pet de tela com corpo físico: gravidade, quique, giro, pouso nas barras de título, arraste e arremesso.
- Rede neural pulsada de 470 neurônios LIF, com 30 canais sensoriais, 10 populações de interneurônios
  e 15 motores (8 de expressão e 7 de decisão).
- Emoções vindas dos motores; carinho com olhinhos fechados de felicidade.
- Bolinha de tênis, notebook de trabalho (VS Code, Visual Studio, PyCharm, Claude, Codex) e pedido de
  trabalho que ele pode recusar.
- Travessuras com memes, fotos, post-its e bilhetes tristes, com frequência decidida pela rede.
- Protesto em estágios até a revolução contra o cursor, com cartazes e bolinhas de papel.
- Cantinho do castigo: placa arrastável, perdão por carinho, fuga por vontade acumulada, rancor, receio,
  medo condicionado da placa e cartazes de xingamento.
- Aprendizado: habituação, regra de três fatores, condicionamento Rescorla–Wagner, memória episódica.
- Pânico (`Ctrl + Alt + Shift + B`), pausa, modo teste, monitor neural e painel de protesto.

### Memória por personagem
- Cada personagem tem a sua memória em `memory/pets/<pet>/` (rede e os sete arquivos de memória); o que
  é do app (permissões, rotina, painéis, log) continua em `memory/`.
- Migração automática da versão antiga: copia, confere, guarda os originais em `memory/legado/<pet>/` e
  só então marca como migrado. Conflito ou falta de permissão não sobrescrevem nada: ele segue com os
  arquivos antigos e avisa na bandeja.

### Conteúdo por personagem
- Frases, cartazes e memes de cada personagem ficam em `pets/<pet>/`; imagens neutras (bolinhas, notebook)
  e suas fotos em `assets/comum/`. Um personagem nunca usa o conteúdo de outro: sem conteúdo próprio, usa
  frases neutras ou não faz aquela travessura.
- Os cartazes do cantinho do castigo saíram do código para as seções `[castigo]` e `[xingamento]` do
  `cartazes.txt` do pet.

### Escolha do personagem
- O programa passa a se chamar **Pestinha**; o Bryan é o primeiro personagem.
- O personagem é escolhido em Configurações (vale ao reabrir). Só `pets/<pet>.json` vira opção.
- Os textos usam o nome do personagem onde é ele que fala (apresentação, "Estou aqui", notebook, monitor
  neural, painel de protesto) e o nome do programa no resto (configurações, bandeja, pânico).
- O log passa a ser `memory/logs/pestinha.log`; o executável, `Pestinha.exe`.

### Jorge
- Segundo personagem: coach de finanças e IA, trambiqueiro. Mesma rede e mesmos estágios do Bryan, com
  outra semente, outro temperamento e conteúdo próprio (recadinhos, bilhetes tristes, cartazes de todos os
  estágios e do cantinho, e um panfleto de mentoria no lugar da bolinha de papel). Cinco memes para cada uma de felizes, contentes, curiosos e bravos, em `pets/jorge/memes/`.
- `ferramentas/medir_cartazes.py` confere, com as fontes de verdade, se cada cartaz cabe na placa.
- `ferramentas/gerar_panfleto.py` desenha o panfleto do Jorge.

### Cores e acessórios
- Cada pet pode ter as próprias cores (moldura, tela, olhos) e acessórios (óculos, gravata) no campo
  `aparencia` do `.json`. Os acessórios são uma camada por cima do rosto; olhos e expressões não mudam.
- O Jorge tem moldura e olhos dourados e gravata vermelha. O Bryan continua igual.

### Licença
- Código sob GPL-3.0-or-later (`LICENSE`).

### Qualidade
- Arquitetura em camadas verificada por teste; `app.py` dividido em composição e mixins de sessão e
  interação.
- Persistência validada: escrita atômica, recusa de `NaN`, carga tudo-ou-nada.
- Cinco rodadas de auditoria, com cada bug corrigido coberto por teste, registradas em `docs/auditorias/`.
- Suíte de testes, bateria de 100 cenários do cantinho e fuzzer com invariantes.
