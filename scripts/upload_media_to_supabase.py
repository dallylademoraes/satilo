import mimetypes
import os
from pathlib import Path

from supabase import create_client


def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    bucket = os.getenv("SUPABASE_BUCKET", "media")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.")
    if not url.endswith("/"):
        url = f"{url}/"

    root = Path(__file__).resolve().parents[1]
    media_root = root / "media"
    if not media_root.exists():
        raise SystemExit(f"Media folder not found: {media_root}")

    client = create_client(url, key)

    for path in media_root.rglob("*"):
        if path.is_dir():
            continue
        rel_path = path.relative_to(media_root).as_posix()
        content_type, _ = mimetypes.guess_type(str(path))
        options = {"upsert": "true"}
        if content_type:
            options["content-type"] = content_type

        with path.open("rb") as f:
            data = f.read()
        client.storage.from_(bucket).upload(rel_path, data, options)

    print("Upload complete.")


if __name__ == "__main__":
    main()
