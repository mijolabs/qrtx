import math

from protocol import _imul, splitmix32

_LN2 = 0.6931471805599453

SOLITON_C = 0.1
SOLITON_DELTA = 0.5


def _dlog(x: float) -> float:
    e = 0
    m = x
    while m >= 1.5:
        m /= 2
        e += 1
    while m < 0.75:
        m *= 2
        e -= 1
    z = (m - 1) / (m + 1)
    z2 = z * z
    term = z
    total = 0.0
    for n in range(1, 22, 2):
        total += term / n
        term *= z2
    return e * _LN2 + 2 * total


def _soliton_cdf(k: int) -> list[float]:
    if k == 1:
        return [1.0]
    R = max(1.0, SOLITON_C * _dlog(k / SOLITON_DELTA) * math.sqrt(k))
    spike = min(k, math.ceil(k / R))
    total = 0.0
    cdf = []
    for d in range(1, k + 1):
        rho = 1 / k if d == 1 else 1 / (d * (d - 1))
        tau = 0.0
        if d < spike:
            tau = R / (d * k)
        elif d == spike:
            tau = (R * max(0.0, _dlog(R / SOLITON_DELTA))) / k
        total += rho + tau
        cdf.append(total)
    for i in range(k):
        cdf[i] /= total
    cdf[k - 1] = 1.0
    return cdf


def _to_signed32(v: int) -> int:
    v = v & 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def _frame_seed(session_id: int, seq: int) -> int:
    a = (session_id + 1) & 0xFFFFFFFF
    h = _imul(a, 0x9E3779B1) & 0xFFFFFFFF
    b = (seq + 0x85EBCA6B) & 0xFFFFFFFF
    h = (h ^ b) & 0xFFFFFFFF
    h = _to_signed32(h)
    h_unsigned = h & 0xFFFFFFFF
    shifted = h_unsigned >> 13
    h = _to_signed32(h_unsigned ^ shifted)
    h = _imul(h & 0xFFFFFFFF, 0xC2B2AE35) & 0xFFFFFFFF
    h = _to_signed32(h)
    h_unsigned = h & 0xFFFFFFFF
    shifted = h_unsigned >> 16
    h = _to_signed32(h_unsigned ^ shifted)
    return h & 0xFFFFFFFF


def _frame_indices(k: int, cdf: list[float], session_id: int, seq: int) -> list[int]:
    seed = _frame_seed(session_id, seq)
    rnd = splitmix32(seed)
    u = rnd() * 2**-32
    lo, hi = 0, k - 1
    while lo < hi:
        mid = (lo + hi) >> 1
        if cdf[mid] >= u:
            hi = mid
        else:
            lo = mid + 1
    d = min(k, lo + 1)
    if d > k >> 3:
        scratch = list(range(k))
        out = []
        for i in range(d):
            j = i + (rnd() % (k - i))
            scratch[i], scratch[j] = scratch[j], scratch[i]
            out.append(scratch[i])
        return out
    indices: set[int] = set()
    while len(indices) < d:
        indices.add(rnd() % k)
    return list(indices)


def _xor_bytes(a: bytearray, b: bytearray) -> None:
    for i in range(len(a)):
        a[i] ^= b[i]


class LTEncoder:
    def __init__(self, payload: bytes, block_len: int, session_id: int):
        self.block_len = block_len
        self.session_id = session_id
        self.k = max(1, math.ceil(len(payload) / block_len))
        self._blocks: list[bytearray] = []
        padded_len = math.ceil(block_len / 4) * 4
        for b in range(self.k):
            start = b * block_len
            end = min(start + block_len, len(payload))
            block = bytearray(padded_len)
            block[: end - start] = payload[start:end]
            self._blocks.append(block)
        self._cdf = _soliton_cdf(self.k)

    def encode(self, seq: int) -> bytes:
        idx = _frame_indices(self.k, self._cdf, self.session_id, seq)
        padded_len = len(self._blocks[0])
        out = bytearray(padded_len)
        for b in idx:
            _xor_bytes(out, self._blocks[b])
        return bytes(out[: self.block_len])


class _PendingFrame:
    __slots__ = ("idx", "words")

    def __init__(self, idx: set[int], words: bytearray):
        self.idx = idx
        self.words = words


class LTDecoder:
    def __init__(self, k: int, block_len: int, session_id: int, total_len: int):
        self.k = k
        self.block_len = block_len
        self.session_id = session_id
        self.total_len = total_len
        self._padded = math.ceil(block_len / 4) * 4
        self._cdf = _soliton_cdf(k)
        self._solved: list[bytearray | None] = [None] * k
        self._by_block: dict[int, set[_PendingFrame]] = {}
        self._seen: set[int] = set()
        self.solved_count = 0
        self.frames_new = 0
        self.frames_dup = 0

    @property
    def is_complete(self) -> bool:
        return self.solved_count >= self.k

    def add_frame(self, seq: int, block: bytes) -> None:
        if seq in self._seen:
            self.frames_dup += 1
            return
        self._seen.add(seq)
        self.frames_new += 1
        if self.is_complete:
            return
        idx = set(_frame_indices(self.k, self._cdf, self.session_id, seq))
        words = bytearray(self._padded)
        words[: len(block)] = block[: self.block_len]
        for b in list(idx):
            s = self._solved[b]
            if s is not None:
                _xor_bytes(words, s)
                idx.discard(b)
        if not idx:
            return
        if len(idx) == 1:
            self._resolve(next(iter(idx)), words)
            return
        pf = _PendingFrame(idx, words)
        for b in idx:
            if b not in self._by_block:
                self._by_block[b] = set()
            self._by_block[b].add(pf)

    def _resolve(self, b0: int, w0: bytearray) -> None:
        queue: list[tuple[int, bytearray]] = [(b0, w0)]
        while queue:
            b, w = queue.pop()
            if self._solved[b] is not None:
                continue
            self._solved[b] = w
            self.solved_count += 1
            waiting = self._by_block.pop(b, None)
            if not waiting:
                continue
            for pf in waiting:
                _xor_bytes(pf.words, w)
                pf.idx.discard(b)
                if len(pf.idx) == 1:
                    r = next(iter(pf.idx))
                    by_r = self._by_block.get(r)
                    if by_r:
                        by_r.discard(pf)
                    if self._solved[r] is None:
                        queue.append((r, pf.words))

    def assemble(self) -> bytes | None:
        if not self.is_complete:
            return None
        out = bytearray(self.total_len)
        for b in range(self.k):
            start = b * self.block_len
            length = min(self.block_len, self.total_len - start)
            if length > 0 and self._solved[b] is not None:
                out[start : start + length] = self._solved[b][:length]
        return bytes(out)
