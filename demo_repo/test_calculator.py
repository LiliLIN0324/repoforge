"""Tests for calculator — add() currently fails on purpose."""

from calculator import add, multiply


def test_add():
    assert add(2, 3) == 5


def test_add_negative():
    assert add(-1, 1) == 0


def test_multiply():
    assert multiply(3, 4) == 12
