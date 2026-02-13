from src.projectile import SoulDrainProjectile
from src.entities.enemy import Enemy


class DummyPlayer:
    def __init__(self):
        self.x = 0
        self.y = 0


def test_soul_drain_targets_boss():
    sd = SoulDrainProjectile(300, 300, 0, 0, damage=5, heal_amount=2, level=1)
    boss = Enemy(300, 350, enemy_type="boss_big", health=200)

    # Ensure boss is within homing range
    assert hasattr(sd, 'homing_range')
    assert sd.homing_range >= 50

    sd.update([boss], DummyPlayer())

    # After update, target should be set to boss when within range
    assert sd.target is boss


def test_soul_drain_prefers_boss_over_closer_enemy():
    sd = SoulDrainProjectile(300, 300, 0, 0, damage=5, heal_amount=2, level=1)
    # Place a weak enemy closer than the boss but both within homing range
    weak = Enemy(305, 305, enemy_type="normal", health=20)
    boss = Enemy(320, 320, enemy_type="boss_big", health=200)

    # Sanity: weak is closer than boss
    dist_weak = ((weak.x - sd.x) ** 2 + (weak.y - sd.y) ** 2) ** 0.5
    dist_boss = ((boss.x - sd.x) ** 2 + (boss.y - sd.y) ** 2) ** 0.5
    assert dist_weak < dist_boss

    # Both inside homing range
    assert dist_boss < sd.homing_range

    sd.update([weak, boss], DummyPlayer())

    # Soul Drain should prioritize the boss despite being further away
    assert sd.target is boss
