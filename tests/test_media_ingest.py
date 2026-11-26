import pytest

from src.media_ingest import MediaAsset, accept_media


def test_ingestion_policy_accepts_video_and_rejects_unexpected_media():
    assert accept_media(MediaAsset("a-1", "a-1/video.mp4", "video/mp4", 1024))
    assert not accept_media(MediaAsset("a-2", "a-2/photo.jpg", "image/jpeg", 1024))
    assert not accept_media(MediaAsset("a-3", "a-3/video.mp4", "video/mp4", 5 * 1024**3 + 1))
