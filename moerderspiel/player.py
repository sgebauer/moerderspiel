from moerderspiel import notification, pdf
from moerderspiel.db import GameState, Game, Circle, Player, Mission, NotificationAddressType, NotificationAddress
from moerderspiel.game import GameError

class PlayerService:
    def __init__(self, player: Player):
        self.player = player

    def remove_player_from_circle(self, circle: Circle) -> Circle:
        mission = Mission.by_victim_in_circle(self.player, circle)
        if mission:
            mission.delete()

    def add_player_to_circle(self, circle: Circle):
        if not Mission.by_victim_in_circle(self.player, circle):
            self.player.game.add(Mission(circle=circle, victim=self.player))

    def get_current_missions(self):
        return sorted(Mission.achievable_missions_by_current_owner(self.player), key=lambda m: m.circle_id)