import dataclasses
import struct
from collections.abc import Callable

HEADER_LEN = 20
MAGIC0 = 0xD1
MAGIC1 = 0x0C
_HEADER_FMT = "<2BHIHHII"


@dataclasses.dataclass(frozen=True, slots=True)
class FrameHeader:
    session_id: int
    seq: int
    k: int
    block_len: int
    total_len: int
    payload_fnv: int


def pack_frame(header: FrameHeader, block: bytes) -> bytes:
    buf = bytearray(HEADER_LEN + len(block))
    struct.pack_into(
        _HEADER_FMT,
        buf,
        0,
        MAGIC0,
        MAGIC1,
        header.session_id,
        header.seq,
        header.k,
        header.block_len,
        header.total_len,
        header.payload_fnv,
    )
    buf[HEADER_LEN:] = block
    return bytes(buf)


def parse_frame(data: bytes) -> tuple[FrameHeader, bytes] | None:
    if len(data) <= HEADER_LEN:
        return None
    if data[0] != MAGIC0 or data[1] != MAGIC1:
        return None
    _, _, sid, seq, k, blen, tlen, fnv = struct.unpack_from(_HEADER_FMT, data, 0)
    if k == 0 or blen == 0 or tlen == 0:
        return None
    if len(data) != HEADER_LEN + blen:
        return None
    header = FrameHeader(
        session_id=sid, seq=seq, k=k, block_len=blen, total_len=tlen, payload_fnv=fnv
    )
    return header, data[HEADER_LEN:]


def fnv1a(data: bytes) -> int:
    h = 0x811C9DC5
    for b in data:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def _imul(a: int, b: int) -> int:
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF


def splitmix32(seed: int) -> Callable[[], int]:
    s = seed & 0xFFFFFFFF

    def _next() -> int:
        nonlocal s
        s = (s + 0x9E3779B9) & 0xFFFFFFFF
        t = s ^ (s >> 16)
        t = _imul(t, 0x21F0AAAD) & 0xFFFFFFFF
        t = t ^ (t >> 15)
        t = _imul(t, 0x735A2D97) & 0xFFFFFFFF
        t = t ^ (t >> 15)
        return t

    return _next
