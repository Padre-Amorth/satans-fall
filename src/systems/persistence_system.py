"""Persistence system for permanent stats and global progress."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game import Game

logger = logging.getLogger(__name__)


class PersistenceSystem:
    """Handles saving and loading persistent game data (permanent stats, global progress).

    Operates on game state via a reference to the Game instance.
    """

    def __init__(self, game: "Game") -> None:
        self.game = game

    def _ensure_permanent_stat_keys(self) -> None:
        """Ensure full set of permanent stat keys (backwards compatibility)."""
        keys = [
            "fire_1",
            "fire_2",
            "fire_3",
            "fire_4",
            "fire_5",
            "fire_6",
            "fire_7",
            "storm_1",
            "storm_2",
            "storm_3",
            "storm_4",
            "storm_5",
            "storm_6",
            "storm_7",
            "ice_1",
            "ice_2",
            "ice_3",
            "ice_4",
            "ice_5",
            "ice_6",
            "ice_7",
            # Blasphemies grid (include bottom-row leveled stats 6..9 and slot 10)
            "blasphemy_1",
            "blasphemy_2",
            "blasphemy_3",
            "blasphemy_4",
            "blasphemy_5",
            "blasphemy_6",
            "blasphemy_7",
            "blasphemy_8",
            "blasphemy_9",
            "blasphemy_10",
        ]
        for k in keys:
            self.game.permanent_stats.setdefault(k, 0)

    def record_enemy_kill(self) -> None:
        """Record a single enemy kill for the current run.

        Also award a small amount of meta XP so external progress reflects
        action even if the run is not completed.  This keeps the bar from
        remaining empty during play.
        """
        try:
            self.game.enemies_killed_this_run = (
                int(getattr(self.game, "enemies_killed_this_run", 0)) + 1
            )
        except Exception:
            try:
                self.game.enemies_killed_this_run = (
                    getattr(self.game, "enemies_killed_this_run", 0) + 1
                )
            except Exception:
                pass
        # award meta XP for the kill.  Use a small multiple so progress is
        # visible without needing an unreasonable number of kills.  Tests are
        # updated accordingly.
        try:
            self.game.award_meta_xp(5)
        except Exception:
            pass

    def load_permanent_stats(self) -> None:
        """Load persistent data from disk if file exists. Backwards-compatible.

        Supported formats:
        - Older flat dict: {"power": 1, "vigor": 0, ...} -> treated as permanent_stats
        - New wrapper: {"permanent_stats": {...}, "global_progress": {...}}"""
        try:
            if hasattr(self.game, "permanent_stats_file"):
                logger.debug(
                    "Checking persistent file: %s", self.game.permanent_stats_file
                )
            if (
                hasattr(self.game, "permanent_stats_file")
                and self.game.permanent_stats_file.exists()
            ):
                logger.debug(
                    "Loading persistent data from %s", self.game.permanent_stats_file
                )
                with open(self.game.permanent_stats_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                # Detect obsolete Blasphemy slots in the raw file so we can migrate (and persist) if present
                _loaded_had_obsolete_blasphemies = False
                if isinstance(data, dict):
                    # wrapper format: check nested permanent_stats
                    if isinstance(data.get("permanent_stats"), dict):
                        # No obsolete blasphemy slots expected — consider passed file current
                        pass
                    else:
                        # flat-dict format: nothing to treat as obsolete here
                        pass

                # New wrapper format
                if isinstance(data, dict) and (
                    "permanent_stats" in data or "global_progress" in data
                ):
                    ps = data.get("permanent_stats", {})
                    gp = data.get("global_progress", {})
                    if isinstance(ps, dict):
                        for k, v in ps.items():
                            if isinstance(v, int):
                                self.game.permanent_stats[k] = v
                    if isinstance(gp, dict):
                        # Accept JSON-serializable types for global progress
                        self.game.global_progress.update(gp)
                elif isinstance(data, dict):
                    # Backwards-compatible: flat dict treated as permanent_stats
                    for k, v in data.items():
                        if isinstance(v, int):
                            self.game.permanent_stats[k] = v
                self._ensure_permanent_stat_keys()
                # Remove legacy keys related to old tower/statue formats that should no longer be present
                self._prune_legacy_permanent_keys()

                # Migration: if the loaded file contained obsolete blasphemy_6..10 keys,
                # we've pruned them above — persist the cleaned file so users don't keep
                # seeing legacy data on subsequent loads.
                try:
                    if _loaded_had_obsolete_blasphemies:
                        logger.info(
                            "Migrating persistent permanent_stats: removing obsolete blasphemy_6..10 keys and saving"
                        )
                        self.save_permanent_stats()
                except Exception:
                    pass
                logger.debug(
                    "Loaded permanent_stats: %s; global_progress: %s",
                    self.game.permanent_stats,
                    self.game.global_progress,
                )
        except Exception as e:
            logger.exception("Failed to load persistent data: %s", e)

    def _prune_legacy_permanent_keys(self) -> None:
        """Remove legacy permanent_stats keys that refer to old tower/statue formats.

        Keys containing 'tower' or 'statue' are considered legacy and removed to avoid
        showing or persisting outdated data structures.
        """
        removed = []
        for k in list(self.game.permanent_stats.keys()):
            # Legacy tower/statue keys
            if "tower" in k or "statue" in k:
                removed.append(k)
                self.game.permanent_stats.pop(k, None)
            # Remove deprecated Blasphemy slots (7..10) if present in older save files
            if k.startswith("blasphemy_"):
                try:
                    num = int(k.split("_")[-1])
                except Exception:
                    num = 0
                # NOTE: blasphemy_6..10 are valid slots now — only prune truly out-of-range indices (>10)
                if num > 10:
                    removed.append(k)
                    self.game.permanent_stats.pop(k, None)
        if removed:
            logger.info("Pruned legacy permanent_stats keys: %s", removed)

    def save_permanent_stats(self) -> None:
        """Persist current permanent stats and global progress to disk.

        If no `permanent_stats_file` was supplied when the Game was created, this
        function becomes a no-op (tests and some runtime usage expect that
        creating a Game() without persistence doesn't attempt to write files).
        """
        try:
            # If persistence wasn't configured, do nothing (don't raise)
            if (
                not hasattr(self.game, "permanent_stats_file")
                or not self.game.permanent_stats_file
            ):
                logger.debug("No permanent_stats_file configured; skipping save")
                return

            p = self.game.permanent_stats_file
            logger.debug("Saving persistent data to %s", p)
            if not p.parent.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "permanent_stats": self.game.permanent_stats,
                "global_progress": self.game.global_progress,
            }
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            logger.debug("Persistent data saved, file exists: %s", p.exists())
        except Exception as e:
            logger.exception("Failed to save persistent data: %s", e)
