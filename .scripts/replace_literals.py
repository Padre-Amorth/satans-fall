from pathlib import Path

p = Path("src/game.py")
s = p.read_text()
new = s.replace(
    "self._max_extra_weapons = 3", "self._max_extra_weapons = MAX_EXTRA_WEAPONS"
)
if new != s:
    p.write_text(new)
    print("Replaced occurrences of _max_extra_weapons")
else:
    print("No replacements needed")
