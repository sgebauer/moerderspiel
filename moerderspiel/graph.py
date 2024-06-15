import os.path

from moerderspiel import util
from moerderspiel.db import Circle
from moerderspiel.config import CACHE_DIRECTORY

from typing import List

import graphviz
import hashlib


def get_circles_graph_cache_path(circles: List[Circle]) -> str:
    circles_id = circles[0].game.id + '/' + '+'.join([str(c.id) for c in circles])
    circles_hash = hashlib.sha1(circles_id.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIRECTORY, 'graphs', f"{circles_hash}.svg")


def generate_circles_graph(circles: List[Circle]) -> None:
    dot = graphviz.Digraph()
    colorscheme = util.colorscheme()

    for circle in circles:
        color = '#%02x%02x%02x' % next(colorscheme)

        for mission in circle.missions:
            dot.node(mission.victim.name)
            dot.edge(mission.initial_owner.name, mission.victim.name, style="dashed", color=color)

            if mission.completed:
                dot.edge(mission.killer.name, mission.victim.name, label=mission.completion_reason, color=color)

    dot.render(format='svg', outfile=get_circles_graph_cache_path(circles))
