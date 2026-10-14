"""Immutable, authenticated encrypted gzip segments outside the web root."""

import gzip
import hashlib
import io
import json
import os
import re
import stat
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from neoavlod.errors import DomainError
from neoavlod.settings import Settings

MAX_BATCH = 128
MAX_PLAIN = MAX_BATCH * 65536
MAX_CIPHER = MAX_PLAIN * 2
OBJECT_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-f0-9]{64}\.jsonl\.gz\.fernet$")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_line(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


@dataclass(frozen=True)
class SegmentProof:
    object_name: str
    day: date
    ids: list[int]
    plain_hash: str
    cipher_hash: str
    key_id: str


class AuditStore:
    def __init__(self, settings: Settings, *, create: bool = False) -> None:
        if settings.audit_encryption_key is None:
            raise DomainError("Audit shifrlash kaliti sozlanmagan", 503)
        self.directory = settings.audit_dir
        self.key_id = settings.audit_key_id
        self.keys = {self.key_id: Fernet(settings.audit_encryption_key.get_secret_value().encode())}
        try:
            old = (
                json.loads(settings.audit_previous_keys.get_secret_value())
                if settings.audit_previous_keys and settings.audit_previous_keys.get_secret_value()
                else {}
            )
            if not isinstance(old, dict) or len(old) > 8 or self.key_id in old:
                raise ValueError
            for ident, key in old.items():
                if re.fullmatch(r"[a-z0-9_-]{1,32}", ident) is None:
                    raise ValueError
                self.keys[ident] = Fernet(key.encode())
        except (ValueError, TypeError, AttributeError):
            raise DomainError("Audit oldingi kalitlar konfiguratsiyasi yaroqsiz", 503) from None
        if create:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _directory(self) -> int:
        descriptor = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        if os.fstat(descriptor).st_mode & 0o077:
            os.close(descriptor)
            raise OSError("Audit directory must be private")
        return descriptor

    def _read_cipher(self, name: str) -> bytes:
        if OBJECT_PATTERN.fullmatch(name) is None:
            raise ValueError("Invalid audit object name")
        folder = self._directory()
        try:
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
            with os.fdopen(descriptor, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CIPHER:
                    raise ValueError("Invalid audit file")
                result = stream.read(MAX_CIPHER + 1)
                if len(result) > MAX_CIPHER:
                    raise ValueError("Audit file exceeds limit")
                return result
        finally:
            os.close(folder)

    def read(self, proof: SegmentProof) -> list[dict[str, Any]]:
        cipher = self._read_cipher(proof.object_name)
        if sha256(cipher) != proof.cipher_hash or proof.key_id not in self.keys:
            raise ValueError("Audit archive integrity failed")
        try:
            envelope = self.keys[proof.key_id].decrypt(cipher)
        except InvalidToken:
            raise ValueError("Audit archive authentication failed") from None
        header, separator, compressed = envelope.partition(b"\n")
        if not separator or len(header) > 8192:
            raise ValueError("Invalid audit manifest")
        manifest = json.loads(header)
        if manifest != {
            "schema": 1,
            "day": proof.day.isoformat(),
            "ids": proof.ids,
            "plain_sha256": proof.plain_hash,
            "key_id": proof.key_id,
        }:
            raise ValueError("Audit manifest mismatch")
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            raw = stream.read(MAX_PLAIN + 1)
        if len(raw) > MAX_PLAIN or sha256(raw) != proof.plain_hash:
            raise ValueError("Audit plaintext integrity failed")
        records = [json.loads(line) for line in raw.splitlines()]
        if (
            len(records) != len(proof.ids)
            or not 1 <= len(records) <= MAX_BATCH
            or [int(e["id"]) for e in records] != proof.ids
            or any(e["day"] != proof.day.isoformat() for e in records)
        ):
            raise ValueError("Audit records mismatch")
        return records

    def persist(self, day: date, records: list[dict[str, Any]]) -> SegmentProof:
        if not 1 <= len(records) <= MAX_BATCH:
            raise ValueError("Audit batch exceeds limit")
        ids = [int(e["id"]) for e in records]
        if len(set(ids)) != len(ids) or any(e["day"] != day.isoformat() for e in records):
            raise ValueError("Audit batch mismatch")
        raw = b"".join(json_line(e) for e in records)
        if len(raw) > MAX_PLAIN:
            raise ValueError("Audit plaintext exceeds limit")
        plain_hash = sha256(raw)
        manifest = {
            "schema": 1,
            "day": day.isoformat(),
            "ids": ids,
            "plain_sha256": plain_hash,
            "key_id": self.key_id,
        }
        name = f"{day}-{sha256(json_line(manifest))}.jsonl.gz.fernet"
        cipher = self.keys[self.key_id].encrypt(json_line(manifest) + gzip.compress(raw, mtime=0))
        folder = self._directory()
        temporary = f".pending-{uuid.uuid4().hex}"
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=folder,
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(cipher)
                stream.flush()
                os.fsync(stream.fileno())
                os.fchmod(stream.fileno(), 0o400)
                os.fsync(stream.fileno())
            try:
                os.link(
                    temporary, name, src_dir_fd=folder, dst_dir_fd=folder, follow_symlinks=False
                )
            except FileExistsError:
                # Valid orphan from a previous crash is reused, never overwritten.
                cipher = self._read_cipher(name)
            os.fsync(folder)
        finally:
            try:
                os.unlink(temporary, dir_fd=folder)
            except FileNotFoundError:
                pass
            os.close(folder)
        proof = SegmentProof(name, day, ids, plain_hash, sha256(cipher), self.key_id)
        if self.read(proof) != records:
            raise ValueError("Audit persisted read-back mismatch")
        return proof

    def clean_pending(self) -> None:
        """Remove only uncommitted staging files; committed audit files stay forever."""
        folder = self._directory()
        try:
            with os.scandir(folder) as entries:
                for item in entries:
                    if re.fullmatch(r"\.pending-[a-f0-9]{32}", item.name):
                        os.unlink(item.name, dir_fd=folder)
            os.fsync(folder)
        finally:
            os.close(folder)
