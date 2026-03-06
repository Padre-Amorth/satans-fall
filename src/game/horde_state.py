"""HordeState dataclass for managing Limbo and Purgatory horde event state."""

from dataclasses import dataclass, field


@dataclass
class HordeState:
    """Encapsulates all state variables for a single horde event (Limbo or Purgatory)."""

    # Timing
    started: bool = False
    timer: int = 0  # Countdown until horde spawns
    elapsed: int = 0  # Time elapsed during horde
    active: bool = False  # Horde is currently running
    completed: bool = False  # Horde has finished

    # Victory
    victory_timer: int = 0  # Countdown to victory screen (after boss dies)
    ready_for_victory: bool = False  # Boss died, ready to start countdown

    # Enemy tracking
    initial: int = 0  # Total enemies to spawn
    killed: int = 0  # Enemies killed so far
    remaining: int = 0  # Enemies still alive

    # Purgatory-specific
    phase_index: int = 0  # Current phase (0-9 for 10 phases)
    explosion_ready: bool = False  # Explosion wave is ready to trigger
    wave_timer: float = 0.0  # Timer for malevolent wave expansion


class LimboHordeState(HordeState):
    """Limbo horde specific state."""

    pass


class PurgatoryHordeState(HordeState):
    """Purgatory horde specific state (with explosion tracking)."""

    pass
