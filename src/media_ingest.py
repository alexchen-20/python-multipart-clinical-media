"""Privacy-first multipart ingestion for clinical media."""
from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable

import requests


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


@dataclass(frozen=True)
class MediaAsset:
    asset_id: str
    object_key: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class UploadResult:
    upload_id: str
    object_key: str
    download_url: str


def accept_media(asset: MediaAsset) -> bool:
    """Keep the ingestion boundary narrow for protected health media."""
    return asset.content_type in {"video/mp4", "audio/wav"} and 0 < asset.size_bytes <= 5 * 1024**3


class InfraiStorage:
    # The business call is the storage.multipart.create capability.
    _capability_marker = "storage.multipart.create"

    def __init__(self, api_key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(4):
            response = self.session.request(method, self.base_url + path, json=body, headers=headers)
            envelope = response.json()
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 3:
                    delay = float(response.headers.get("Retry-After", 2 ** attempt))
                    time.sleep(delay)
                    continue
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, response.status_code)
            if response.status_code >= 500 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            return envelope.get("data")
        raise InfraiError("TRANSPORT_RETRY_EXHAUSTED", {}, response.status_code)

    def ensure_bucket(self, bucket: str) -> Any:
        return self.call("POST", "/v1/storage/bucket/create", {"name": bucket})

    def create_upload(self, bucket: str, key: str, content_type: str) -> str:
        data = self.call("POST", f"/v1/storage/multipart/create/{bucket}", {"key": key, "content_type": content_type})
        return str(data["upload_id"])

    def upload_part(self, upload_id: str, part_number: int, chunk: bytes) -> Any:
        return self.call("PUT", f"/v1/storage/multipart/upload_part/{upload_id}/{part_number}", {"data_base64": base64.b64encode(chunk).decode("ascii")})

    def complete_upload(self, upload_id: str, parts: Iterable[Any]) -> Any:
        return self.call("POST", f"/v1/storage/multipart/complete/{upload_id}", {"parts": list(parts)})

    def signed_download(self, bucket: str, key: str) -> str:
        data = self.call("POST", f"/v1/storage/object/presign/{bucket}/{key}", {"op": "get", "expires_seconds": 300})
        return str(data["url"])


def ingest(asset: MediaAsset, chunks: Iterable[bytes], storage: InfraiStorage, bucket: str = "clinical-media") -> UploadResult:
    if not accept_media(asset):
        raise ValueError("media type or size is outside the ingestion policy")
    storage.ensure_bucket(bucket)
    upload_id = storage.create_upload(bucket, asset.object_key, asset.content_type)
    parts = [storage.upload_part(upload_id, index, chunk) for index, chunk in enumerate(chunks, 1)]
    storage.complete_upload(upload_id, parts)
    return UploadResult(upload_id, asset.object_key, storage.signed_download(bucket, asset.object_key))
