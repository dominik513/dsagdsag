from datetime import datetime
import threading

class GSIData:
    def __init__(self):
        self.lock = threading.Lock()
        self.current_match = {}
        self.finished_matches = {}
        self.last_update = None
        self.player_stats = {}
        self.match_details = {}

    def update(self, data: dict):
        with self.lock:
            self.current_match = data
            self.last_update = datetime.utcnow()
            match_id = data.get("map", {}).get("matchid", "unknown")
            player_data = data.get("player", {})
            hero_data = data.get("hero", {})
            items_data = data.get("items", {})
            if match_id != "unknown":
                if match_id not in self.match_details:
                    self.match_details[match_id] = {"heroes": {}, "items": {}, "networth": {}}
                if hero_data:
                    player_name = player_data.get("name", "unknown")
                    hero_name = hero_data.get("name", "unknown")
                    if player_name != "unknown":
                        self.match_details[match_id]["heroes"][player_name] = hero_name
                if player_data:
                    pname = player_data.get("name", "unknown")
                    if pname != "unknown":
                        self.match_details[match_id]["items"][pname] = items_data.get("inventory", [])
                        self.match_details[match_id]["networth"][pname] = player_data.get("net_worth", 0)
                if match_id not in self.player_stats:
                    self.player_stats[match_id] = {}
                name = player_data.get("name", "unknown")
                if name != "unknown":
                    self.player_stats[match_id][name] = {
                        "kills": player_data.get("kills", 0),
                        "deaths": player_data.get("deaths", 0),
                        "assists": player_data.get("assists", 0),
                        "last_hits": player_data.get("last_hits", 0),
                        "denies": player_data.get("denies", 0),
                        "team": player_data.get("team_name", "unknown")
                    }

    def get_current(self) -> dict:
        with self.lock:
            return self.current_match.copy()

    def add_finished(self, matchid: str, data: dict):
        with self.lock:
            self.finished_matches[matchid] = data

    def get_finished(self, matchid: str) -> dict | None:
        with self.lock:
            return self.finished_matches.get(matchid)

    def pop_finished(self, matchid: str) -> dict | None:
        with self.lock:
            data = self.finished_matches.pop(matchid, None)
            stats = self.player_stats.pop(matchid, None)
            details = self.match_details.pop(matchid, None)
            if data:
                data["player_stats"] = stats
                data["match_details"] = details
            return data

    def is_match_active(self) -> bool:
        with self.lock:
            state = self.current_match.get("game_state", "")
            return "IN_PROGRESS" in state or "PRE_GAME" in state

gsi_data = GSIData()
