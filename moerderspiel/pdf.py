from moerderspiel.db import Game, Mission
from moerderspiel.config import CACHE_DIRECTORY, BASE_URL

import os
import subprocess
import hashlib


def get_mission_sheet_cache_path(mission: Mission) -> str:
    mission_hash = hashlib.sha1(
        f"{mission.game.id}/{mission.circle.id}/{mission.victim.id}".encode('utf-8')).hexdigest()
    return f"{CACHE_DIRECTORY}/mission-sheets/{mission_hash}.pdf"


def get_game_mission_sheet_cache_path(game: Game) -> str:
    game_hash = hashlib.sha1(game.id.encode('utf-8')).hexdigest()
    return f"{CACHE_DIRECTORY}/mission-sheets/{game_hash}.pdf"


def generate_mission_sheet(mission: Mission) -> None:
    env = os.environ
    env['destfile'] = get_mission_sheet_cache_path(mission)
    env['gameid'] = mission.game.id
    env['missioncode'] = mission.code
    env['owner'] = mission.current_owner.name
    env['victim'] = mission.victim.name
    env['gameurl'] = f"{BASE_URL}/{mission.game.id}"

    if len(mission.game.circles) == 1:
        env['headline'] = mission.game.name
    else:
        env['headline'] = f"{mission.game.name} - {mission.circle.name}"

    subprocess.run('./resources/build-mission-sheet.sh')


def generate_game_mission_sheet(game: Game) -> None:
    mission_sheets = []

    for mission in Mission.achievable_missions_in_game(game):
        generate_mission_sheet(mission)
        mission_sheets.append(get_mission_sheet_cache_path(mission))

    subprocess.run(['/usr/bin/pdfunite', *mission_sheets, get_game_mission_sheet_cache_path(game)])
