import os.path

from moerderspiel.db import Circle, Mission
from moerderspiel.config import CACHE_DIRECTORY
from moerderspiel.util import get_circle_color

from typing import List

import graphviz
import hashlib


def get_circles_graph_cache_path(circles: List[Circle]) -> str:
    circles_id = circles[0].game.id + '/' + '+'.join([str(c.id) for c in circles])
    circles_hash = hashlib.sha1(circles_id.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIRECTORY, 'graphs', f"{circles_hash}.svg")


def generate_circles_graph(circles: List[Circle], show_original_owners: bool = False, show_isolated_players: bool = True) -> str:
    mass_murderers = Mission.mass_murderers_by_game(circles[0].game)
    dot = graphviz.Digraph()
    dot.attr(bgcolor='#00000000')

    for circle in circles:
        color = '#%02x%02x%02x' % get_circle_color(circle)

        for mission in circle.missions:
            styles = []
            if not mission.victim.alive:
                styles.append('dashed')
            if mission.victim in mass_murderers:
                styles.append('bold')

            if show_isolated_players or show_original_owners or mission.completed or mission.victim.completed_missions:
                dot.node(str(mission.victim.id), label=f" {mission.victim.name}\n{mission.victim.group}", style=', '.join(styles))

            if show_original_owners:
                dot.edge(mission.initial_owner.name, mission.victim.name, style="dashed", color=color)

            if mission.completed:
                if not mission.killer:
                    dot.node('Game Master', color='#aaaaaa', fontcolor='#aaaaaa')
                    killer = 'Game Master'
                else:
                    killer = str(mission.killer.id)

                dot.edge(killer, str(mission.victim.id), color=color,
                         label=f" {mission.completion_reason}\n({mission.completion_date.strftime('%Y-%m-%d %H:%M')})")

    path = get_circles_graph_cache_path(circles)
    dot.render(format='svg', outfile=path)
    return path

