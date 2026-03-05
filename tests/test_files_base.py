from __future__ import annotations

from io import BytesIO

import edgy


class NonSeekableBytesIO(BytesIO):
    def seek(self, offset: int, whence: int = 0) -> int:  # type: ignore[override]
        raise OSError("stream is not seekable")


def test_file_hash_uses_name() -> None:
    file_a = edgy.files.File(name="demo.txt")
    file_b = edgy.files.File(name="demo.txt")

    assert hash(file_a) == hash("demo.txt")
    assert file_a == file_b
    assert len({file_a, file_b}) == 1


def test_file_chunks_support_non_seekable_streams() -> None:
    file = edgy.files.File(file=NonSeekableBytesIO(b"abcdef"), name="demo.bin")

    assert list(file.chunks(chunk_size=2)) == [b"ab", b"cd", b"ef"]


def test_file_open_non_seekable_stream_keeps_working() -> None:
    file = edgy.files.File(file=NonSeekableBytesIO(b"abcdef"), name="demo.bin")

    reopened = file.open()

    assert reopened is file
    assert file.read(3) == b"abc"
