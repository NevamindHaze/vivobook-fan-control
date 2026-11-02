#!/usr/bin/env python3
"""Run: python3 test_fanctl.py"""
import os
import tempfile

from fanctl import average_mhz, cpu_percent, cpu_times, read, serve

# Parsers for the graphs: 100 of 400 new jiffies busy-free is 75% load; iowait counts as idle.
assert cpu_times("cpu  10 0 10 70 10 0 0 0 0 0\ncpu0 1 1 1 1 1") == (100, 80)
assert cpu_percent((100, 80), (500, 180)) == 75
assert cpu_percent((100, 80), (100, 80)) == 0.0  # no time passed must not divide by zero
assert average_mhz("cpu MHz\t\t: 1000.0\nother: 5\ncpu MHz\t\t: 3000.0\n") == 2000
assert average_mhz("") == 0.0

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
