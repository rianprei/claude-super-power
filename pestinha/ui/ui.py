"""
UI - tela inicial de permissões, ícone na bandeja e atalho de pânico.

O visual é o do Claude Code: fundo escuro quente, texto creme, letra de terminal e o laranja do Claude
(cores em body/desenho_rosto.py). A tela abre com a caixa de boas-vindas com borda laranja e o ✻.
"""

from __future__ import annotations

from string import Template

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .. import config, plataforma
from ..body import desenho_rosto as tema
from ..body.clawd3d import draw_clawd
from ..body.pet import draw_face
from ..core.emotion import EYE_SHAPES
from ..sense import timeline

_CORES = {nome: getattr(tema, nome) for nome in ("FUNDO", "SUPERFICIE", "SUPERFICIE_ALTA", "BORDA", "TEXTO",
                                                "TEXTO_FORTE", "APAGADO", "DESLIGADO", "LARANJA", "LARANJA_CLARO")}
_CORES["MONO"] = ", ".join(f if f == "monospace" else f"'{f}'" for f in tema.MONO)

STYLE = Template("""
QWidget { font-family: $MONO; }
QDialog { background: $FUNDO; }
QScrollArea { background: $FUNDO; border: none; }
QWidget#conteudo, QWidget#qt_scrollarea_viewport { background: $FUNDO; }
QLabel { color: $TEXTO; font-size: 12px; }
QFrame#banner { border: 1px solid $LARANJA; border-radius: 8px; background: $FUNDO; }
QFrame#banner QLabel { background: transparent; }
QLabel#title { color: $TEXTO_FORTE; font-size: 15px; }
QLabel#banner_sub { color: $APAGADO; font-size: 12px; }
QLabel#hint { color: $APAGADO; font-size: 11px; }
QGroupBox { color: $LARANJA; font-size: 12px; font-weight: bold; border: 1px solid $BORDA;
            border-radius: 8px; margin-top: 14px; padding: 10px 8px 6px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QCheckBox { color: $TEXTO; font-size: 12px; spacing: 8px; }
QCheckBox:disabled { color: $DESLIGADO; }
QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid $DESLIGADO; border-radius: 3px;
                       background: $SUPERFICIE; }
QCheckBox::indicator:hover { border-color: $LARANJA; }
QCheckBox::indicator:checked { background: $LARANJA; border-color: $LARANJA_CLARO; }
QCheckBox::indicator:disabled { border-color: $BORDA; background: $FUNDO; }
QCheckBox::indicator:checked:disabled { background: $DESLIGADO; border-color: $DESLIGADO; }
QComboBox { background: $SUPERFICIE; color: $TEXTO; border: 1px solid $BORDA; border-radius: 6px;
            padding: 4px 8px; }
QComboBox:hover, QComboBox:focus { border-color: $LARANJA; }
QComboBox QAbstractItemView { background: $SUPERFICIE_ALTA; color: $TEXTO; border: 1px solid $BORDA;
                              selection-background-color: $LARANJA; selection-color: $FUNDO; }
QPushButton { background: $SUPERFICIE; color: $TEXTO; border: 1px solid $BORDA;
              border-radius: 6px; padding: 7px 18px; font-size: 12px; }
QPushButton:hover { border-color: $LARANJA; color: $TEXTO_FORTE; }
QPushButton:disabled { color: $DESLIGADO; border-color: $BORDA; }
QPushButton#start { background: $LARANJA; color: $FUNDO; border-color: $LARANJA; font-weight: bold; }
QPushButton#start:hover { background: $LARANJA_CLARO; border-color: $LARANJA_CLARO; }
QScrollBar:vertical { background: $FUNDO; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $BORDA; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $LARANJA; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QToolTip { background: $SUPERFICIE_ALTA; color: $TEXTO; border: 1px solid $LARANJA; padding: 4px; }
QMessageBox { background: $FUNDO; }
""").substitute(_CORES)

# menus (bandeja e botão direito no pet) no mesmo tema
MENU_STYLE = Template("""
QMenu { background: $SUPERFICIE; color: $TEXTO; border: 1px solid $BORDA; padding: 5px;
        font-family: $MONO; font-size: 12px; }
QMenu::item { padding: 6px 24px 6px 14px; border-radius: 5px; }
QMenu::item:selected { background: $LARANJA; color: $FUNDO; }
QMenu::item:disabled { color: $DESLIGADO; }
QMenu::separator { height: 1px; background: $BORDA; margin: 5px 8px; }
""").substitute(_CORES)


