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
