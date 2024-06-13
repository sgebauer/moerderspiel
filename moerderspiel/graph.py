from db import Circle

from typing import List

import graphviz
import hashlib
import os


def get_circles_graph_cache_path(circles: List[Circle]) -> str:
    circles_id = circles[0].game.id + '/' + '+'.join([str(c.id) for c in circles])
    circles_hash = hashlib.sha1(circles_id.encode('utf-8')).hexdigest()
    return f"{os.environ['CACHE_DIRECTORY']}/graphs/{circles_hash}.svg"


def generate_circles_graph(circles: List[Circle]) -> None:
    missions = sum([c.missions for c in circles], [])

    dot = graphviz.Digraph()

    for mission in missions:
        dot.node(mission.victim.name)
        dot.edge(mission.initial_owner.name, mission.victim.name, style="dashed")

        if mission.completed:
            dot.edge(mission.killer.name, mission.victim.name, label=mission.completion_reason)

    dot.render(format='svg', outfile=get_circles_graph_cache_path(circles))
