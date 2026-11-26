import argparse
from pathlib import Path

from src.media_ingest import InfraiStorage, MediaAsset, ingest


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a media file in bounded multipart chunks")
    parser.add_argument("path", type=Path)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--bucket", default="clinical-media")
    args = parser.parse_args()
    asset = MediaAsset(args.asset_id, f"assets/{args.asset_id}/{args.path.name}", "video/mp4", args.path.stat().st_size)
    chunk_size = 8 * 1024 * 1024
    with args.path.open("rb") as handle:
        chunks = iter(lambda: handle.read(chunk_size), b"")
        result = ingest(asset, chunks, InfraiStorage(), args.bucket)
    print(f"uploaded {result.object_key}; download={result.download_url}")


if __name__ == "__main__":
    main()
