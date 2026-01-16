import os
import re
import sys
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "satilo.settings")

import django  # noqa: E402

django.setup()

from pessoas.models import Pessoa  # noqa: E402


def to_ascii_filename(name: str) -> str:
    stem, ext = os.path.splitext(name)
    normalized = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "_", normalized).strip("._-")
    if not normalized:
        normalized = "foto"
    return f"{normalized}{ext.lower()}"


def main():
    media_root = BASE_DIR / "media"
    uploads_dir = media_root / "fotos_pessoas"
    if not uploads_dir.exists():
        print(f"No media folder found at {uploads_dir}")
        return

    used = set()
    renamed = 0

    for pessoa in Pessoa.objects.exclude(foto="").exclude(foto__isnull=True):
        old_name = pessoa.foto.name
        old_path = media_root / old_name
        if not old_path.exists():
            continue

        new_file = to_ascii_filename(old_path.name)
        candidate = new_file
        counter = 1
        while (uploads_dir / candidate).exists() or candidate in used:
            stem, ext = os.path.splitext(new_file)
            candidate = f"{stem}_{counter}{ext}"
            counter += 1

        if candidate != old_path.name:
            new_rel = f"fotos_pessoas/{candidate}"
            new_path = media_root / new_rel
            new_path.parent.mkdir(parents=True, exist_ok=True)
            old_path.rename(new_path)
            pessoa.foto.name = new_rel
            pessoa.save(update_fields=["foto"])
            renamed += 1
            used.add(candidate)

    print(f"Renamed {renamed} file(s).")


if __name__ == "__main__":
    main()
