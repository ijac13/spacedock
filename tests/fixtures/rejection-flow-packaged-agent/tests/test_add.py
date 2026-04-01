# ABOUTME: Tests for the add function in math_ops.py.
# ABOUTME: Verifies that add(a, b) returns the correct sum.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from math_ops import add


def test_add_positive():
    assert add(2, 3) == 5, f"Expected 5, got {add(2, 3)}"


def test_add_negative_and_positive():
    assert add(-1, 1) == 0, f"Expected 0, got {add(-1, 1)}"


def test_add_zeros():
    assert add(0, 0) == 0, f"Expected 0, got {add(0, 0)}"


if __name__ == "__main__":
    failures = 0
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                func()
                print(f"  PASS: {name}")
            except AssertionError as e:
                print(f"  FAIL: {name} — {e}")
                failures += 1
    sys.exit(1 if failures else 0)
