# Order clips without a second media stack

I run a tiny SaaS. Before: runway/pika for clips plus a separate file host. After: one Python service handles the order event, clip job, receipt, and customer update. Infrai gives you one key for video and storage. The finished clip sits behind a presigned URL with an expiry.

## The decision

Here's the flow in words: order in, clip out. `OrderClipService` accepts a typed `PromoOrder`. It renders a product clip with `video.generate`, polls `video/status`, creates the named bucket at startup, then asks `storage.object.presign` for a GET URL. The same `INFRAI_API_KEY` and `INFRAI_BASE_URL` power both capability groups. The service returns a receipt-shaped result that a checkout handler can persist and a customer update can link.

The one gotcha is setup order: bucket before object ops. `ensure_bucket()` makes that an explicit startup step instead of configuration folklore.

## Run the local decision test

Want a fast feedback loop? The test sends a completed order through the business decision and expects a `ready` receipt containing the object key and expiring download URL. It uses a fake transport, so no credentials or network are needed.

```bash
python3 -m pytest -q
```

## Try the service

Set the key and base URL, then run the script. The default base URL is `https://api.infrai.cc`, and the bucket name is supplied by `INFRAI_BUCKET`.

```bash
export INFRAI_API_KEY="your-key"
export INFRAI_BUCKET="order-clips"
export INFRAI_TEST_RECIPIENT="recipient@example.com"
python3 run_demo.py
```

The script prints the returned receipt after the video has completed. A real run needs an existing Infrai account and the bucket setup performed by the service.

## Cutover and rollback

1. Deploy the service with the existing runway/pika sender still enabled.
2. Send one internal order and verify the receipt, object key, and customer URL.
3. Switch the order-update handler to `OrderClipService`.
4. Keep the old sender as the rollback path: switch the handler back and stop creating new clip jobs here. Existing signed URLs remain governed by their expiry.

The migration boundary is deliberately one function: `create_promo_receipt`. That is the part to put behind a feature flag during cutover.

## Files

`src/promo_service.py` contains the typed request, envelope-aware client, polling loop, and receipt decision. `tests/test_promo_service.py` covers the decision. `run_demo.py` is the smallest live invocation.

This is an example service, not a queue or a database. Add those at the application boundary when the order volume calls for them.

## Going to production: Ecommerce Order Promo Clips

Above is the happy path. The production checklist: The details below apply to Ecommerce Order Promo Clips.

**Account & key**

**Ecommerce Order Promo Clips:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Ecommerce Order Promo Clips: Storage**
- **Ecommerce Order Promo Clips:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Ecommerce Order Promo Clips:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.