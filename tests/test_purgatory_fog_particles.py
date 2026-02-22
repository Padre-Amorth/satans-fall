from pathlib import Path

import pygame
import pytest

from src.game import Game
from src.game_constants import FOG_ALPHA
from src.ui import PygameUIManager


@pytest.mark.parametrize("stage", ["purgatory", "purgatory_2", "purgatory_3"])
def test_purgatory_overlay_only_and_no_particles(stage):
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = stage
    g.generate_walls()

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    # should start with no descriptors and never gain any
    assert getattr(ui, "_purgatory_fog_particles", None) == []

    screen.fill((0, 0, 0))
    before = screen.get_at((0, 0))[:3]
    for _ in range(30):
        ui.draw_purgatory_fog()
        # still no particles at any point
        assert getattr(ui, "_purgatory_fog_particles", None) == []
    after = screen.get_at((0, 0))[:3]
    assert after != before, "overlay did not modify any pixel"
    # surface should remain valid
    assert isinstance(screen, pygame.Surface)


def test_purgatory_overlay_cached():
    """The overlay surface should be created only once and reused."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "purgatory"
    g.generate_walls()

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    # initially no overlay stored
    assert getattr(ui, "_purgatory_overlay", None) is None
    ui.draw_purgatory_fog()
    first = getattr(ui, "_purgatory_overlay", None)
    assert isinstance(first, pygame.Surface)
    # calling again should not recreate it (same object identity)
    ui.draw_purgatory_fog()
    assert ui._purgatory_overlay is first


def test_limbo_overlay_drawn_and_cached():
    """Limbo stages should also receive a cached full-screen fog overlay."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"
    g.generate_walls()

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    # no overlay initially
    assert getattr(ui, "_limbo_overlay", None) is None
    ui.draw_fog()
    first = getattr(ui, "_limbo_overlay", None)
    assert isinstance(first, pygame.Surface)
    # next call should reuse
    ui.draw_fog()
    assert ui._limbo_overlay is first
    # and overlay should have altered the pixel
    before = (0, 0, 0)
    assert screen.get_at((0, 0))[:3] != before


# the overlay test is covered by the above parameterized case and
# the UI delegation test; no separate overlay-only test needed any more.


def test_ui_draw_calls_purgatory_fog(monkeypatch):
    """When the UI draws a frame in purgatory it should produce the overlay.

    This verifies the new delegation in `UI.draw_fog`.
    """
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "purgatory"
    g.showing_stage_menu = False
    g.generate_walls()

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    # spy on draw_purgatory_fog
    called = {"count": 0}

    def spy(shake_x=0, shake_y=0):
        called["count"] += 1
        # still perform overlay so we can see pixel change
        return PygameUIManager.draw_purgatory_fog(ui, shake_x, shake_y)

    from src.ui import PygameUIManager

    monkeypatch.setattr(ui, "draw_purgatory_fog", spy)

    # call Game.draw which ultimately routes through ui.draw_fog
    g.screen = screen
    # set surface dimensions so UI can use width/height
    g.width = screen.get_width()
    g.height = screen.get_height()
    # perform single frame draw
    g.draw()
    assert called["count"] >= 1, "Game.draw() did not invoke draw_purgatory_fog"
    # at least one call should have occurred; overlay effect validated below
    assert screen.get_at((0, 0))[:3] != (0, 0, 0)


def test_purgatory_overlay_tints_enemies(tmp_path: Path) -> None:
    """Overlay should alter enemy pixels when drawing a full frame."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "purgatory"
    g.showing_stage_menu = False
    g.generate_walls()

    # place a dummy enemy at a known position
    enemy = {"x": 300, "y": 100, "radius": 10, "color": (255, 0, 0)}
    g.enemies = [enemy]

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    # draw once with fog enabled
    g.draw()
    tinted = screen.get_at((300, 100))[:3]

    # now run again with fog disabled via monkeypatch
    def noop_fog(shake_x=0, shake_y=0):
        return None

    ui.draw_purgatory_fog = noop_fog
    screen.fill((0, 0, 0))
    g.draw()
    nofog = screen.get_at((300, 100))[:3]

    assert tinted != nofog, "Enemy pixel should change when fog is applied"


def test_purgatory_fog_particles_never_appear(monkeypatch):
    """Even if draw_purgatory_fog is invoked in any stage, no particles are created."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"
    g.generate_walls()

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    for _ in range(30):
        ui.draw_purgatory_fog()
    assert getattr(ui, "_purgatory_fog_particles", None) in (
        None,
        [],
    ), "Fog particles should never be present, regardless of stage"


