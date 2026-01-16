import os

from django.core.files.storage import Storage
from django.core.exceptions import ImproperlyConfigured
from supabase import create_client


class SupabaseStorage(Storage):
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        bucket = os.getenv("SUPABASE_BUCKET", "media")
        if not url or not key:
            raise ImproperlyConfigured("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.")
        if not url.endswith("/"):
            url = f"{url}/"
        self.bucket = bucket
        self.client = create_client(url, key)

    def _save(self, name, content):
        data = content.read()
        file_options = {"upsert": "true"}
        if getattr(content, "content_type", None):
            file_options["content-type"] = content.content_type
        self.client.storage.from_(self.bucket).upload(name, data, file_options)
        return name

    def exists(self, name):
        return False

    def url(self, name):
        return self.client.storage.from_(self.bucket).get_public_url(name)
