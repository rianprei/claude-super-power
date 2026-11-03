"""Partes que os três sistemas compartilham: rodar comandos do sistema e o atalho global via pynput."""

# subprocess: só comandos fixos do sistema, em lista de argumentos e sem shell
import subprocess  # nosec B404

from ..log import log


def rodar(comando, tempo=1.0):
    """Saída do comando (texto) ou None se ele não existe, falhou ou demorou demais.

    `comando` é sempre uma lista fixa montada no código (nunca texto do usuário) e roda sem shell.
    Bytes inválidos na saída (um título de janela em outra codificação) viram U+FFFD.
    """
    try:
        # lista de argumentos fixa montada no código, sem shell
        resultado = subprocess.run(  # noqa: S603  # nosec B603
            comando, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=tempo, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return resultado.stdout if resultado.returncode == 0 else None


def atalho_pynput(callback):
    """Ctrl + Alt + Shift + B em qualquer lugar do sistema. Precisa de pynput instalado."""
    try:
        from pynput import keyboard
    except Exception:  # noqa: BLE001 - sem pynput, ou o backend dele (Xlib) falha ao importar sem servidor
        log("[pânico] pynput indisponível: o atalho global fica desligado (o menu da bandeja funciona)")
        return False
    try:
        listener = keyboard.GlobalHotKeys({"<ctrl>+<alt>+<shift>+b": callback})
        listener.daemon = True
        listener.start()
    except Exception as error:  # noqa: BLE001 - backends do pynput (Xlib, uinput) levantam tipos próprios
        log(f"[pânico] não deu para registrar o atalho: {error}")
        return False
    return True
