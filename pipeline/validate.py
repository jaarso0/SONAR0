"""Build gate checks for generated packs."""

from pathlib import Path


def validate_pack(pack_dir: Path) -> list[str]:
    errors: list[str] = []
    if not (pack_dir / "meta.json").exists():
        errors.append("missing meta.json")
    if not (pack_dir / "raw").exists():
        errors.append("missing raw directory")
    if not (pack_dir / "build").exists():
        errors.append("missing build directory")
    return errors
