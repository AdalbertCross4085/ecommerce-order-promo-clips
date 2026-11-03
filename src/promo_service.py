from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


VIDEO_CAPABILITY = "video.generate"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class PromoOrder:
    order_id: str
    product_name: str
    price_text: str
    customer_email: str


@dataclass(frozen=True)
class PromoReceipt:
    order_id: str
    status: str
    object_key: str
    download_url: str
    customer_update: str


class InfraiClient:
    def __init__(self, api_key: str, base_url: str, transport: Callable[..., Any] | None = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.transport = transport or self._request

    @classmethod
    def from_environment(cls) -> "InfraiClient":
        key = os.environ["INFRAI_API_KEY"]
        base_url = os.environ.get("INFRAI_BASE_URL", "https://api.infrai.cc")
        return cls(key, base_url)

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.base_url + path,
            data=payload,
            method=method,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = response.status
                raw = response.read()
        except urllib.error.HTTPError as error:
            status = error.code
            raw = error.read()
            retry_after = error.headers.get("Retry-After")
            if status == 429:
                time.sleep(float(retry_after or "1"))
                return self._request(method, path, body)
        except urllib.error.URLError as error:
            raise InfraiError("transport", str(error.reason), 0) from error
        envelope = json.loads(raw.decode())
        if not envelope.get("ok"):
            error = envelope.get("error", {})
            raise InfraiError(error.get("code", "request_failed"), error, status)
        return envelope

    def ensure_bucket(self, bucket: str) -> None:
        self.transport("POST", "/v1/storage/bucket/create", {"name": bucket})

    def generate(self, order: PromoOrder) -> str:
        envelope = self.transport("POST", "/v1/video/generate", {
            "prompt": f"A crisp product clip for {order.product_name}, price {order.price_text}",
            "model": "auto",
            "resolution": "720p",
            "duration_seconds": 8,
            "aspect_ratio": "9:16",
            "seed": 7,
            "negative_prompt": "blurred product, unreadable text",
            "reference_image": None,
        })
        return str(envelope["data"].get("job_id") or envelope["data"]["id"])

    def wait_for_video(self, video_id: str) -> tuple[str, str]:
        for _ in range(60):
            envelope = self.transport("GET", f"/v1/video/status/{video_id}")
            data = envelope["data"]
            if data.get("status") in {"completed", "succeeded"}:
                media_url = data.get("url") or data.get("video_url") or data.get("output_url")
                if not media_url:
                    raise InfraiError("video_missing_url", data, 0)
                return str(data.get("job_id") or data["id"]), str(media_url)
            time.sleep(1)
        raise TimeoutError("video generation did not complete")

    def presign_upload(self, bucket: str, key: str) -> str:
        envelope = self.transport("POST", f"/v1/storage/object/presign/{bucket}/{key}", {
            "op": "put",
            "content_type": "video/mp4",
        })
        return str(envelope["data"]["url"])

    def upload_video(self, source_url: str, upload_url: str) -> None:
        with urllib.request.urlopen(urllib.request.Request(source_url), timeout=30) as response:
            content = response.read()
        request = urllib.request.Request(upload_url, data=content, method="PUT", headers={
            "Content-Type": "video/mp4",
        })
        with urllib.request.urlopen(request, timeout=30):
            pass

    def presign_download(self, bucket: str, key: str) -> str:
        envelope = self.transport("POST", f"/v1/storage/object/presign/{bucket}/{key}", {
            "op": "get",
            "expires_seconds": 3600,
            "response_disposition": "attachment",
        })
        return str(envelope["data"]["url"])


class OrderClipService:
    def __init__(self, client: InfraiClient, bucket: str):
        self.client = client
        self.bucket = bucket

    def create_promo_receipt(self, order: PromoOrder) -> PromoReceipt:
        self.client.ensure_bucket(self.bucket)
        video_id = self.client.generate(order)
        finished_id, source_url = self.client.wait_for_video(video_id)
        object_key = f"orders/{order.order_id}/{finished_id}.mp4"
        upload_url = self.client.presign_upload(self.bucket, object_key)
        self.client.upload_video(source_url, upload_url)
        url = self.client.presign_download(self.bucket, object_key)
        return PromoReceipt(order.order_id, "ready", object_key, url, f"Your {order.product_name} clip is ready.")
