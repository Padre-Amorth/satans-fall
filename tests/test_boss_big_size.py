from src.entities.enemy import Enemy


def test_boss_big_is_large_enough():
    boss = Enemy(100, 100, enemy_type="boss_big", health=200)

    # Expect boss_big to be at least 3x a typical small enemy (~40px => 120px)
    assert boss.width >= 120
    assert boss.height >= 120
    # Radius should reflect increased size
    assert boss.radius >= (boss.width + boss.height) // 4 - 1
