"""
CONTRATO - o que os mixins de controle usam do PestinhaApp, declarado para o verificador de tipos.

SessaoMixin e InteracaoMixin leem atributos que só existem depois do PestinhaApp.__init__. Em
execução esta classe é vazia (tudo está sob TYPE_CHECKING); para o mypy ela diz o tipo de cada um.
Importa só de camadas abaixo de `controle` (ver tests/test_arquitetura.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from ..body.behavior import Behavior
    from ..body.bolinha import Ball
    from ..body.pet import PetWindow
    from ..body.pet_state import PetState
    from ..core.conditioning import Conditioning
    from ..core.episodic import EpisodicMemory
    from ..core.homeostasis import Drives
    from ..core.nervous_system import LIFBrain
    from ..core.protesto import Protesto
    from ..mind.castigo_ctl import CastigoController
    from ..mind.festa import FestaController
    from ..mind.mesa import MesaController
    from ..mind.mischief_ctl import MischiefController
    from ..mind.protest_ctl import ProtestController
    from ..mind.revolucao import RevolucaoController
    from ..mind.sleep import SleepController
    from ..paths import Paths, PetPaths
    from ..sense.senses import ComputerSenses
    from ..sense.timeline import TimelineRecorder
    from ..settings_store import SettingsStore
    from ..ui.float_manager import FloatManager
    from ..ui.ui import SettingsDialog, Tray
    from ..world.mischief import MischiefEngine


class ContratoApp:
    """Atributos e métodos que o PestinhaApp fornece aos mixins (só declarações de tipo)."""

    if TYPE_CHECKING:
        perms: dict[str, Any]
        prof: dict[str, Any]
        store: SettingsStore
        paths: Paths
        pet_paths: PetPaths
        state_file: Path
        pet: PetWindow
        pet_state: PetState
        behavior: Behavior
        ball: Ball
        ball_stored: bool
        brain: LIFBrain
        castigo: CastigoController
        conditioning: Conditioning
        drives: Drives
        festa: FestaController
        floats: FloatManager
        fullscreen: bool
        memory: EpisodicMemory
        mesa: MesaController
        mischief: MischiefEngine
        mischief_ctl: MischiefController
        protest: Protesto
        protest_ctl: ProtestController
        revolucao: RevolucaoController
        sad: Protesto
        sad_ctl: ProtestController
        senses: ComputerSenses
        sleep: SleepController
        timeline: TimelineRecorder
        tray: Tray
        reacao_notebook: str
        settings: SettingsDialog | None
        paused: bool
        hidden: bool
        wiping: bool
        in_flight: bool
        last_poke: float
        poke_probe: tuple[float, float] | None
        last_poke_response: float | None
        _pausado_em: float | None
        _ultimo_think: float | None
        debugging: Callable[[], bool]

        @property
        def asleep(self) -> bool: ...
        def bounds(self) -> tuple[float, float, float, float]: ...
        def _congelado(self) -> bool: ...
        def open_settings(self) -> None: ...
        def quit(self) -> None: ...
        def toggle_hidden(self) -> None: ...
        def update_visibility(self) -> None: ...