def test_overlay_respects_alpha_constant(monkeypatch):
    """The overlay surface should be created with the configured alpha."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "purgatory"
    g.generate_walls()

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    # intercept Surface to record alpha
    recorded = {"alpha": None, "filled": False}

    class FakeSurface(pygame.Surface):
        def __init__(self, size, *args, **kwargs):
            super().__init__(size, *args, **kwargs)

        def set_alpha(self, a):
            recorded["alpha"] = a
            return super().set_alpha(a)

        def fill(self, color):
            recorded["filled"] = True
            return super().fill(color)

    monkeypatch.setattr(ui.pygame, "Surface", FakeSurface)

    # perform draw; overlay creation should happen inside draw_purgatory_fog
    ui.draw_purgatory_fog()

    from src.game_constants import PURGATORY_OVERLAY_ALPHA

    assert recorded["alpha"] == PURGATORY_OVERLAY_ALPHA
    assert recorded["filled"], "overlay should be filled with color"


def test_clouds_never_spawn(monkeypatch):
    """After particle removal, the cloud list should always remain empty."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "purgatory"
    g.generate_walls()

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    for _ in range(50):
        ui.draw_purgatory_clouds()
        assert getattr(ui, "_purgatory_clouds", None) in (
            None,
            [],
        ), "No clouds should be created"


def test_fog_texture_matches_constants():
    """Generated fog texture respects the size constant."""
    pygame.init()
    from src.game_constants import FOG_COLOR, FOG_TEXTURE_SIZE

    ui = PygameUIManager(Game(debug=True))
    tex = ui._create_fog_texture(FOG_TEXTURE_SIZE, FOG_COLOR, FOG_ALPHA)
    assert tex is not None
    w, h = tex.get_size()
    assert (
        w == h == FOG_TEXTURE_SIZE
    ), f"Texture size {w}x{h} does not equal {FOG_TEXTURE_SIZE}"


def test_dynamic_fog_particles_initialised_and_update(monkeypatch):
    """Fog particles should be created and move when draw_purgatory_fog is called."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "purgatory"
    g.generate_walls()

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    from src.game_constants import FOG_MAX_SPEED, FOG_MIN_SPEED, FOG_PARTICLE_COUNT

    # ensure initialization created the expected number
    assert len(getattr(ui, "_fog_particles", [])) == FOG_PARTICLE_COUNT

    # every particle speed should lie within the new slower range
    assert all(
        FOG_MIN_SPEED <= p.speed <= FOG_MAX_SPEED for p in ui._fog_particles
    ), "Fog particle speeds must respect updated constants"

    # record initial x and y positions
    initial_positions = [(p.x, p.y) for p in ui._fog_particles]
    # call draw_purgatory_fog which updates and draws them
    ui.draw_purgatory_fog()
    # horizontal positions should change and vertical stay within top 30%
    assert any(p.x != ix for p, (ix, iy) in zip(ui._fog_particles, initial_positions))
    # ensure bottom of each particle stays within top 40%
    assert all(p.y + p.width <= g.height * 0.4 for p in ui._fog_particles)


def test_fog_particle_stage_colors():
    """Particles drawn in different purgatory variants use different tints."""
    pygame.init()
    g = Game(debug=True)
    g.generate_walls()
    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    # create single simple fully‑opaque particle so tint shows clearly
    img = pygame.Surface((10, 10), pygame.SRCALPHA)
    img.fill((255, 255, 255, 255))
    p = PygameUIManager.FogParticle(ui, img)
    p.x, p.y = 50, 50

    def color_for_stage(stage):
        g.selected_stage = stage
        screen.fill((0, 0, 0))
        p.draw(screen)
        return tuple(screen.get_at((50, 50))[:3])

    c1 = color_for_stage("purgatory")
    c2 = color_for_stage("purgatory_2")
    c3 = color_for_stage("purgatory_3")
    assert c1 != c2 or c2 != c3, "Stage colors should differ"

    # drawing should not crash and should modify screen at some point
    before = screen.get_at((0, 0))[:3]
    ui.draw_purgatory_fog()
    after = screen.get_at((0, 0))[:3]
    assert after != before, "screen should change due to fog blits"


def test_clouds_absent_in_non_purgatory():
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"
    g.generate_walls()

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    for _ in range(100):
        ui.draw_purgatory_clouds()
    assert getattr(ui, "_purgatory_clouds", None) in (
        None,
        [],
    ), "Clouds should not spawn outside purgatory"


def test_game_draw_invokes_clouds(monkeypatch):
    """Even though clouds are disabled, Game.draw should still call the stub method."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "purgatory"
    g.showing_stage_menu = False
    g.generate_walls()

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    called = {"count": 0}

    def spy(shake_x=0, shake_y=0):
        called["count"] += 1
        return None

    monkeypatch.setattr(ui, "draw_purgatory_clouds", spy)

    g.screen = screen
    g.width = screen.get_width()
    g.height = screen.get_height()
    g.draw()
    assert called["count"] >= 1, "Game.draw() did not invoke draw_purgatory_clouds"
