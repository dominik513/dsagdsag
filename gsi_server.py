from flask import Flask, request, jsonify, send_from_directory
from gsi_data import gsi_data
import logging
import os

log = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "ok", "service": "Dota 2 Tournament Bot"})

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "match_active": gsi_data.is_match_active(),
        "current_score": f"{gsi_data.current_match.get('radiant_score', 0)} - {gsi_data.current_match.get('dire_score', 0)}"
    })

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/gsi', methods=['POST'])
def receive_gsi():
    try:
        payload = request.json
        if not payload:
            return jsonify({"status": "empty"})
        # Оригинальный формат Dota GSI содержит вложенные секции (map/player/hero/items/...).
        # Ниже формируем "плоскую" структуру + сохраняем оригинальные секции, чтобы:
        # - tournament.py мог читать привычные ключи (radiant_score, game_state, win_team, ...)
        # - gsi_data.py мог собирать расширенную статистику по игрокам/героям/предметам
        map_data = payload.get("map", {}) if isinstance(payload, dict) else {}
        player_data = payload.get("player", {}) if isinstance(payload, dict) else {}
        hero_data = payload.get("hero", {}) if isinstance(payload, dict) else {}
        items_data = payload.get("items", {}) if isinstance(payload, dict) else {}
        match_info = {
            "matchid": map_data.get("matchid", "unknown"),
            "radiant_score": map_data.get("radiant_score", 0),
            "dire_score": map_data.get("dire_score", 0),
            "clock_time": map_data.get("clock_time", 0),
            "game_state": map_data.get("game_state", ""),
            "win_team": map_data.get("win_team", ""),
            "player_name": player_data.get("name", "unknown"),
            "player_kills": player_data.get("kills", 0),
            "player_deaths": player_data.get("deaths", 0),
            "player_assists": player_data.get("assists", 0),
            "player_team": player_data.get("team_name", ""),
            "last_hits": player_data.get("last_hits", 0),
            "denies": player_data.get("denies", 0),
            "net_worth": player_data.get("net_worth", 0),
            # оригинальные секции (для gsi_data.py и других потребителей)
            "map": map_data,
            "player": player_data,
        }
        if hero_data:
            match_info["hero"] = hero_data
        if items_data:
            match_info["items"] = items_data
        if match_info["win_team"] == "radiant":
            match_info["radiant_win"] = True
        elif match_info["win_team"] == "dire":
            match_info["radiant_win"] = False
        gsi_data.update(match_info)
        if match_info["game_state"] == "DOTA_GAMERULES_STATE_POST_GAME":
            match_id = match_info["matchid"]
            tid = None
            with gsi_data.lock:
                if len(gsi_data.tournament_bindings) == 1:
                    tid = next(iter(gsi_data.tournament_bindings))
            gsi_data.add_finished(match_id, match_info.copy(), tournament_id=tid)
            log.info(f"Матч {match_id} завершён (tournament={tid})!")
        return jsonify({"status": "ok"})
    except Exception as e:
        log.error(f"Ошибка: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/overlay')
def overlay():
    return send_from_directory('static', 'overlay.html')

@app.route('/api/match')
def api_match():
    cur = gsi_data.get_current()
    if not cur or not cur.get("game_state"):
        return jsonify({"active": False})
    is_active = "IN_PROGRESS" in cur.get("game_state", "") or "POST_GAME" in cur.get("game_state", "")
    return jsonify({
        "active": is_active,
        "radiant_score": cur.get("radiant_score", 0),
        "dire_score": cur.get("dire_score", 0),
        "clock_time": cur.get("clock_time", 0),
        "game_state": "in_progress" if "IN_PROGRESS" in cur.get("game_state", "") else "finished" if "POST_GAME" in cur.get("game_state", "") else "waiting",
        "radiant_players": [{"name": cur.get("player_name", "?"), "hero": cur.get("hero", {}).get("name", ""), "networth": cur.get("net_worth", 0)}],
        "dire_players": []
    })
