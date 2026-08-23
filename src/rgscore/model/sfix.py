from functools import cache, reduce

from bitstring import BitArray, Bits


@cache
def __2pow(n) -> float | int:
    return pow(2, n)


def U(en: int, bit_arrays: list[Bits]) -> float | int:
    return reduce(lambda acc, v: acc + v, bit_arrays, BitArray(0)).uint / __2pow(en)


def S(en: int, bit_arrays: list[Bits]) -> float | int:
    return reduce(lambda acc, v: acc + v, bit_arrays, BitArray(0)).int / __2pow(en)
