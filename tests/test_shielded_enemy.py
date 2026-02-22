import pygame

from src.entities.enemy import Enemy


def test_shielded_enemy_has_shield_and_blocks_damage():
    pygame.init()
    e = Enemy(0, 0, "shielded", health=100, speed=50)
    # shield should equal max health (max_health already includes global 20% bonus)
    assert hasattr(e, "shield_hp")
    assert e.shield_hp == e.max_health
    orig_health = e.health

    # deal 20 damage - should reduce shield only
    e.take_damage(20)
    assert e.shield_hp == e.max_health - 20
    assert e.health == orig_health

    # deal 40 damage - shield drops by another 40 but no health loss
    e.take_damage(40)
    assert e.shield_hp == e.max_health - 60
    assert e.health == orig_health

    # deplete remaining shield
    e.take_damage(e.max_health - 60)
    assert e.shield_hp == 0
    assert e.health == orig_health

    # now deal damage, health should decrease
    e.take_damage(10)
    assert e.health == orig_health - 10


def test_mage_has_shield_and_blocks_damage_like_shielded():
    pygame.init()
    m = Enemy(0, 0, "mage", health=80, speed=50)
    # mage should have shield equal to max health (includes 20% scaling)
    assert hasattr(m, "shield_hp")
    assert m.shield_hp == m.max_health
    orig_health = m.health

    m.take_damage(30)
    assert m.shield_hp == orig_health - 30
    assert m.health == orig_health

    # drain remaining shield (only the shield portion)
    m.take_damage(m.shield_hp)
    assert m.shield_hp == 0
    assert m.health == orig_health

    # further damage reduces health
    m.take_damage(5)
    assert m.health == orig_health - 5


def test_shielded_enemy_draws_asset_and_fallback(monkeypatch):
    pygame.init()
    called = {}

    def fake_get_image(name, size=None):
        called["name"] = name
        return pygame.Surface(size or (10, 10))

    import src.assets.manager as am

    monkeypatch.setattr(am, "get_image", fake_get_image)

    e = Enemy(0, 0, "shielded", health=100, speed=50)
    e.draw_enemy()
    assert called.get("name") == "enemy_shielded.png"
