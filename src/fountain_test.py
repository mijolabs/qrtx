import math
import os

from fountain import LTDecoder, LTEncoder, _dlog, _frame_indices, _soliton_cdf


def test_dlog_matches_math_log():
    for x in [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 100.0, 1000.0]:
        assert abs(_dlog(x) - math.log(x)) < 1e-12, f"dlog({x}) diverged"


def test_soliton_cdf_monotonic():
    cdf = _soliton_cdf(100)
    assert len(cdf) == 100
    for i in range(1, len(cdf)):
        assert cdf[i] >= cdf[i - 1]
    assert cdf[-1] == 1.0


def test_soliton_cdf_single_block():
    cdf = _soliton_cdf(1)
    assert cdf == [1.0]


def test_soliton_cdf_deterministic():
    assert _soliton_cdf(50) == _soliton_cdf(50)


def test_frame_indices_in_range():
    cdf = _soliton_cdf(100)
    for seq in range(50):
        indices = _frame_indices(100, cdf, 42, seq)
        assert len(indices) > 0
        assert len(indices) == len(set(indices))
        for idx in indices:
            assert 0 <= idx < 100


def test_frame_indices_deterministic():
    cdf = _soliton_cdf(100)
    a = _frame_indices(100, cdf, 42, 7)
    b = _frame_indices(100, cdf, 42, 7)
    assert a == b


def test_encode_decode_roundtrip_small():
    payload = bytes(range(256)) * 2  # 512 bytes
    block_len = 64
    session_id = 1234

    encoder = LTEncoder(payload, block_len, session_id)
    decoder = LTDecoder(encoder.k, block_len, session_id, len(payload))

    seq = 0
    while not decoder.is_complete:
        block = encoder.encode(seq)
        decoder.add_frame(seq, block)
        seq += 1
        assert seq < encoder.k * 5, "decoder failed to complete"

    result = decoder.assemble()
    assert result == payload


def test_encode_decode_roundtrip_medium():
    payload = os.urandom(10000)
    block_len = 200
    session_id = 9999

    encoder = LTEncoder(payload, block_len, session_id)
    decoder = LTDecoder(encoder.k, block_len, session_id, len(payload))

    seq = 0
    while not decoder.is_complete:
        block = encoder.encode(seq)
        decoder.add_frame(seq, block)
        seq += 1
        assert seq < encoder.k * 5

    result = decoder.assemble()
    assert result == payload


def test_encode_decode_single_block():
    payload = b"short"
    block_len = 64
    session_id = 1

    encoder = LTEncoder(payload, block_len, session_id)
    assert encoder.k == 1
    decoder = LTDecoder(1, block_len, session_id, len(payload))

    block = encoder.encode(0)
    decoder.add_frame(0, block)
    assert decoder.is_complete
    assert decoder.assemble() == payload


def test_duplicate_frames_counted():
    payload = os.urandom(500)
    block_len = 64
    session_id = 42

    encoder = LTEncoder(payload, block_len, session_id)
    decoder = LTDecoder(encoder.k, block_len, session_id, len(payload))

    block = encoder.encode(0)
    decoder.add_frame(0, block)
    decoder.add_frame(0, block)

    assert decoder.frames_new == 1
    assert decoder.frames_dup == 1
