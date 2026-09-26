"""Local validation of Bitcoin mainnet addresses, txids and search queries.

No network access: base58check (P2PKH/P2SH) and bech32/bech32m (BIP173/BIP350) checksums.
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal

AddressType = Literal["p2pkh", "p2sh", "v0_p2wpkh", "v0_p2wsh", "v1_p2tr", "witness_unknown"]
QueryKind = Literal["address", "txid", "outpoint", "text"]

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BECH32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32M_CONST = 0x2BC830A3
_TXID_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _b58decode_check(s: str) -> bytes | None:
    n = 0
    for c in s:
        i = _B58.find(c)
        if i < 0:
            return None
        n = n * 58 + i
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    raw = b"\x00" * (len(s) - len(s.lstrip("1"))) + body
    if len(raw) < 5:
        return None
    payload, checksum = raw[:-4], raw[-4:]
    if hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] != checksum:
        return None
    return payload


def _polymod(values: list[int]) -> int:
    gen = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    chk = 1
    for v in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            if (top >> i) & 1:
                chk ^= gen[i]
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _convertbits(data: list[int], frombits: int, tobits: int) -> list[int] | None:
    """Regroup bits without padding (decoding direction); None if padding is invalid."""
    acc = bits = 0
    ret: list[int] = []
    maxv = (1 << tobits) - 1
    for value in data:
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return None
    return ret


def _segwit_decode(addr: str) -> tuple[int, bytes] | None:
    if addr.lower() != addr and addr.upper() != addr:
        return None
    addr = addr.lower()
    pos = addr.rfind("1")
    if addr[:pos] != "bc" or pos + 7 > len(addr) or len(addr) > 90:
        return None
    data = [_BECH32.find(c) for c in addr[pos + 1 :]]
    if any(d < 0 for d in data):
        return None
    const = _polymod(_hrp_expand("bc") + data)
    if const not in (1, _BECH32M_CONST) or not data[:-6]:
        return None
    witver, prog5 = data[0], data[1:-6]
    prog = _convertbits(prog5, 5, 8)
    if prog is None or not 2 <= len(prog) <= 40 or witver > 16:
        return None
    if witver == 0 and (len(prog) not in (20, 32) or const != 1):
        return None
    if witver != 0 and const != _BECH32M_CONST:
        return None
    return witver, bytes(prog)


def address_type(addr: str) -> AddressType | None:
    """Return the script type of a valid mainnet address, or None if invalid."""
    if not addr or not addr.isascii():
        return None
    if addr[:3].lower() == "bc1":
        decoded = _segwit_decode(addr)
        if decoded is None:
            return None
        witver, prog = decoded
        if witver == 0:
            return "v0_p2wpkh" if len(prog) == 20 else "v0_p2wsh"
        if witver == 1 and len(prog) == 32:
            return "v1_p2tr"
        return "witness_unknown"
    if addr[0] in "13" and 25 <= len(addr) <= 35:
        payload = _b58decode_check(addr)
        if payload is None or len(payload) != 21:
            return None
        return {0x00: "p2pkh", 0x05: "p2sh"}.get(payload[0])  # type: ignore[return-value]
    return None


def is_address(s: str) -> bool:
    return address_type(s) is not None


def normalize_address(addr: str) -> str:
    """Bech32 addresses are case-insensitive; store them lowercase."""
    return addr.lower() if addr[:3].lower() == "bc1" else addr


def is_txid(s: str) -> bool:
    return bool(_TXID_RE.match(s))


def classify_query(q: str) -> tuple[QueryKind, str]:
    """Classify a search string and return it normalized."""
    q = q.strip()
    if is_txid(q):
        return "txid", q.lower()
    txid, sep, vout = q.partition(":")
    if sep and is_txid(txid) and vout.isdigit():
        return "outpoint", f"{txid.lower()}:{int(vout)}"
    if is_address(q):
        return "address", normalize_address(q)
    return "text", q
