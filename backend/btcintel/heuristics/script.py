"""Script helpers shared by detectors."""

from __future__ import annotations

from btcintel.chain.models import Tx


def op_return_payloads(tx: Tx) -> list[bytes]:
    """Concatenated data pushes of each OP_RETURN output (malformed scripts yield partial data)."""
    payloads = []
    for out in tx.vout:
        if out.script_type != "op_return":
            continue
        try:
            script = bytes.fromhex(out.script_hex)
        except ValueError:
            continue
        if not script or script[0] != 0x6A:
            continue
        data = bytearray()
        i = 1
        while i < len(script):
            op = script[i]
            i += 1
            if 0x01 <= op <= 0x4B:
                n = op
            elif op == 0x4C:
                if i >= len(script):
                    break
                n = script[i]
                i += 1
            elif op == 0x4D:
                if i + 2 > len(script):
                    break
                n = int.from_bytes(script[i : i + 2], "little")
                i += 2
            else:
                continue
            data += script[i : i + n]
            i += n
        payloads.append(bytes(data))
    return payloads


def is_printable_ascii(data: bytes) -> bool:
    return bool(data) and all(0x20 <= b < 0x7F for b in data)
