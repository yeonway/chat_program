"""병합된 파일에 대한 클라이언트 MIME·매직 바이트(filetype) 검증."""

from __future__ import annotations

import os
from typing import Final

import filetype

# 확장자 → 클라이언트가 보낼 수 있는 Content-Type (소문자, 파라미터 제외)
ALLOWED_CLIENT_MIMES: Final[dict[str, frozenset[str]]] = {
    ".pdf": frozenset({"application/pdf"}),
    ".zip": frozenset({"application/zip", "application/x-zip-compressed"}),
    ".png": frozenset({"image/png"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".gif": frozenset({"image/gif"}),
    ".webp": frozenset({"image/webp"}),
    ".txt": frozenset({"text/plain", "application/octet-stream"}),
    ".mp4": frozenset({"video/mp4", "application/octet-stream"}),
    ".mp3": frozenset({"audio/mpeg", "audio/mp3", "application/octet-stream"}),
    ".doc": frozenset({"application/msword", "application/octet-stream"}),
    ".docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
            "application/octet-stream",
        }
    ),
}

# 매직 바이트로 판별된 MIME이 이 집합에 있어야 함 (docx는 zip 시그니처로 잡힐 수 있음)
ALLOWED_DETECTED_MIMES: Final[dict[str, frozenset[str]]] = {
    ".pdf": frozenset({"application/pdf"}),
    ".zip": frozenset({"application/zip", "application/x-zip-compressed"}),
    ".png": frozenset({"image/png"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".gif": frozenset({"image/gif"}),
    ".webp": frozenset({"image/webp"}),
    ".txt": frozenset(),  # 별도 규칙
    ".mp4": frozenset({"video/mp4", "audio/mp4"}),
    ".mp3": frozenset({"audio/mpeg"}),
    ".doc": frozenset({"application/msword"}),
    ".docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
            "application/x-zip-compressed",
        }
    ),
}

_READ_HEAD = 1024 * 256  # 256KB 스니핑

_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class FileContentValidationError(Exception):
    """MIME/매직 불일치."""


def _normalize_client_mime(mime: str) -> str:
    return mime.split(";")[0].strip().lower()


def validate_merged_file(path: str, declared_ext: str, client_mime: str) -> None:
    """
    병합 완료 후 디스크 상의 파일 검증.
    declared_ext: 소문자, 점 포함 (예: .png)
    """
    ext = declared_ext.lower()
    if ext not in ALLOWED_CLIENT_MIMES:
        raise FileContentValidationError("지원하지 않는 확장자입니다.")

    client_main = _normalize_client_mime(client_mime)
    if client_main not in ALLOWED_CLIENT_MIMES[ext]:
        raise FileContentValidationError("선언한 MIME이 이 확장자에 허용되지 않습니다.")

    size = os.path.getsize(path)
    if size == 0:
        raise FileContentValidationError("빈 파일은 허용되지 않습니다.")

    with open(path, "rb") as f:
        head = f.read(min(_READ_HEAD, size))

    if ext == ".txt":
        if b"\x00" in head[:8192]:
            raise FileContentValidationError("텍스트 파일에 바이너리 데이터가 포함되어 있습니다.")
        return

    guessed = filetype.guess(head)
    if ext == ".doc" and guessed is None and len(head) >= 8 and head[:8] == _OLE_MAGIC:
        return

    if guessed is None:
        raise FileContentValidationError("파일 내용 형식을 확인할 수 없습니다. 손상되었거나 허용되지 않는 형식일 수 있습니다.")

    detected = guessed.mime.lower()
    allowed_det = ALLOWED_DETECTED_MIMES.get(ext)
    if not allowed_det or detected not in allowed_det:
        raise FileContentValidationError("파일 내용이 확장자/MIME과 일치하지 않습니다.")
