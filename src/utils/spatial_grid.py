"""Simple uniform spatial grid for fast neighbor queries.

This is intentionally minimal: it partitions 2D space into square cells and
allows building the grid from arbitrary objects that expose `x` and `y`
attributes (or dicts with 'x'/'y') and an optional radius value. Query uses
circle bounding box to collect candidate objects (deduplicated).
"""

from __future__ import annotations

from typing import Any, Iterable, List, Set, Tuple


class SpatialGrid:
    def __init__(
        self, cell_size: int = 120, width: int = 1280, height: int = 720
    ) -> None:
        self.cell_size: int = max(8, int(cell_size))
        self.width: int = width
        self.height: int = height
        self.cols: int = max(1, (self.width + self.cell_size - 1) // self.cell_size)
        self.rows: int = max(1, (self.height + self.cell_size - 1) // self.cell_size)
        self.cells: List[List[Any]] = [[] for _ in range(self.cols * self.rows)]

    def clear(self) -> None:
        for c in self.cells:
            c.clear()

    def _cell_index(self, col: int, row: int) -> int:
        return row * self.cols + col

    def _bounds_to_cells(
        self, minx: float, miny: float, maxx: float, maxy: float
    ) -> Tuple[int, int, int, int]:
        min_col: int = max(0, int(minx) // self.cell_size)
        max_col: int = min(self.cols - 1, int(maxx) // self.cell_size)
        min_row: int = max(0, int(miny) // self.cell_size)
        max_row: int = min(self.rows - 1, int(maxy) // self.cell_size)
        return min_col, min_row, max_col, max_row

    @staticmethod
    def _get_pos_radius(obj: Any) -> Tuple[float, float, float]:
        # Support both objects with .x/.y/.radius and dict-like with keys
        if hasattr(obj, "x") and hasattr(obj, "y"):
            x = float(getattr(obj, "x"))
            y = float(getattr(obj, "y"))
            r = float(getattr(obj, "radius", 0))
            return x, y, r
        if isinstance(obj, dict):
            x = float(obj.get("x", 0) or 0)
            y = float(obj.get("y", 0) or 0)
            r = float(obj.get("radius", obj.get("rad", 0)) or 0)
            return x, y, r
        # Fallback: try attributes 'rect' center
        rect: Any | None = getattr(obj, "rect", None)
        if rect is not None:
            cx = float(getattr(rect, "centerx", 0))
            cy = float(getattr(rect, "centery", 0))
            return cx, cy, 0.0
        return 0.0, 0.0, 0.0

    def add(self, obj: Any) -> None:
        x, y, r = self._get_pos_radius(obj)
        minx: float = x - r
        miny: float = y - r
        maxx: float = x + r
        maxy: float = y + r
        min_col, min_row, max_col, max_row = self._bounds_to_cells(
            minx, miny, maxx, maxy
        )
        for col in range(min_col, max_col + 1):
            for row in range(min_row, max_row + 1):
                self.cells[self._cell_index(col, row)].append(obj)

    def build(self, objects: Iterable[Any]) -> None:
        self.clear()
        for obj in objects:
            try:
                self.add(obj)
            except Exception:
                # Ignore malformed entries
                continue

    def query_circle(self, x: float, y: float, radius: float) -> List[Any]:
        minx: float = x - radius
        miny: float = y - radius
        maxx: float = x + radius
        maxy: float = y + radius
        min_col, min_row, max_col, max_row = self._bounds_to_cells(
            minx, miny, maxx, maxy
        )
        results: List[Any] = []
        seen: Set[int] = set()
        for col in range(min_col, max_col + 1):
            for row in range(min_row, max_row + 1):
                idx: int = self._cell_index(col, row)
                for obj in self.cells[idx]:
                    oid: int = id(obj)
                    if oid in seen:
                        continue
                    seen.add(oid)
                    results.append(obj)
        return results


__all__: List[str] = ["SpatialGrid"]
