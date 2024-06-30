from typing import Dict, List

from moerderspiel.db import Game, Mission
from moerderspiel.config import CACHE_DIRECTORY, BASE_URL

import os
import os.path
import subprocess
import hashlib

RESOURCE_DIRECTORY = os.path.dirname(__file__)


def generate_mission_sheet(mission: Mission) -> str:
    params = dict(
        gameid=mission.game.id,
        missioncode=mission.code,
        owner=mission.current_owner.name,
        victim=mission.victim.name,
        gameurl=f"{BASE_URL}/{mission.game.id}",
        headline=(mission.game.title if len(mission.game.circles) == 1 else f"{mission.game.title} - {mission.circle.name}")
    )

    params_string = str(dict(sorted(params.items())))
    params_hash = hashlib.sha1(params_string.encode("utf-8")).hexdigest()
    dest = os.path.join(CACHE_DIRECTORY, 'mission-sheets', f"{params_hash}.pdf")

    if not os.path.exists(dest):
        print(f"Generating mission sheet {dest}")
        subprocess.run(os.path.join(RESOURCE_DIRECTORY, 'build-mission-sheet.sh'),
                       env={**os.environ, **params, 'destfile': dest})

    return dest


def generate_mission_sheets(missions: List[Mission]) -> str:
    mission_sheets = []

    for mission in missions:
        mission_sheets.append(generate_mission_sheet(mission))

    mission_hashes = [os.path.basename(p).replace('.pdf', '') for p in mission_sheets]
    game_hash = hashlib.sha1('/'.join(mission_hashes).encode('utf-8')).hexdigest()
    dest = os.path.join(CACHE_DIRECTORY, 'mission-sheets', f"{game_hash}.pdf")

    if not os.path.exists(dest):
        print(f"Generating game mission sheet {dest}")
        subprocess.run(['/usr/bin/pdfunite', *mission_sheets, dest])

    return dest


def generate_game_mission_sheets(game: Game) -> str:
    missions = sorted(Mission.achievable_missions_in_game(game), key=lambda p: p.current_owner.name)
    return generate_mission_sheets(missions)
