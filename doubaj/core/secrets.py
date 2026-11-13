"""Secure storage of API keys.

On Windows the keys are encrypted with DPAPI (CryptProtectData), which ties them to the
current Windows user account: copying the data folder to another PC or user will NOT
reveal the keys (they must be re-entered). On other systems (development only) a
machine-bound XOR obfuscation is used and a warning is reported.
Keys are never written to logs.
"""
from __future__ import annotations

import base64
import ctypes
import hashlib
import platform
import sys
import uuid

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    from ctypes import wintypes

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32
    _ENTROPY = b"DOUBAJ-AI-v1"

    def _blob(data: bytes) -> _DATA_BLOB:
        buf = ctypes.create_string_buffer(data, len(data))
        return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    def _protect(data: bytes) -> bytes:
        out = _DATA_BLOB()
        ent = _blob(_ENTROPY)
        if not _crypt32.CryptProtectData(ctypes.byref(_blob(data)), "DOUBAJ", ctypes.byref(ent),
                                         None, None, 0x01, ctypes.byref(out)):
            raise OSError("CryptProtectData failed")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            _kernel32.LocalFree(out.pbData)

    def _unprotect(data: bytes) -> bytes:
        out = _DATA_BLOB()
        ent = _blob(_ENTROPY)
        if not _crypt32.CryptUnprotectData(ctypes.byref(_blob(data)), None, ctypes.byref(ent),
                                           None, None, 0x01, ctypes.byref(out)):
            raise OSError("CryptUnprotectData failed")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            _kernel32.LocalFree(out.pbData)
else:
    def _key() -> bytes:
        seed = f"{platform.node()}-{uuid.getnode()}-DOUBAJ".encode()
        return hashlib.sha256(seed).digest()

    def _protect(data: bytes) -> bytes:
        k = _key()
        return bytes(b ^ k[i % len(k)] for i, b in enumerate(data))

    _unprotect = _protect


def encrypt(value: str) -> str:
    if not value:
        return ""
    return base64.b64encode(_protect(value.encode("utf-8"))).decode("ascii")


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _unprotect(base64.b64decode(token)).decode("utf-8")
    except Exception:
        return ""  # key cannot be decrypted (other PC / user): ask user again


def mask(value: str) -> str:
    """Display-safe version of a key: never show it fully."""
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return value[:4] + "•" * 8 + value[-4:]


SECURE_BACKEND = "Windows DPAPI" if IS_WINDOWS else "obfuscation (dev only)"