def face_icon(emotion="observando", corpo="tela"):
    """Ícone da bandeja e das janelas: o pet (a telinha ou o Clawd 3D) desenhado numa imagem pequena."""
    pix = QPixmap(128, 128)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if corpo == "clawd3d":
        p.translate(64, 62)
        p.scale(1.15, 1.15)
        draw_clawd(p, EYE_SHAPES[emotion])
    else:
        p.translate(64, 64)
        p.scale(0.95, 0.95)
        draw_face(p, EYE_SHAPES[emotion])
    p.end()
    return QIcon(pix)


class SettingsDialog(QDialog):
    """
    Tela inicial (e de configurações, pela bandeja). Cada mudança é gravada
    na hora e avisada por `changed`, então vale na sessão em andamento.
    """

    changed = Signal(dict)
    wipe_all = Signal()
    history_wiped = Signal()

    def __init__(self, perms, paths, first_run=True):
        """Tela de permissões e configurações. Trabalha numa cópia das permissões: cada mudança é avisada ao app na hora."""
        super().__init__()
        self.perms = dict(perms)           # cópia: só o app grava, pela transição certa
        self.paths = paths
        self.setWindowTitle(config.APP_NOME)
        pet = config.load_pet(paths, config.escolher_pet(paths, perms["pet"]))
        self.setWindowIcon(face_icon(corpo=pet["corpo"]))
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(460)
        # cabe na tela: o conteúdo rola dentro da janela, e o botão de começar fica sempre visível
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(500, min(760, int(screen.height() * 0.85)))
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)    # o conteúdo quebra a linha; só rola na vertical
        content = QWidget()
        content.setObjectName("conteudo")
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        self._outer = outer
        self.boxes = {}

        root = QVBoxLayout(content)
        root.setSpacing(8)
        root.addWidget(self._banner(pet["nome"], pet["id"]))
        if first_run:
            welcome = QLabel(
                f"O {config.APP_NOME} vê só o nome dos programas, o tempo sem usar o teclado e "
                "as janelas para pousar. Nunca lê o conteúdo de nada. Detalhes em PRIVACIDADE.md.\n"
                "Escolha abaixo o que ele pode fazer e clique em Começar. Tudo pode ser mudado depois.")
            welcome.setObjectName("hint")
            welcome.setWordWrap(True)
            root.addWidget(welcome)
        hint = QLabel("Escolha o que o pet pode fazer nesta sessão. Fica salvo para a próxima.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        top = QGroupBox(config.APP_NOME)
        top_layout = QVBoxLayout(top)
        self.active_box = QCheckBox(f"{config.APP_NOME} ligado")
        self.active_box.setChecked(perms["ativo"])
        self.active_box.toggled.connect(lambda on: self._set("ativo", on))
        top_layout.addWidget(self.active_box)
        if not perms["ativo"]:
            warn = QLabel(f"O pânico desligou o {config.APP_NOME} na última vez. Marque acima para religar.")
            warn.setObjectName("hint")
            warn.setWordWrap(True)
            top_layout.addWidget(warn)

        pet_row = QHBoxLayout()
        pet_row.addWidget(QLabel("Personagem:"))
        self.pet_combo = QComboBox()
        for pet_id in config.list_pets(self.paths):            # só pets/<id>.json; memória antiga não conta
            self.pet_combo.addItem(config.load_pet(self.paths, pet_id)["nome"], pet_id)
        atual = config.escolher_pet(self.paths, perms["pet"])
        self.pet_combo.setCurrentIndex(max(0, self.pet_combo.findData(atual)))
        self.pet_combo.currentIndexChanged.connect(self._trocar_pet)
        pet_row.addWidget(self.pet_combo, 1)
        top_layout.addLayout(pet_row)
        self.pet_aviso = QLabel("Vale na próxima vez que abrir. Cada personagem tem a própria memória.")
        self.pet_aviso.setObjectName("hint")
        self.pet_aviso.setWordWrap(True)
        self.pet_aviso.setVisible(not first_run)
        top_layout.addWidget(self.pet_aviso)
        root.addWidget(top)

        for group_title, items in config.PERMISSION_GROUPS:
            group = QGroupBox(group_title)
            layout = QVBoxLayout(group)
            for key, label, description in items:
                box = QCheckBox(label)
                box.setChecked(bool(perms[key]))
                box.setToolTip(description)
                box.toggled.connect(lambda on, k=key: self._set(k, on))
                self.boxes[key] = box
                layout.addWidget(box)
                desc = QLabel(description)
                desc.setObjectName("hint")
                desc.setWordWrap(True)
                desc.setContentsMargins(26, 0, 0, 4)
                layout.addWidget(desc)
            if group_title == "Travessuras":
                self.resumo = self._asset_summary()
                layout.addWidget(self.resumo)
            if group_title == "Rotina":
                row = QHBoxLayout()
                self.history_label = QLabel()
                self.history_label.setObjectName("hint")
                row.addWidget(self.history_label, 1)
                wipe = QPushButton("Apagar histórico")
                wipe.clicked.connect(self._wipe_history)
                row.addWidget(wipe)
                layout.addLayout(row)
                everything = QPushButton(f"Apagar todos os dados do {config.APP_NOME}")
                everything.clicked.connect(self._wipe_everything)
                layout.addWidget(everything)
                self._update_history_label()
            root.addWidget(group)

        panic = QLabel(f"Pânico (desliga tudo e fica desligado): {config.PANIC_HOTKEY_TEXT}")
        panic.setObjectName("hint")
        root.addWidget(panic)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        if first_run:
            leave = QPushButton("Sair")
            leave.clicked.connect(self.reject)
            buttons.addWidget(leave)
            go = QPushButton("Começar")
            go.setObjectName("start")
            go.clicked.connect(self.accept)
        else:
            go = QPushButton("Fechar")
            go.setObjectName("start")
            go.clicked.connect(self.accept)
        buttons.addWidget(go)
        self._outer.addLayout(buttons)

        self._sync_enabled()

    def _banner(self, nome, pet_id):
        """Caixa de boas-vindas no jeito do Claude Code: borda laranja, ✻ e, embaixo, quem e onde (como o cwd)."""
        banner = QFrame()
        banner.setObjectName("banner")
        layout = QVBoxLayout(banner)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        title = QLabel(f"<span style='color:{tema.LARANJA}'>✻</span> Welcome to <b>{config.APP_NOME}</b>!")
        title.setObjectName("title")
        title.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(title)
        self.banner_sub = QLabel()
        self.banner_sub.setObjectName("banner_sub")
        self.banner_sub.setWordWrap(True)
        layout.addWidget(self.banner_sub)
        self._atualizar_banner(nome, pet_id)
        return banner

    def _atualizar_banner(self, nome, pet_id):
        """As linhas de baixo da caixa de boas-vindas: o personagem escolhido e onde fica a memória dele."""
        self.banner_sub.setText(f"  personagem: {nome}\n  memória:    memory/pets/{pet_id}/")

    def _asset_summary(self):
        """Linha de resumo do conteúdo do pet escolhido (memes, fotos, recadinhos)."""
        label = QLabel()
        label.setWordWrap(True)
        label.setObjectName("hint")
        self.resumo = label
        self._atualizar_resumo()
        return label

    def _atualizar_resumo(self):
        """Recalcula o resumo do conteúdo quando o personagem muda."""
        if not hasattr(self, "resumo"):
            return
        pet = config.escolher_pet(self.paths, self.perms["pet"])
        conteudo = self.paths.conteudo(pet)
        memes = sum(len(config.list_images(conteudo.memes / e)) for e in config.EMOTIONS)
        trabalho = len(config.list_images(conteudo.memes_trabalho))
        photos = len(config.list_images(conteudo.fotos))
        notes = config.Notes(conteudo.notes)
        notes._reload()
        tristes = config.Notes(conteudo.notes_sad)
        tristes._reload()
        nome = config.load_pet(self.paths, pet)["nome"]
        self.resumo.setText(f"Conteúdo de {nome}: {memes} memes de emoção, {trabalho} de trabalho, {photos} fotos, "
                            f"{len(notes.lines)} recadinhos e {len(tristes.lines)} bilhetes tristes.")

    def _update_history_label(self):
        """Mostra quantos minutos de rotina estão gravados."""
        minutes = timeline.count_rows(self.paths.timeline)
        self.history_label.setText(f"Histórico: {minutes} minutos ({minutes / 60:.1f} h) gravados.")

    def _wipe_history(self):
        """Apaga a rotina (timeline.csv) depois de pedir confirmação."""
        answer = QMessageBox.question(
            self, "Apagar histórico",
            "Apagar todo o histórico da sua rotina (memory/timeline.csv)? Não dá para desfazer.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            try:
                self.paths.timeline.unlink(missing_ok=True)
            except OSError as error:
                QMessageBox.warning(self, "Apagar histórico", f"Não deu para apagar: {error}")
            else:
                self.history_wiped.emit()         # o app descarta também o minuto que ainda está em RAM
            self._update_history_label()

    def _wipe_everything(self):
        """Apaga todos os dados do app depois de pedir confirmação; o app fecha em seguida."""
        answer = QMessageBox.question(
            self, "Apagar todos os dados",
            f"Apagar tudo que o {config.APP_NOME} guardou (pasta memory/: a memória de todos os "
            f"personagens, histórico, painéis, permissões)? O {config.APP_NOME} vai fechar. Não dá para desfazer.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.wipe_all.emit()

    def _trocar_pet(self, _indice):
        """Só grava a escolha: o pet que está na tela continua até reabrir (a memória dele é outra)."""
        self._set("pet", self.pet_combo.currentData())
        self._atualizar_banner(self.pet_combo.currentText(), self.pet_combo.currentData())
        self._atualizar_resumo()

    def _set(self, key, value):
        """Grava uma permissão e avisa o app só dessa mudança."""
        self.perms[key] = value
        self._sync_enabled()
        self.changed.emit({key: value})          # só o campo mudado: o resto é do app

    def _sync_enabled(self):
        """Liga ou desliga os itens que dependem de 'Travessuras' (memes, fotos, bilhetes)."""
        master = self.perms["travessuras"]
        for key in ("memes", "fotos", "bilhetes"):
            self.boxes[key].setEnabled(master)
        self.boxes["mostrar_emocao"].setEnabled(self.perms["modo_teste"])

    def set_active(self, on):
        """Atualiza a caixa 'ligado' sem disparar a gravação (usado pelo pânico)."""
        self.active_box.blockSignals(True)
        self.active_box.setChecked(on)
        self.active_box.blockSignals(False)


class Tray(QObject):
    """Ícone da bandeja do sistema, com o menu de controle do pet."""
    open_settings = Signal()
    open_monitor = Signal()
    open_panel = Signal()
    fechar_paineis = Signal()
    toggle_pause = Signal()
    toggle_hidden = Signal()
    clear_things = Signal()
    panic = Signal()
    quit = Signal()

    def __init__(self, nome, corpo="tela"):
        """Cria o ícone (o desenho do pet) e o menu; cada item emite um sinal que o app ouve."""
        super().__init__()
        self.titulo = f"{config.APP_NOME} · {nome}"
        self.icon = QSystemTrayIcon(face_icon(corpo=corpo))
        self.icon.setToolTip(self.titulo)
        menu = QMenu()
        menu.setStyleSheet(MENU_STYLE)
        self.actions = {}
        for key, text, signal in [
            ("settings", "Configurações...", self.open_settings),
            ("monitor", "Monitor neural", self.open_monitor),
            ("panel", "Painel de protesto", self.open_panel),
            ("paineis", "Fechar painéis", self.fechar_paineis),
            ("pause", "Pausar", self.toggle_pause),
            ("hide", "Esconder", self.toggle_hidden),
            ("clear", "Limpar travessuras", self.clear_things),
            ("panic", f"Pânico ({config.PANIC_HOTKEY_TEXT})", self.panic),
            ("quit", "Sair", self.quit),
        ]:
            action = QAction(text, menu)
            action.triggered.connect(signal.emit)
            menu.addAction(action)
            self.actions[key] = action
            if key in ("hide", "panic"):
                menu.addSeparator()
        self.menu = menu
        self.icon.setContextMenu(menu)
        self.icon.activated.connect(
            lambda reason: self.open_settings.emit() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )
        self.icon.show()

    def set_state(self, paused, hidden, test_mode):
        """Atualiza os textos do menu e a dica do ícone conforme o estado (pausado, escondido, modo de teste)."""
        self.actions["pause"].setText("Continuar" if paused else "Pausar")
        self.actions["hide"].setText("Mostrar" if hidden else "Esconder")
        self.icon.setToolTip(self.titulo + ("  [MODO TESTE]" if test_mode else ""))
        plataforma.estado_da_bandeja(paused, hidden)     # Android: a notificação faz o papel da bandeja


# ============================================================
# ATALHO GLOBAL DE PÂNICO (Ctrl + Alt + Shift + B)
# ============================================================


class PanicHotkey(QObject):
    """Registra o atalho pela plataforma (Windows, macOS ou Linux); avisa o Qt por sinal."""

    pressed = Signal()

    def __init__(self):
        """Registra o atalho de pânico pela plataforma; `ok` diz se o sistema aceitou o atalho."""
        super().__init__()
        self.ok = plataforma.iniciar_atalho(self.pressed.emit)
