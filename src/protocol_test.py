from protocol import FrameHeader, fnv1a, pack_frame, parse_frame, splitmix32


def test_splitmix32_deterministic():
    rnd = splitmix32(12345)
    values = [rnd() for _ in range(5)]
    rnd2 = splitmix32(12345)
    values2 = [rnd2() for _ in range(5)]
    assert values == values2


def test_splitmix32_produces_u32():
    rnd = splitmix32(0)
    for _ in range(100):
        v = rnd()
        assert 0 <= v < 2**32


def test_fnv1a_empty():
    assert fnv1a(b"") == 0x811C9DC5


def test_fnv1a_known():
    h = fnv1a(b"hello")
    assert isinstance(h, int)
    assert 0 <= h < 2**32


def test_fnv1a_deterministic():
    assert fnv1a(b"test data 12345") == fnv1a(b"test data 12345")


def test_pack_parse_roundtrip():
    header = FrameHeader(
        session_id=0x1234,
        seq=42,
        k=100,
        block_len=64,
        total_len=6400,
        payload_fnv=0xDEADBEEF,
    )
    block = bytes(range(64))
    frame = pack_frame(header, block)

    result = parse_frame(frame)
    assert result is not None
    h, b = result
    assert h.session_id == header.session_id
    assert h.seq == header.seq
    assert h.k == header.k
    assert h.block_len == header.block_len
    assert h.total_len == header.total_len
    assert h.payload_fnv == header.payload_fnv
    assert b == block


def test_parse_rejects_bad_magic():
    data = b"\x00\x00" + b"\x00" * 40
    assert parse_frame(data) is None


def test_parse_rejects_short_data():
    assert parse_frame(b"\xd1\x0c" + b"\x00" * 10) is None


def test_parse_rejects_zero_fields():
    header = FrameHeader(
        session_id=1, seq=0, k=0, block_len=10, total_len=100, payload_fnv=0
    )
    block = bytes(10)
    frame = pack_frame(header, block)
    assert parse_frame(frame) is None
