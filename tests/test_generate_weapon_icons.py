import os
import pygame
import importlib.util
import sys

from src import weapons


def run_script_and_capture(monkeypatch, tmp_path):
    """Import the generate_weapon_icons module and run its main() with a fake
    output directory.

    We monkeypatch ``pygame.image.save`` so that no real files are written;
    instead we record the filenames and sizes requested.  We set CWD to the
    temporary path so that the script's default output_dir (``assets``) points
    inside the temporary directory.
    """
    calls = []

    def fake_save(surface, fname):
        calls.append(fname)

    monkeypatch.setattr(pygame.image, "save", fake_save)

    # ensure dummy video driver so the script works in CI
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    # temporarily change to tmp_path so assets/ points there
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        spec = importlib.util.spec_from_file_location(
            "generate_weapon_icons",
            os.path.join(cwd, "scripts", "generate_weapon_icons.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)  # type: ignore
        mod.main()
    finally:
        os.chdir(cwd)
    return calls


def test_generate_weapon_icons_creates_expected_files(tmp_path, monkeypatch):
    calls = run_script_and_capture(monkeypatch, tmp_path)
    # verify that at least one call was made and that it contains weapon_ prefix
    assert calls, "pygame.image.save was never called"
    assert all(os.path.basename(c).startswith("weapon_") for c in calls)
    # expect an icon for every weapon definition; use the icon field if
    # specified or fall back to the lowercase id pattern.
    expected = set()
    for wid, d in weapons.WEAPON_DEFS.items():
        fname = d.get("icon") or f"weapon_{wid.lower()}.png"
        expected.add(fname)
    written = {os.path.basename(c) for c in calls}
    assert expected == written, f"output mismatch: {written} vs {expected}"
