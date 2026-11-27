"""Stock photos: check the uploaded files and store them in backend/uploads/stock/.

Rules: at most settings.max_stock_photos pictures per listing, each at most settings.max_photo_mb,
and only real JPEG, PNG or WebP images. The type is read from the file's first bytes, so a renamed
file or a wrong Content-Type header cannot get past the check.
"""
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.models.catalog import StockListing, StockPhoto


def stock_dir() -> Path:
    path = Path(settings.upload_dir) / "stock"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _extension(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def add_photos(db: Session, listing: StockListing, files: list[UploadFile]) -> None:
    """Validate every file first; save them only if all are fine."""
    files = [f for f in files if f.filename]
    if not files:
        raise HTTPException(400, "Choose at least one photo")
    room = settings.max_stock_photos - len(listing.photo_rows)
    if len(files) > room:
        raise HTTPException(
            400, f"A listing can have {settings.max_stock_photos} photos. You can add {max(room, 0)} more."
        )

    limit = settings.max_photo_mb * 1024 * 1024
    checked: list[tuple[bytes, str]] = []
    for upload in files:
        data = upload.file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"{upload.filename}: each photo must be {settings.max_photo_mb} MB or smaller")
        ext = _extension(data)
        if not ext:
            raise HTTPException(400, f"{upload.filename}: only JPG, PNG or WebP pictures are allowed")
        checked.append((data, ext))

    folder = stock_dir()
    position = len(listing.photo_rows)
    for data, ext in checked:
        name = f"{uuid.uuid4().hex}{ext}"
        (folder / name).write_bytes(data)
        db.add(StockPhoto(listing_id=listing.id, filename=name, position=position))
        position += 1
    db.flush()
    db.refresh(listing)


def delete_files(filenames: list[str]) -> None:
    """Remove image files from disk (used after a listing is deleted). Missing files are ignored."""
    for name in filenames:
        try:
            (stock_dir() / name).unlink(missing_ok=True)
        except OSError:
            pass
