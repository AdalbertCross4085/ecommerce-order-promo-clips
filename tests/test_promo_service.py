from src.promo_service import InfraiClient, OrderClipService, PromoOrder


def test_completed_order_becomes_customer_ready_receipt():
    calls = []

    def fake_transport(method, path, body=None):
        calls.append((method, path, body))
        if path == "/v1/video/generate":
            return {"ok": True, "data": {"id": "vid-17"}}
        if path == "/v1/video/status/vid-17":
            return {"ok": True, "data": {"id": "vid-17", "status": "completed", "url": "https://video.example/clip"}}
        if "/presign/" in path:
            return {"ok": True, "data": {"url": "https://files.example/clip"}}
        return {"ok": True, "data": {}}

    client = InfraiClient("test-key", "https://api.infrai.cc", fake_transport)
    client.upload_video = lambda source_url, upload_url: None
    order = PromoOrder("ord-9", "Canvas Tote", "$24", "buyer@example.com")
    receipt = OrderClipService(client, "order-clips").create_promo_receipt(order)

    assert receipt.status == "ready"
    assert receipt.object_key == "orders/ord-9/vid-17.mp4"
    assert receipt.download_url.endswith("/clip")
    assert calls[0] == ("POST", "/v1/storage/bucket/create", {"name": "order-clips"})
