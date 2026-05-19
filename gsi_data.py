from __future__ import annotations

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
        # tournament_id -> {lobby_match_id, dota_matchid, name_map}
        self.tournament_bindings = {}

    def bind_tournament(self, tournament_id: int, lobby_match_id: str, name_map: dict[int, str]):
        with self.lock:
            self.tournament_bindings[tournament_id] = {
                "lobby_match_id": lobby_match_id,
                "dota_matchid": None,
                "name_map": dict(name_map),
            }

    def unbind_tournament(self, tournament_id: int):
        with self.lock:
            self.tournament_bindings.pop(tournament_id, None)

    def _active_tournament_for_dota_match(self, dota_matchid: str) -> int | None:
        for tid, bind in self.tournament_bindings.items():
            if bind.get("dota_matchid") == dota_matchid:
                return tid
        if len(self.tournament_bindings) == 1:
            return next(iter(self.tournament_bindings))
        return None

    def update(self, data: dict):
        with self.lock:
            self.current_match = data
            self.last_update = datetime.utcnow()
            map_data = data.get("map", {}) if isinstance(data.get("map"), dict) else {}
            match_id = data.get("matchid") or map_data.get("matchid", "unknown")
            player_data = data.get("player", {}) if isinstance(data.get("player"), dict) else {}
            hero_data = data.get("hero", {}) if isinstance(data.get("hero"), dict) else {}
            items_data = data.get("items", {}) if isinstance(data.get("items"), dict) else {}

            for tid, bind in self.tournament_bindings.items():
                if bind.get("dota_matchid") in (None, "unknown") and match_id not in ("unknown", None):
                    bind["dota_matchid"] = match_id

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
                    account_id = player_data.get("accountid") or player_data.get("account_id")
                    entry = {
                        "kills": player_data.get("kills", 0),
                        "deaths": player_data.get("deaths", 0),
                        "assists": player_data.get("assists", 0),
                        "last_hits": player_data.get("last_hits", 0),
                        "denies": player_data.get("denies", 0),
                        "networth": player_data.get("net_worth", 0),
                        "team": player_data.get("team_name", "unknown"),
                    }
                    if account_id is not None:
                        entry["account_id"] = account_id
                    self.player_stats[match_id][name] = entry

    def get_current(self) -> dict:
        with self.lock:
            return self.current_match.copy()

    def add_finished(self, matchid: str, data: dict, tournament_id: int | None = None):
        with self.lock:
            payload = dict(data)
            stats = self.player_stats.get(matchid)
            details = self.match_details.get(matchid)
            if stats:
                payload["player_stats"] = stats
            if details:
                payload["match_details"] = details
            self.finished_matches[matchid] = payload
            if tournament_id is not None:
                self.finished_matches[f"tournament:{tournament_id}"] = payload

    def get_finished(self, matchid: str) -> dict | None:
        with self.lock:
            return self.finished_matches.get(matchid)

    def pop_finished(self, matchid: str) -> dict | None:
        with self.lock:
            data = self.finished_matches.pop(matchid, None)
            if not data:
                return None
            stats = self.player_stats.pop(matchid, None)
            details = self.match_details.pop(matchid, None)
            if stats and "player_stats" not in data:
                data["player_stats"] = stats
            if details and "match_details" not in data:
                data["match_details"] = details
            return data

    def pop_finished_for_tournament(self, tournament_id: int, lobby_match_id: str | None = None) -> dict | None:
        with self.lock:
            keys = [
                f"tournament:{tournament_id}",
                str(tournament_id),
            ]
            bind = self.tournament_bindings.get(tournament_id)
            if bind:
                if bind.get("dota_matchid"):
                    keys.append(str(bind["dota_matchid"]))
                if bind.get("lobby_match_id"):
                    keys.append(str(bind["lobby_match_id"]))
            if lobby_match_id:
                keys.append(str(lobby_match_id))

            for key in keys:
                if key in self.finished_matches:
                    data = self.finished_matches.pop(key)
                    dota_id = bind.get("dota_matchid") if bind else None
                    if dota_id:
                        self.player_stats.pop(dota_id, None)
                        self.match_details.pop(dota_id, None)
                    return data

            dota_id = bind.get("dota_matchid") if bind else None
            if dota_id and dota_id in self.player_stats:
                data = {
                    "player_stats": self.player_stats.pop(dota_id, {}),
                    "match_details": self.match_details.pop(dota_id, {}),
                }
                return data
            return None

    def is_match_active(self) -> bool:
        with self.lock:
            state = self.current_match.get("game_state", "")
            return "IN_PROGRESS" in state or "PRE_GAME" in state


gsi_data = GSIData()
