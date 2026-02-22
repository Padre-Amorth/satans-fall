import os
import tempfile
from pathlib import Path

from src.game import Game


def test_permanent_upgrade_persistence():
    # Use a temp file to avoid polluting real saves
    with tempfile.TemporaryDirectory() as tmpdir:
        stats_path = Path(tmpdir) / "permanent_stats.json"
        # Create game and apply upgrade
        game = Game(permanent_stats_file=stats_path)
        game.permanent_stats["power"] = 5
        game.save_permanent_stats()
        # Simulate closing and reopening game
        game2 = Game(permanent_stats_file=stats_path)
        assert (
            game2.permanent_stats["power"] == 5
        ), "Permanent upgrade did not persist after reload"

        # Change upgrade and save again
        game2.permanent_stats["power"] = 7
        game2.save_permanent_stats()
        game3 = Game(permanent_stats_file=stats_path)
        assert (
            game3.permanent_stats["power"] == 7
        ), "Permanent upgrade did not persist after second reload"

        # Clean up
        if stats_path.exists():
            os.remove(stats_path)
