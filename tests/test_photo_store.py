from datetime import datetime

import pytest

from recipe_agent.photo_store import SourcePhoto, save_photos, sniff_image_ext

WHEN = datetime(2026, 10, 25, 18, 30, 5)
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 20


def _src(tmp_path, name, short, ext=".jpg", data=JPEG):
    p = tmp_path / name
    p.write_bytes(data)
    return SourcePhoto(p, ext, short)


def test_normal_name_format(tmp_path):
    out = tmp_path / "photos"
    saved = save_photos(out, WHEN, [_src(tmp_path, "a.jpg", "番茄")])
    assert saved == ["2026-10-25 18-30-05 番茄.jpg"]
    assert (out / saved[0]).read_bytes() == JPEG


def test_same_second_same_name_gets_suffix(tmp_path):
    out = tmp_path / "photos"
    a = save_photos(out, WHEN, [_src(tmp_path, "a.jpg", "番茄"), _src(tmp_path, "b.jpg", "番茄"), _src(tmp_path, "c.jpg", "番茄")])
    b = save_photos(out, WHEN, [_src(tmp_path, "d.jpg", "番茄")])
    assert a == ["2026-10-25 18-30-05 番茄.jpg", "2026-10-25 18-30-05 番茄-2.jpg", "2026-10-25 18-30-05 番茄-3.jpg"]
    assert b == ["2026-10-25 18-30-05 番茄-4.jpg"]
    assert len(list(out.iterdir())) == 4


@pytest.mark.parametrize(
    "evil",
    ["../../evil", "..\\..\\evil", "a/b", "a\\b", "C:\\Windows\\x", "x:y", "a*b?c", 'a"b<c>d|e', "line1\nline2",
     "／／evil", "＼＼evil", "...", "   ", "", "CON", "nul", "a" * 200, "..", ". .", "\x00\x01"],
)
def test_guard3_evil_names_stay_inside_photos_dir(tmp_path, evil):
    out = tmp_path / "photos"
    saved = save_photos(out, WHEN, [_src(tmp_path, "a.jpg", evil)])
    assert len(saved) == 1
    written = list(tmp_path.rglob("*.jpg"))
    inside = [p for p in written if p.parent == out]
    assert len(inside) == 1
    assert not any(p.name == "evil.jpg" for p in written)
    name = saved[0]
    assert not any(ch in name for ch in '/\\:*?"<>|\n') and ".." not in name
    assert len(name) < 60


def test_guard3_empty_becomes_unnamed(tmp_path):
    saved = save_photos(tmp_path / "photos", WHEN, [_src(tmp_path, "a.jpg", "///")])
    assert saved == ["2026-10-25 18-30-05 未命名.jpg"]


def test_sniff_image_ext():
    assert sniff_image_ext(JPEG) == ".jpg"
    assert sniff_image_ext(b"\x89PNG\r\n\x1a\n....") == ".png"
    assert sniff_image_ext(b"GIF89a....") == ".gif"
    assert sniff_image_ext(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == ".webp"
    assert sniff_image_ext(b"%PDF-1.7") is None
    assert sniff_image_ext(b"") is None
