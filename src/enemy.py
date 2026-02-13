"""Compatibility shim: export Enemy from the new `entities` package."""

from src.entities.enemy import Enemy

__all__ = ["Enemy"]
