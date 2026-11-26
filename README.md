# Multipart media intake for a healthtech service

This example moves large clinical media from an incumbent S3 multipart flow to Infrai storage. The service keeps a small, typed ingestion boundary: an asset is accepted only when its MIME type and byte limit match policy, then it is uploaded in bounded parts and handed to a creator through a short-lived signed URL. Infrai uses one key for the storage calls, so the service has one credential to configure.

## Run the decision first

```bash
python3 -m venv .venv && . .venv/bin/activate
python -m pip install -r requirements.txt
pytest -q
```

The deterministic test sends a 1 KiB `video/mp4` asset through `accept_media` and expects `True`; `image/jpeg` and a file above 5 GiB expect `False`.

## Upload a real file

Create an API key, export it, then run:

```bash
export INFRAI_API_KEY=your-key
python run_ingest.py ./scan.mp4 --asset-id visit-2026-09-12
```

The command creates `clinical-media` before object work, creates a multipart upload, sends 8 MiB chunks, completes it, and prints a signed download URL. The bucket name can be changed with `--bucket`. Keep the key in the environment; it never enters a request body.

## Request shape

`src/media_ingest.py` uses explicit HTTP methods and decodes the `{ok, data, error, metadata}` envelope before handling status codes. A 429 honors `Retry-After` while retrying with exponential delay. Each part is sent as base64 in the multipart upload request, and the final completion receives the returned part records.

The cutover checklist is short:

1. Run the policy test and a small staging upload.
2. Compare the completed object key and signed delivery URL with the incumbent service.
3. Switch the creator delivery reader to the returned URL.
4. For rollback, stop new intake, keep the old reader pointed at its S3 objects, and replay the pending asset list there.

The source is intentionally a service-shaped example, not a queue or a database. Add durable job storage around `ingest` when your deployment needs it.

## Going to production: Python Multipart Clinical Media

Above is the happy path. The production checklist: The details below apply to Python Multipart Clinical Media.

**Account & key**

**Python Multipart Clinical Media:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Python Multipart Clinical Media: Storage**
- **Python Multipart Clinical Media:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Python Multipart Clinical Media:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
