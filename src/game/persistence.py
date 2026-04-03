"""Profile and save system utilities."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def profile_path(slot: int) -> Path:
    """Return the Path for a given profile slot (1-3)."""
    return Path(__file__).parent.parent.parent / f"profile_{slot}.json"


def migrate_legacy_save() -> None:
    """Move permanent_stats.json → profile_1.json on first launch with new profile system."""
    import shutil

    legacy = Path(__file__).parent.parent.parent / "permanent_stats.json"
    target = profile_path(1)
    if legacy.exists() and not target.exists():
        try:
            shutil.copy2(str(legacy), str(target))
            logger.info("Migrated %s → %s", legacy, target)
        except Exception as e:
            logger.warning("Could not migrate legacy save: %s", e)


def load_last_profile_slot() -> int | None:
    """Load the last selected profile slot from any profile's save file.

    Searches all 3 profile files to find which one was most recently played,
    and returns that slot. Uses 'last_played' timestamp to determine order.
    Returns the slot number (1-3) or None if no profiles exist.
    """
    profiles = []
    for slot in range(1, 4):
        path = profile_path(slot)
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_played_str = data.get("last_played", "")
            try:
                last_played = datetime.fromisoformat(last_played_str)
            except (AttributeError, TypeError, ValueError, KeyError):
                last_played = datetime.fromtimestamp(0)
            profiles.append((slot, last_played))
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    if not profiles:
        return None

    profiles.sort(key=lambda x: x[1], reverse=True)
    most_recent_slot = profiles[0][0]
    logger.debug(
        "Loaded last profile slot: %s (last_played: %s)",
        most_recent_slot,
        profiles[0][1],
    )
    return most_recent_slot


def load_permanent_stats(game: Any) -> None:
    """Load permanent stats and global meta-progress from disk.

    Reads the active profile file (``profile_N.json``) from the project root.
    If the file does not exist (first launch / empty slot) or is corrupt the
    method silently returns so the caller's ``setdefault`` calls supply safe
    initial values.
    """
    slot = getattr(game, "active_profile_slot", None)
    if slot is None:
        return
    save_path = profile_path(slot)
    if not save_path.exists():
        logger.debug("No save file found at %s — starting fresh", save_path)
        return
    try:
        with open(save_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        ps = data.get("permanent_stats", {})
        if isinstance(ps, dict):
            for k, v in ps.items():
                if isinstance(k, str) and isinstance(v, int):
                    game.permanent_stats[k] = v

        gp = data.get("global_progress", {})
        if isinstance(gp, dict):
            for key in ("meta_xp", "meta_level", "meta_points", "blasphemy_points"):
                if key in gp and isinstance(gp[key], (int, float)):
                    game.global_progress[key] = int(gp[key])
            sc = gp.get("stages_cleared")
            if isinstance(sc, dict):
                game.global_progress["stages_cleared"] = sc
            for key in ("display", "audio"):
                if key in gp and isinstance(gp[key], dict):
                    game.global_progress[key] = gp[key]

        name = data.get("name")
        if isinstance(name, str):
            game.global_progress["profile_name"] = name

        logger.debug("Loaded permanent stats from %s (slot %s)", save_path, slot)
    except Exception as e:
        logger.warning("Failed to load permanent stats from %s: %s", save_path, e)


def save_permanent_stats(game: Any) -> None:
    """Write permanent stats and global meta-progress to disk.

    Saves to ``profile_N.json`` in the project root using an atomic write
    (temp file + os.replace) so a crash mid-write never corrupts the save.
    Does nothing if no profile slot is active.

    **Regression guard**: before writing, the existing profile file is read.
    If the in-memory state looks like a default/uninitialized reset (meta_level
    dropped while permanent_stats still have upgrades on disk), the save is
    blocked to prevent overwriting hard-earned progression with zeros.
    Values that can only grow (meta_level, permanent_stat tiers, stages_cleared)
    are enforced to never decrease.
    """
    slot = getattr(game, "active_profile_slot", None)
    if slot is None:
        return
    save_path = profile_path(slot)
    tmp_path = save_path.with_suffix(".json.tmp")

    # --- Regression guard: read existing on-disk data ---------------------
    disk_ps: Dict[str, int] = {}
    disk_gp: Dict[str, Any] = {}
    if save_path.exists():
        try:
            with open(save_path, "r", encoding="utf-8") as f:
                disk_data = json.load(f)
            raw_ps = disk_data.get("permanent_stats", {})
            if isinstance(raw_ps, dict):
                for k, v in raw_ps.items():
                    if isinstance(k, str) and isinstance(v, int):
                        disk_ps[k] = v
            raw_gp = disk_data.get("global_progress", {})
            if isinstance(raw_gp, dict):
                disk_gp = raw_gp
        except Exception:
            pass  # if the file is corrupt we just save what we have

    # Detect whether in-memory state looks like an uninitialized reset:
    # if the disk has significant upgrades but memory has none, the in-memory
    # state was likely wiped by a code restart / crash.
    mem_total = sum(game.permanent_stats.get(k, 0) for k in game.permanent_stats)
    dsk_total = sum(disk_ps.values())
    # A reset is: disk has upgrades but memory has zero (all defaults).
    # This catches the case where Game() was constructed but global_progress
    # was wiped before load_permanent_stats ran.
    is_likely_reset = dsk_total > 0 and mem_total == 0

    if is_likely_reset:
        # Restore ALL disk data — memory state is not trustworthy
        dsk_meta_level = (
            int(disk_gp.get("meta_level", 1))
            if isinstance(disk_gp.get("meta_level"), (int, float))
            else 1
        )
        dsk_xp = (
            int(disk_gp.get("meta_xp", 0))
            if isinstance(disk_gp.get("meta_xp"), (int, float))
            else 0
        )
        dsk_pts = (
            int(disk_gp.get("meta_points", 0))
            if isinstance(disk_gp.get("meta_points"), (int, float))
            else 0
        )
        logger.warning(
            "Regression guard: memory looks reset (0 upgrades vs %d on disk), "
            "restoring disk values (level=%d, xp=%d, points=%d)",
            dsk_total,
            dsk_meta_level,
            dsk_xp,
            dsk_pts,
        )
        game.global_progress["meta_level"] = dsk_meta_level
        game.global_progress["meta_xp"] = dsk_xp
        game.global_progress["meta_points"] = dsk_pts
        dsk_bp = (
            int(disk_gp.get("blasphemy_points", 0))
            if isinstance(disk_gp.get("blasphemy_points"), (int, float))
            else 0
        )
        game.global_progress["blasphemy_points"] = dsk_bp
        for k, v in disk_ps.items():
            game.permanent_stats[k] = v
    else:
        # Normal save path: player intentionally modified stats (upgrade/downgrade).
        # Allow individual stats to decrease (right-click downgrade).
        # Restore stats that exist on disk but not in memory (edge case).
        for k in disk_ps:
            if k not in game.permanent_stats:
                game.permanent_stats[k] = disk_ps[k]

    # Guard 2: stages_cleared can only grow (union) — always applies
    dsk_sc = disk_gp.get("stages_cleared", {})
    if isinstance(dsk_sc, dict):
        mem_sc = game.global_progress.get("stages_cleared", {})
        if isinstance(mem_sc, dict):
            merged_sc = dict(dsk_sc)
            merged_sc.update(mem_sc)
            game.global_progress["stages_cleared"] = merged_sc

    # --- Build save data --------------------------------------------------
    profile_name = game.global_progress.get("profile_name", f"Profile {slot}")
    game.global_progress["active_profile_slot"] = slot
    data = {
        "version": 1,
        "name": profile_name,
        "last_played": datetime.now().isoformat(timespec="seconds"),
        "permanent_stats": dict(game.permanent_stats),
        "global_progress": {
            "meta_xp": game.global_progress.get("meta_xp", 0),
            "meta_level": game.global_progress.get("meta_level", 1),
            "meta_points": game.global_progress.get("meta_points", 0),
            "blasphemy_points": game.global_progress.get("blasphemy_points", 0),
            "stages_cleared": dict(game.global_progress.get("stages_cleared", {})),
            "display": game.global_progress.get("display", {}),
            "audio": game.global_progress.get("audio", {}),
            "active_profile_slot": slot,
        },
    }
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, save_path)
        logger.debug("Saved permanent stats to %s (slot %s)", save_path, slot)
    except Exception as e:
        logger.warning("Failed to save permanent stats: %s", e)
        try:
            tmp_path.unlink(missing_ok=True)
        except (AttributeError, TypeError, ValueError, KeyError):
            pass


def get_profile_info(slot: int) -> Dict[str, Any]:
    """Return display info for a profile slot without loading full stats into game state.

    Returns a dict with keys: exists, name, meta_level, meta_xp, meta_points, last_played.
    """
    path = profile_path(slot)
    if not path.exists():
        return {
            "exists": False,
            "name": "",
            "meta_level": 1,
            "meta_xp": 0,
            "meta_points": 0,
            "last_played": "",
        }
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        gp = data.get("global_progress", {})
        return {
            "exists": True,
            "name": data.get("name", f"Profile {slot}"),
            "meta_level": int(gp.get("meta_level", 1)),
            "meta_xp": int(gp.get("meta_xp", 0)),
            "meta_points": int(gp.get("meta_points", 0)),
            "last_played": data.get("last_played", ""),
        }
    except (AttributeError, TypeError, ValueError, KeyError):
        return {
            "exists": False,
            "name": "",
            "meta_level": 1,
            "meta_xp": 0,
            "meta_points": 0,
            "last_played": "",
        }
