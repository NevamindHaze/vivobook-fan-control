#!/usr/bin/env python3
"""Run: python3 test_fanctl.py"""
import os
import tempfile

from fanctl import read, serve

with tempfile.TemporaryDirectory() as d:
    enable = os.path.join(d, "enable")

    def script(*lines):
        for line, expected in lines:
            yield line
            assert read(enable) == expected, line

    # Each state is checked after its line applied; bad input must change nothing.
    serve(script(("full\n", "0"), ("rm -rf /\n", "0"), ("auto\n", "2"), ("full\n", "0")), enable)
    assert read(enable) == "2"  # input ended while on Full

    # A failure mid-stream must still restore Auto.
    def crash():
        yield "full\n"
        raise RuntimeError

    try:
        serve(crash(), enable)
    except RuntimeError:
        pass
    assert read(enable) == "2"

print("ok")
