import colorsys
import math
from typing import Tuple, Generator


def colorscheme(start_hue: float = 0.86) -> Generator[Tuple[int, int, int], None, None]:
    phi = 1.0 / ((1.0 + math.sqrt(5)) / 2.0)
    h = start_hue
    s = 1.0
    v = 1.0
    c = 0

    while True:
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        yield int(r * 255), int(g * 255), int(b * 255)
        h = (h + phi) % 1.0
        c += 1
        if c % 3 == 0:
            v = (v + phi) % 1.0
