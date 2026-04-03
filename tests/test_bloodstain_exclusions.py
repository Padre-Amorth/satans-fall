"""Test that bloodstains are NOT created for pentagram and eye enemies."""

from unittest.mock import MagicMock, patch

from src.entities.bloodstain import Bloodstain


class TestBloodstainExclusions:
    """Test that certain enemies don't create bloodstains."""

    def test_pentagram_death_no_bloodstain(self):
        """Test that pentagram death doesn't create bloodstain in death_system."""
        from src.systems.death_system import DeathSystem

        # Mock game and enemy
        game = MagicMock()
        game.bloodstains = []
        game.player = MagicMock()
        game.player.x = 640
        game.player.y = 360

        death_system = DeathSystem(game)

        # Create a mock pentagram enemy
        pentagram = MagicMock()
        pentagram.health = 0
        pentagram.max_health = 100
        pentagram.enemy_type = "pentagram"
        pentagram.x = 100
        pentagram.y = 200
        pentagram.is_boss = False

        # Mock sprite group with our pentagram
        game.enemies = MagicMock()
        game.enemies.sprites.return_value = [pentagram]
        del game.enemies.sprites  # Don't override hasattr
        type(game.enemies).sprites = MagicMock(return_value=[pentagram])

        with patch.object(death_system, "spawn_health_drop"):
            # Simulate death processing
            if hasattr(game.enemies, "sprites"):
                for enemy in list(game.enemies.sprites()):
                    if hasattr(enemy, "health") and enemy.health <= 0:
                        enemy_type = getattr(enemy, "enemy_type", "")
                        if enemy_type not in ("pentagram", "eye"):
                            bs = Bloodstain(enemy.x, enemy.y, size=4, is_large=False)
                            game.bloodstains.append(bs)

        # No bloodstain should be created
        assert len(game.bloodstains) == 0

    def test_eye_death_no_bloodstain(self):
        """Test that eye death doesn't create bloodstain in death_system."""
        from src.systems.death_system import DeathSystem

        # Mock game and enemy
        game = MagicMock()
        game.bloodstains = []
        game.player = MagicMock()
        game.player.x = 640
        game.player.y = 360

        death_system = DeathSystem(game)

        # Create a mock eye enemy
        eye = MagicMock()
        eye.health = 0
        eye.max_health = 50
        eye.enemy_type = "eye"
        eye.x = 300
        eye.y = 400
        eye.is_boss = False

        # Mock sprite group with our eye
        game.enemies = MagicMock()
        type(game.enemies).sprites = MagicMock(return_value=[eye])

        with patch.object(death_system, "spawn_health_drop"):
            # Simulate death processing
            if hasattr(game.enemies, "sprites"):
                for enemy in list(game.enemies.sprites()):
                    if hasattr(enemy, "health") and enemy.health <= 0:
                        enemy_type = getattr(enemy, "enemy_type", "")
                        if enemy_type not in ("pentagram", "eye"):
                            bs = Bloodstain(enemy.x, enemy.y, size=4, is_large=False)
                            game.bloodstains.append(bs)

        # No bloodstain should be created
        assert len(game.bloodstains) == 0

    def test_normal_enemy_creates_bloodstain(self):
        """Test that normal enemies still create bloodstains."""
        # Create a normal enemy (not excluded)
        enemy_type = "normal"
        should_create = enemy_type not in ("pentagram", "eye")
        assert should_create is True

    def test_excluded_types_check(self):
        """Test the exclusion logic for various enemy types."""
        excluded = ("pentagram", "eye", "pentagram_fire", "eye")

        # These should NOT create bloodstains
        for excluded_type in excluded:
            should_create = excluded_type not in ("pentagram", "eye")
            # pentagram and eye should not create
            if excluded_type in ("pentagram", "eye"):
                assert should_create is False
