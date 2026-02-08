from src.enemy import Enemy


def test_boss_final_is_100x100():
    boss = Enemy(100, 100, "boss_final", health=1000, speed=10)
    expected = 100
    assert boss.width == expected, f"Expected width {expected}, got {boss.width}"
    assert boss.height == expected, f"Expected height {expected}, got {boss.height}"
    # Radius should be based on the new size
    assert boss.radius == (boss.width + boss.height) // 4
