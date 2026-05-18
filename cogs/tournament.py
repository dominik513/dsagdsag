from __future__ import annotations

import asyncio
import json
import random
import discord
from discord.ext import commands
from database import models
from utils.lobby_generator import generate_lobby
from utils.helpers import (
    create_gather_embed, create_teams_embed,
    create_live_match_embed, create_result_embed, create_history_embed,
    create_void_embed, create_match_log_embed,
    PositionButtons, SoloButtons,
)
from utils.match_integrity import analyze_match
from config import (
    REGISTRATION_CHANNEL_ID, ADMIN_CHANNEL_ID, DEFAULT_GATHER_TIMEOUT,
    WINNER_POINTS, LOSER_POINTS, GUILD_ID, MATCH_LOG_CHANNEL_ID,
    INTEGRITY_MIN_MAPPED_PLAYERS, INTEGRITY_MIN_DEATHS_5X5, INTEGRITY_MIN_DEATHS_1X1,
    INTEGRITY_MAX_KDA_FEED, INTEGRITY_BLOWOUT_SCORE_DIFF, INTEGRITY_BLOWOUT_MAX_MINUTES,
    MVP_BONUS_POINTS, STREAK_BONUS_PER_WIN, STREAK_BONUS_MAX, FEED_PENALTY_POINTS,
)

HEROES_LIST = [
    "Abaddon", "Alchemist", "Ancient Apparition", "Anti-Mage", "Arc Warden", "Axe",
    "Bane", "Batrider", "Beastmaster", "Bloodseeker", "Bounty Hunter", "Brewmaster",
    "Bristleback", "Broodmother", "Centaur Warrunner", "Chaos Knight", "Chen", "Clinkz",
    "Clockwerk", "Crystal Maiden", "Dark Seer", "Dark Willow", "Dawnbreaker", "Dazzle",
    "Death Prophet", "Disruptor", "Doom", "Dragon Knight", "Drow Ranger", "Earth Spirit",
    "Earthshaker", "Elder Titan", "Ember Spirit", "Enchantress", "Enigma", "Faceless Void",
    "Grimstroke", "Gyrocopter", "Hoodwink", "Huskar", "Invoker", "Io", "Jakiro",
    "Juggernaut", "Keeper of the Light", "Kunkka", "Legion Commander", "Leshrac", "Lich",
    "Lifestealer", "Lina", "Lion", "Lone Druid", "Luna", "Lycan", "Magnus", "Marci",
    "Mars", "Medusa", "Meepo", "Mirana", "Monkey King", "Morphling", "Muerta",
    "Naga Siren", "Nature's Prophet", "Necrophos", "Night Stalker", "Nyx Assassin",
    "Ogre Magi", "Omniknight", "Oracle", "Outworld Destroyer", "Pangolier", "Phantom Assassin",
    "Phantom Lancer", "Phoenix", "Primal Beast", "Puck", "Pudge", "Pugna", "Queen of Pain",
    "Razor", "Riki", "Rubick", "Sand King", "Shadow Demon", "Shadow Fiend", "Shadow Shaman",
    "Silencer", "Skywrath Mage", "Slardar", "Slark", "Snapfire", "Sniper", "Spectre",
    "Spirit Breaker", "Storm Spirit", "Sven", "Techies", "Templar Assassin", "Terrorblade",
    "Tidehunter", "Timbersaw", "Tinker", "Tiny", "Treant Protector", "Troll Warlord",
    "Tusk", "Underlord", "Undying", "Ursa", "Vengeful Spirit", "Venomancer", "Viper",
    "Visage", "Void Spirit", "Warlock", "Weaver", "Windranger", "Winter Wyvern",
    "Witch Doctor", "Wraith King", "Zeus"
]

DRAFT_PHASES = ["ban_r", "ban_d", "ban_r2", "ban_d2", "pick_r", "pick_d", "pick_d2", "pick_r2", "pick_r3", "pick_d3", "pick_d4", "pick_r4", "pick_r5", "pick_d5"]

class CaptainDraft:
    def __init__(self, cog, tid, team_r, team_d):
        self.cog = cog
        self.tid = tid
        self.captain_r = team_r[0]
        self.captain_d = team_d[0]
        self.players_r = team_r
        self.players_d = team_d
        self.bans = []
        self.picks_r = []
        self.picks_d = []
        self.phase = DRAFT_PHASES[0]
        self.hero_pool = HEROES_LIST.copy()
        self.message = None
        self.phase_idx = 0

class DraftView(discord.ui.View):
    def __init__(self, draft: CaptainDraft):
        super().__init__(timeout=600)
        self.draft = draft
        options = [discord.SelectOption(label=h[:25], value=h) for h in draft.hero_pool[:25]]
        self.select_menu = discord.ui.Select(placeholder="Выберите героя...", options=options)
        self.select_menu.callback = self.select_callback
        self.add_item(self.select_menu)

    async def select_callback(self, interaction):
        hero = self.select_menu.values[0]
        draft = self.draft
        if "r" in draft.phase:
            captain = draft.captain_r
        else:
            captain = draft.captain_d
        if interaction.user.id != captain:
            return await interaction.response.send_message("<:no:1503121885674868938> Только капитан может выбирать!", ephemeral=True)
        if hero not in draft.hero_pool:
            return await interaction.response.send_message("<:no:1503121885674868938> Герой недоступен!", ephemeral=True)
        draft.hero_pool.remove(hero)
        if "ban" in draft.phase:
            draft.bans.append(hero)
            msg = f"🚫 **{hero}** забанен!"
        else:
            if "r" in draft.phase:
                draft.picks_r.append(hero)
            else:
                draft.picks_d.append(hero)
            msg = f"<:yes:1503121926128664766> **{hero}** выбран!"
        await interaction.response.send_message(msg, ephemeral=True)
        draft.phase_idx += 1
        if draft.phase_idx >= len(DRAFT_PHASES):
            await draft.message.edit(view=None)
            channel = draft.cog.bot.get_channel(REGISTRATION_CHANNEL_ID)
            if channel:
                embed = discord.Embed(title=f"⚔️ Драфт #{draft.tid} завершён", color=0x2c2f33)
                embed.add_field(name="☀️ Свет", value=", ".join(draft.picks_r) if draft.picks_r else "—", inline=False)
                embed.add_field(name="🌑 Тьма", value=", ".join(draft.picks_d) if draft.picks_d else "—", inline=False)
                embed.add_field(name="🚫 Баны", value=", ".join(draft.bans) if draft.bans else "—", inline=False)
                embed.set_footer(text="Создайте лобби и выберите героев согласно драфту!")
                await channel.send(embed=embed)
            draft.cog._save_draft_picks(draft.tid, draft.picks_r, draft.picks_d)
            return
        draft.phase = DRAFT_PHASES[draft.phase_idx]
        new_options = [discord.SelectOption(label=h[:25], value=h) for h in draft.hero_pool[:25]]
        self.select_menu.options = new_options
        if "r" in draft.phase:
            captain_user = draft.cog.bot.get_user(draft.captain_r)
            turn = f"☀️ {captain_user.mention if captain_user else 'Свет'}"
        else:
            captain_user = draft.cog.bot.get_user(draft.captain_d)
            turn = f"🌑 {captain_user.mention if captain_user else 'Тьма'}"
        action = "Бан" if "ban" in draft.phase else "Пик"
        embed = discord.Embed(
            title=f"🎯 Драфт #{draft.tid}",
            description=f"**{action}** — ход: {turn}",
            color=0x2c2f33
        )
        embed.add_field(name="☀️ Свет", value=", ".join(draft.picks_r) if draft.picks_r else "—", inline=True)
        embed.add_field(name="🌑 Тьма", value=", ".join(draft.picks_d) if draft.picks_d else "—", inline=True)
        embed.add_field(name="🚫 Баны", value=", ".join(draft.bans) if draft.bans else "—", inline=False)
        try:
            await draft.message.edit(embed=embed, view=self)
        except:
            pass

class BetModal(discord.ui.Modal):
    def __init__(self, cog, tid):
        super().__init__(title="Ставка на матч")
        self.cog = cog
        self.tid = tid
        self.add_item(discord.ui.InputText(label="Сумма (мин 10)", placeholder="100"))
        self.add_item(discord.ui.InputText(label="Команда (Свет/Тьма)", placeholder="Свет"))

    async def callback(self, interaction):
        try:
            amount = int(self.children[0].value)
        except:
            return await interaction.response.send_message("<:no:1503121885674868938> Неверная сумма!", ephemeral=True)
        team_raw = self.children[1].value.lower()
        team = "radiant" if team_raw in ("свет", "radiant") else "dire" if team_raw in ("тьма", "dire") else None
        if not team:
            return await interaction.response.send_message("<:no:1503121885674868938> Укажите 'Свет' или 'Тьма'!", ephemeral=True)
        if amount < 10:
            return await interaction.response.send_message("<:no:1503121885674868938> Минимум 10!", ephemeral=True)
        player = models.get_player(interaction.user.id)
        if not player or player["points"] < amount:
            return await interaction.response.send_message("<:no:1503121885674868938> Недостаточно очков!", ephemeral=True)
        md = self.cog.active_matches.get(self.tid)
        if md:
            if interaction.user.id in md["radiant"] + md["dire"]:
                return await interaction.response.send_message("<:no:1503121885674868938> Участники матча не могут ставить!", ephemeral=True)
        if self.tid not in self.cog.bets:
            self.cog.bets[self.tid] = {}
        if interaction.user.id in self.cog.bets[self.tid]:
            return await interaction.response.send_message("<:no:1503121885674868938> Ставка уже сделана!", ephemeral=True)
        self.cog.bets[self.tid][interaction.user.id] = {"team": team, "amount": amount}
        # ставка — не матч, статистику wins/losses не трогаем
        models.add_points(interaction.user.id, -amount, count_match=False)
        await interaction.response.send_message(f"<:yes:1503121926128664766> {amount} на {'☀️ Свет' if team == 'radiant' else '🌑 Тьму'}!", ephemeral=True)

class BetView(discord.ui.View):
    def __init__(self, cog, tid):
        super().__init__(timeout=None)
        self.cog = cog
        self.tid = tid
    @discord.ui.button(label="Ставка", style=discord.ButtonStyle.grey, emoji="💰")
    async def bet_btn(self, button, interaction):
        md = self.cog.active_matches.get(self.tid)
        if md and md["game_state"] != "waiting":
            return await interaction.response.send_message("<:no:1503121885674868938> Ставки закрыты!", ephemeral=True)
        await interaction.response.send_modal(BetModal(self.cog, self.tid))

class Tournament(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_gather = {}
        self.active_matches = {}
        self.bets = {}
        self.bets_messages = {}
        self.auto_mode = True
        self.auto_task = None
        self.next_mode = "5x5"
        self.match_counter = {"5x5": 0, "1x1": 0}

    def _save_draft_picks(self, display_id: int, picks_r: list, picks_d: list):
        for tid, md in self.active_matches.items():
            if md.get("display_id") == display_id:
                md["draft_picks"] = picks_r + picks_d
                break

    def _persist_match_logs(self, tid: int, md: dict, stats_by_uid: dict, integrity_issues=None):
        rows = []
        issue_by_uid = {}
        if integrity_issues:
            for issue in integrity_issues:
                if issue.player_key.isdigit():
                    issue_by_uid[int(issue.player_key)] = issue.code
        for uid in md["radiant"] + md["dire"]:
            st = stats_by_uid.get(uid, {})
            rows.append({
                "discord_id": uid,
                "dota_name": models.get_player_dota_name(uid),
                "team": "radiant" if uid in md["radiant"] else "dire",
                "kills": st.get("kills", 0),
                "deaths": st.get("deaths", 0),
                "assists": st.get("assists", 0),
                "last_hits": st.get("last_hits", 0),
                "denies": st.get("denies", 0),
                "networth": st.get("net_worth", st.get("networth", 0)),
                "hero": st.get("hero"),
                "flags": issue_by_uid.get(uid),
            })
        if rows:
            models.save_match_player_logs(tid, rows)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.auto_task is None:
            self.auto_mode = True
            self.auto_task = asyncio.create_task(self._auto_loop())

    async def _auto_loop(self):
        await asyncio.sleep(5)
        while self.auto_mode:
            mode = self.next_mode
            await self._create_gather(mode)
            await self._wait_for_match_end()
            self.next_mode = "1x1" if mode == "5x5" else "5x5"
            await asyncio.sleep(60)

    async def _wait_for_match_end(self):
        for _ in range(360):
            if not self.active_matches:
                return
            await asyncio.sleep(10)

    async def _create_gather(self, mode):
        self.match_counter[mode] += 1
        display_id = self.match_counter[mode]
        match_id, lobby_name, password = generate_lobby()
        tournament_id = models.create_tournament(match_id, lobby_name, password, 0)
        gather = {"players": {}, "mode": mode, "timeout": DEFAULT_GATHER_TIMEOUT, "message": None, "lobby_name": lobby_name, "password": password, "match_id": match_id, "finalized": False, "display_id": display_id}
        self.active_gather[tournament_id] = gather
        view = PositionButtons(self) if mode == "5x5" else SoloButtons(self)
        channel = self.bot.get_channel(REGISTRATION_CHANNEL_ID)
        if not channel:
            return
        embed = create_gather_embed(DEFAULT_GATHER_TIMEOUT, mode, {})
        message = await channel.send(embed=embed, view=view)
        gather["message"] = message
        for _ in range(DEFAULT_GATHER_TIMEOUT):
            if tournament_id not in self.active_gather or self.active_gather[tournament_id].get("finalized"):
                return
            gather["timeout"] -= 1
            if gather["timeout"] <= 0:
                gather["timeout"] = 0
                await self._update_gather(tournament_id)
                break
            await self._update_gather(tournament_id)
            await asyncio.sleep(1)
        if tournament_id in self.active_gather and not self.active_gather[tournament_id].get("finalized"):
            self.active_gather[tournament_id]["finalized"] = True
            await self.finalize_gather(tournament_id)

    async def register_player(self, interaction, position=None):
        active = models.get_active_tournament()
        if not active:
            return await interaction.response.send_message("Нет сбора!", ephemeral=True)
        g = self.active_gather.get(active["id"])
        if not g:
            return await interaction.response.send_message("Сбор завершён!", ephemeral=True)
        uid = interaction.user.id
        if uid in g["players"]:
            return await interaction.response.send_message("<:no:1503121885674868938> Уже в сборе!", ephemeral=True)
        if g["mode"] == "1x1":
            position = 2
        else:
            count = sum(1 for p in g["players"].values() if p == position)
            if count >= 2:
                return await interaction.response.send_message("<:no:1503121885674868938> Эта роль уже занята!", ephemeral=True)
        g["players"][uid] = position
        models.get_or_create_player(uid, interaction.user.name)
        await self._update_gather(active["id"])
        mx = 10 if g["mode"] == "5x5" else 2
        await interaction.response.defer()
        if len(g["players"]) >= mx:
            g["finalized"] = True
            await self.finalize_gather(active["id"])

    async def leave_player(self, interaction):
        active = models.get_active_tournament()
        if not active:
            return await interaction.response.send_message("<:no:1503121885674868938> Нет сбора!", ephemeral=True)
        g = self.active_gather.get(active["id"])
        if not g:
            return await interaction.response.send_message("<:no:1503121885674868938> Сбор завершён!", ephemeral=True)
        if interaction.user.id not in g["players"]:
            return await interaction.response.send_message("<:no:1503121885674868938> Вы не в сборе!", ephemeral=True)
        del g["players"][interaction.user.id]
        await self._update_gather(active["id"])
        await interaction.response.defer()

    async def _update_gather(self, tid):
        g = self.active_gather.get(tid)
        if g and g["message"] and not g.get("finalized"):
            try:
                await g["message"].edit(embed=create_gather_embed(max(0, g["timeout"]), g["mode"], g["players"]))
            except:
                pass

    async def finalize_gather(self, tid):
        g = self.active_gather.pop(tid, None)
        if not g:
            return
        players, mode = g["players"], g["mode"]
        display_id = g["display_id"]
        channel = self.bot.get_channel(REGISTRATION_CHANNEL_ID)
        mx = 10 if mode == "5x5" else 2
        if len(players) < mx:
            if g["message"]:
                try:
                    await g["message"].delete()
                except:
                    pass
            return models.cancel_tournament(tid)
        ids = list(players.keys())
        if mode == "5x5":
            ids = self._balance_teams(ids)
        else:
            random.shuffle(ids)
        if mode == "1x1":
            r_team, d_team = [ids[0]], [ids[1]]
            pos_r, pos_d = {2: ids[0]}, {2: ids[1]}
        else:
            r_team, d_team = ids[:5], ids[5:10]
            def assign(team):
                by_pos = {1: [], 2: [], 3: [], 4: [], 5: []}
                for u in team:
                    pos = players[u]
                    by_pos[pos].append(u)
                result = {}
                for pos in range(1, 6):
                    candidates = by_pos.get(pos, [])
                    if candidates:
                        result[pos] = candidates[0]
                unassigned = [u for u in team if u not in result.values()]
                free = [p for p in range(1, 6) if p not in result]
                for u in unassigned:
                    if free:
                        result[free.pop(0)] = u
                return {p: u for p, u in result.items()}
            pos_r = assign(r_team)
            pos_d = assign(d_team)

        models.set_tournament_teams(tid, list(pos_r.values()), list(pos_d.values()))
        for p, u in pos_r.items():
            models.add_tournament_player(tid, u, "radiant", p)
        for p, u in pos_d.items():
            models.add_tournament_player(tid, u, "dire", p)
        md = {
            "mode": mode, "radiant": list(pos_r.values()), "dire": list(pos_d.values()),
            "pos_radiant": pos_r, "pos_dire": pos_d, "live_message": None, "display_id": display_id,
            "score": (0, 0), "clock_time": 0, "game_state": "waiting", "gsi_active": False,
            "gsi_match_id": None, "lobby_name": g["lobby_name"], "lobby_password": g["password"],
        }
        self.active_matches[tid] = md
        self.bets[tid] = {}

        from gsi_data import gsi_data
        all_uids = list(pos_r.values()) + list(pos_d.values())
        name_map = models.build_name_map(all_uids, self._username_map(all_uids))
        gsi_data.bind_tournament(tid, g["match_id"], name_map)
        t_row = models.get_tournament(tid)
        if t_row:
            md["lobby_match_id"] = t_row["match_id"]

        if channel:
            await channel.send(embed=create_teams_embed(display_id, g["lobby_name"], g["password"], mode, pos_r, pos_d))
            if mode == "5x5":
                draft = CaptainDraft(self, display_id, list(pos_r.values()), list(pos_d.values()))
                embed = discord.Embed(title=f"🎯 Драфт #{display_id}", description=f"**Бан** — ход: ☀️ <@{draft.captain_r}>", color=0x2c2f33)
                embed.add_field(name="☀️ Свет", value="—", inline=True)
                embed.add_field(name="🌑 Тьма", value="—", inline=True)
                embed.add_field(name="🚫 Баны", value="—", inline=False)
                embed.set_footer(text="Капитаны, выбирайте героев!")
                draft.message = await channel.send(embed=embed, view=DraftView(draft))
                live_embed = create_live_match_embed(display_id, mode, r_team, d_team, pos_r, pos_d)
                md["live_message"] = await channel.send(embed=live_embed)
                all_p = list(pos_r.values()) + list(pos_d.values())
                await channel.send(f"📢 {' '.join(f'<@{u}>' for u in all_p)}\nЛобби: `{g['lobby_name']}` | `{g['password']}`")
            else:
                live_embed = create_live_match_embed(display_id, mode, r_team, d_team, pos_r, pos_d)
                md["live_message"] = await channel.send(embed=live_embed)
                all_p = list(pos_r.values()) + list(pos_d.values())
                await channel.send(f"📢 {' '.join(f'<@{u}>' for u in all_p)}\nЛобби: `{g['lobby_name']}` | `{g['password']}`")

        if channel:
            bets_embed = discord.Embed(title="💰 Ставки", color=0x2c2f33)
            bets_embed.add_field(name="☀️ Свет", value="Нет ставок", inline=True)
            bets_embed.add_field(name="🌑 Тьма", value="Нет ставок", inline=True)
            bets_msg = await channel.send(embed=bets_embed, view=BetView(self, tid))
            self.bets_messages[tid] = bets_msg

        asyncio.create_task(self._monitor(tid))
        asyncio.create_task(self._match_timeout(tid))

    def _balance_teams(self, ids):
        players_with_zxc = [(uid, models.get_zxc_rating(uid)[0]) for uid in ids]
        players_with_zxc.sort(key=lambda x: x[1], reverse=True)
        team_a, team_b = [], []
        for i, (uid, _) in enumerate(players_with_zxc):
            (team_a if i % 2 == 0 else team_b).append(uid)
        return team_a + team_b

    async def _match_timeout(self, tid):
        await asyncio.sleep(900)
        md = self.active_matches.get(tid)
        if md and md["game_state"] == "waiting":
            channel = self.bot.get_channel(REGISTRATION_CHANNEL_ID)
            if channel:
                await channel.send(f"⚠️ #{md['display_id']} отменён по тайм-ауту")
            await self._refund_bets(tid)
            self.bets.pop(tid, None)
            models.cancel_tournament(tid)
            self.active_matches.pop(tid, None)

    async def _monitor(self, tid):
        from gsi_data import gsi_data
        md = self.active_matches.get(tid)
        if not md:
            return
        last, awarded, leaver_penalized = "waiting", False, False
        while tid in self.active_matches:
            await asyncio.sleep(1)
            cur = gsi_data.get_current()
            if not cur:
                continue
            gs = cur.get("game_state", "")
            ns = "in_progress" if "IN_PROGRESS" in gs else "finished" if "POST_GAME" in gs else "waiting"
            sc = (cur.get("radiant_score", 0), cur.get("dire_score", 0))
            cl = cur.get("clock_time", 0)
            md["score"], md["clock_time"], md["game_state"] = sc, cl, ns

            map_id = cur.get("matchid") or cur.get("map", {}).get("matchid")
            if map_id and map_id != "unknown" and ns in ("in_progress", "finished"):
                md["gsi_match_id"] = str(map_id)

            if ns == "in_progress":
                player_data = cur.get("player", {})
                gsi_name = player_data.get("name", "")
                if gsi_name:
                    for uid in md["radiant"] + md["dire"]:
                        user = self.bot.get_user(uid)
                        if user and (user.name == gsi_name or user.display_name == gsi_name):
                            models.learn_dota_name(uid, gsi_name)

            if ns == "in_progress" and not leaver_penalized:
                player_data = cur.get("player", {})
                if player_data.get("activity") == "abandoned":
                    leaver_name = player_data.get("name", "")
                    for uid in md["radiant"] + md["dire"]:
                        user = self.bot.get_user(uid)
                        dota = models.get_player_dota_name(uid)
                        if user and (user.name == leaver_name or (dota and dota.lower() == leaver_name.lower())):
                            models.add_points(uid, -50, False, count_match=False)
                            channel = self.bot.get_channel(REGISTRATION_CHANNEL_ID)
                            if channel:
                                await channel.send(f"⚠️ <@{uid}> покинул матч! Штраф: **-50** очков.")
                            leaver_penalized = True
                            break

            if ns != last and md["live_message"]:
                try:
                    heroes = {}
                    hero_data = cur.get("hero", {})
                    if hero_data and hero_data.get("name"):
                        if md["mode"] == "1x1":
                            player_team = cur.get("player_team", "")
                            if player_team == "radiant":
                                heroes[str(md["radiant"][0])] = hero_data["name"]
                            else:
                                heroes[str(md["dire"][0])] = hero_data["name"]
                    await md["live_message"].edit(embed=create_live_match_embed(
                        md["display_id"], md["mode"], md["radiant"], md["dire"],
                        md["pos_radiant"], md["pos_dire"], sc, cl, ns, heroes
                    ))
                except:
                    pass
                last = ns
            if ns == "finished" and not awarded:
                awarded = True
                winner = "radiant" if cur.get("radiant_win") else "dire"
                await self._finish_match(tid, winner)
                return

    def _username_map(self, uids: list[int]) -> dict[int, str]:
        out = {}
        for uid in uids:
            u = self.bot.get_user(uid)
            out[uid] = u.name if u else str(uid)
        return out

    def _pull_gsi_match(self, tid: int, md: dict) -> dict:
        from gsi_data import gsi_data
        lobby_id = md.get("lobby_match_id")
        data = gsi_data.pop_finished_for_tournament(tid, lobby_id)
        if data:
            return data
        gsi_id = md.get("gsi_match_id")
        if gsi_id:
            data = gsi_data.pop_finished(gsi_id)
            if data:
                return data
        return gsi_data.pop_finished(str(md.get("display_id", ""))) or {}

    def _build_match_context(self, md: dict, gsi_match: dict) -> dict:
        player_stats = gsi_match.get("player_stats") or {}
        match_details = gsi_match.get("match_details") or {}
        all_players = md["radiant"] + md["dire"]
        mapped = models.resolve_stats_to_discord(player_stats, all_players)
        registered = models.get_registered_name_set(all_players)

        integrity = analyze_match(
            mode=md["mode"],
            clock_time=md["clock_time"],
            player_stats=player_stats,
            registered_names=registered,
            mapped_count=len(mapped),
            score=md["score"],
            min_mapped_players=INTEGRITY_MIN_MAPPED_PLAYERS,
            min_deaths_5x5=INTEGRITY_MIN_DEATHS_5X5,
            min_deaths_1x1=INTEGRITY_MIN_DEATHS_1X1,
            max_kda_feed=INTEGRITY_MAX_KDA_FEED,
            blowout_score_diff=INTEGRITY_BLOWOUT_SCORE_DIFF,
            blowout_max_minutes=INTEGRITY_BLOWOUT_MAX_MINUTES,
        )

        heroes_raw = match_details.get("heroes") or {}
        heroes_by_uid = {}
        for uid in all_players:
            for gsi_name, hero in heroes_raw.items():
                if gsi_name.lower() in registered or gsi_name == str(uid):
                    p = models.get_player(uid)
                    if p and (
                        (p.get("dota_name") and p["dota_name"].lower() == gsi_name.lower())
                        or (p.get("username") and p["username"].lower() == gsi_name.lower())
                    ):
                        heroes_by_uid[str(uid)] = hero
                        break

        networth_raw = match_details.get("networth") or {}
        stats_by_uid = {}
        for uid, st in mapped.items():
            enriched = dict(st)
            for gsi_name, nw in networth_raw.items():
                p = models.get_player(uid)
                if p and p.get("dota_name") and p["dota_name"].lower() == gsi_name.lower():
                    enriched["net_worth"] = nw
            stats_by_uid[uid] = enriched

        mvp_uid = None
        if integrity.mvp_key:
            for uid in all_players:
                p = models.get_player(uid)
                if not p:
                    continue
                keys = {str(uid), (p.get("dota_name") or "").lower(), (p.get("username") or "").lower()}
                if integrity.mvp_key.lower() in keys or integrity.mvp_key == str(uid):
                    mvp_uid = uid
                    break

        return {
            "player_stats": player_stats,
            "match_details": match_details,
            "mapped": mapped,
            "stats_by_uid": stats_by_uid,
            "heroes_by_uid": heroes_by_uid,
            "integrity": integrity,
            "mvp_uid": mvp_uid,
        }

    async def _send_match_log(self, md: dict, winner: str, ctx: dict, *, voided: bool):
        if not MATCH_LOG_CHANNEL_ID:
            return
        channel = self.bot.get_channel(MATCH_LOG_CHANNEL_ID)
        if not channel:
            return
        embed = create_match_log_embed(
            md["display_id"],
            md["mode"],
            winner,
            md["score"],
            md["clock_time"],
            md["radiant"],
            md["dire"],
            ctx["stats_by_uid"],
            ctx["heroes_by_uid"],
            voided=voided,
            void_reason=ctx["integrity"].void_reason,
            mvp_uid=ctx.get("mvp_uid"),
            integrity_issues=ctx["integrity"].issues,
        )
        await channel.send(embed=embed)

    async def _refund_bets(self, tid: int):
        for uid, bet in self.bets.get(tid, {}).items():
            models.refund_bet(uid, bet["amount"])

    async def _void_match(self, tid: int, winner: str, reason: str, ctx: dict):
        md = self.active_matches.pop(tid, None)
        if not md:
            return
        await self._refund_bets(tid)
        self.bets.pop(tid, None)

        for uid, stats in ctx["mapped"].items():
            hero = ctx["heroes_by_uid"].get(str(uid))
            dota = None
            for name in ctx["player_stats"]:
                p = models.get_player(uid)
                if p and p.get("dota_name") and p["dota_name"].lower() == name.lower():
                    dota = name
                    break
            models.save_tournament_player_stats(tid, uid, stats, hero=hero, dota_name=dota)

        for feeder_key in ctx["integrity"].feeders:
            for uid in md["radiant"] + md["dire"]:
                p = models.get_player(uid)
                if not p:
                    continue
                if feeder_key.lower() in {
                    str(uid),
                    (p.get("dota_name") or "").lower(),
                    (p.get("username") or "").lower(),
                }:
                    models.add_points(uid, -FEED_PENALTY_POINTS, count_match=False)
                    models.set_win_streak(uid, 0)

        models.void_tournament(tid, reason)
        models.save_match_duration(tid, md["clock_time"])
        self._persist_match_logs(tid, md, ctx["stats_by_uid"], ctx["integrity"].issues)

        from gsi_data import gsi_data
        gsi_data.unbind_tournament(tid)

        reg = self.bot.get_channel(REGISTRATION_CHANNEL_ID)
        if reg:
            await reg.send(embed=create_void_embed(md["display_id"], reason, md["mode"], md["score"], md["clock_time"]))

        admin = self.bot.get_channel(ADMIN_CHANNEL_ID)
        if admin:
            await admin.send(
                f"🚫 Матч **#{md['display_id']}** аннулирован.\n"
                f"Причина: {reason}\n"
                f"Лобби: `{md.get('lobby_name', '?')}`"
            )

        await self._send_match_log(md, winner, ctx, voided=True)

    async def _finish_match(self, tid: int, winner: str):
        md = self.active_matches.get(tid)
        if not md:
            return
        gsi_match = self._pull_gsi_match(tid, md)
        ctx = self._build_match_context(md, gsi_match)

        if not ctx["integrity"].valid:
            await self._void_match(tid, winner, ctx["integrity"].void_reason or "нарушение правил", ctx)
            return

        await self._award(tid, winner, ctx, gsi_match)

    async def _award(self, tid, winner, ctx: dict, gsi_match: dict):
        md = self.active_matches.pop(tid, None)
        t = models.get_tournament(tid)
        if not t or not md or t["status"] in ("finished", "cancelled"):
            return

        wteam = md["radiant"] if winner == "radiant" else md["dire"]
        lteam = md["dire"] if winner == "radiant" else md["radiant"]
        player_stats = ctx["player_stats"]
        match_details = gsi_match.get("match_details") or {}
        mapped = ctx["mapped"]
        avg_winner_zxc = models.get_team_avg_zxc(wteam)
        avg_loser_zxc = models.get_team_avg_zxc(lteam)
        mvp_uid = ctx.get("mvp_uid")

        for u in wteam:
            st = mapped.get(u, {})
            k = st.get("kills", 0)
            d = st.get("deaths", 0)
            a = st.get("assists", 0)
            lh = st.get("last_hits", 0)
            dn = st.get("denies", 0)
            bonus = min(models.get_win_streak(u) * STREAK_BONUS_PER_WIN, STREAK_BONUS_MAX)
            total = WINNER_POINTS + bonus
            if mvp_uid == u:
                total += MVP_BONUS_POINTS
            models.add_points(u, total, True)
            models.set_win_streak(u, models.get_win_streak(u) + 1)
            models.save_tournament_player_stats(
                tid, u, st,
                hero=ctx["heroes_by_uid"].get(str(u)),
                dota_name=models.get_player_dota_name(u),
            )
            if not models.is_calibrated(u, md["mode"]):
                models.update_zxc_calibration(u, k, d, a, True, md["mode"], lh, dn)
            else:
                models.update_zxc_after_calibration(u, k, d, a, True, avg_winner_zxc, avg_loser_zxc, md["mode"])

        for u in lteam:
            st = mapped.get(u, {})
            k = st.get("kills", 0)
            d = st.get("deaths", 0)
            a = st.get("assists", 0)
            lh = st.get("last_hits", 0)
            dn = st.get("denies", 0)
            models.add_points(u, LOSER_POINTS, False)
            models.set_win_streak(u, 0)
            models.save_tournament_player_stats(
                tid, u, st,
                hero=ctx["heroes_by_uid"].get(str(u)),
                dota_name=models.get_player_dota_name(u),
            )
            if not models.is_calibrated(u, md["mode"]):
                models.update_zxc_calibration(u, k, d, a, False, md["mode"], lh, dn)
            else:
                models.update_zxc_after_calibration(u, k, d, a, False, avg_loser_zxc, avg_winner_zxc, md["mode"])

        if tid in self.bets:
            for uid, bet in self.bets[tid].items():
                if bet["team"] == winner:
                    models.add_points(uid, bet["amount"] * 2, count_match=False)
        self.bets.pop(tid, None)

        models.set_tournament_winner(tid, winner)
        models.save_match_duration(tid, md["clock_time"])
        self._persist_match_logs(tid, md, ctx["stats_by_uid"])

        from gsi_data import gsi_data
        gsi_data.unbind_tournament(tid)

        channel = self.bot.get_channel(REGISTRATION_CHANNEL_ID)
        if channel:
            heroes = ctx["heroes_by_uid"]
            items = match_details.get("items", {})
            networth = match_details.get("networth", {})
            embed = create_result_embed(
                md["display_id"],
                "☀️ Свет" if winner == "radiant" else "🌑 Тьма",
                md["score"], md["clock_time"], md["mode"],
                md["radiant"], md["dire"], heroes, items, networth,
            )
            if mvp_uid:
                embed.add_field(name="⭐ MVP", value=f"<@{mvp_uid}> (+{MVP_BONUS_POINTS} очков)", inline=False)
            await channel.send(embed=embed)

        await self._send_match_log(md, winner, ctx, voided=False)

    @discord.slash_command(name="link_dota", description="Привязать ник Dota 2 к Discord", guild_ids=[GUILD_ID])
    async def link_dota(self, ctx: discord.ApplicationContext, dota_name: str):
        await ctx.defer(ephemeral=True)
        name = dota_name.strip()
        if len(name) < 2 or len(name) > 32:
            return await ctx.followup.send("<:no:1503121885674868938> Ник должен быть от 2 до 32 символов.", ephemeral=True)
        models.get_or_create_player(ctx.author.id, ctx.author.name)
        models.set_player_dota_name(ctx.author.id, name)
        await ctx.followup.send(
            f"<:yes:1503121926128664766> Dota-ник **{name}** привязан.\n"
            "Это нужно для статистики, логов и антифида.",
            ephemeral=True,
        )

    @discord.slash_command(name="void_match", description="Аннулировать текущий матч (админ)", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def void_match(self, ctx: discord.ApplicationContext, reason: str = "решение администратора"):
        await ctx.defer(ephemeral=True)
        active = models.get_active_tournament()
        if not active:
            return await ctx.followup.send("<:no:1503121885674868938> Нет активного матча.", ephemeral=True)
        tid = active["id"]
        md = self.active_matches.get(tid)
        if not md:
            return await ctx.followup.send("<:no:1503121885674868938> Матч не в процессе.", ephemeral=True)
        gsi_match = self._pull_gsi_match(tid, md)
        ctx_data = self._build_match_context(md, gsi_match)
        winner = "radiant" if md["score"][0] >= md["score"][1] else "dire"
        await self._void_match(tid, winner, reason, ctx_data)
        await ctx.followup.send(f"<:yes:1503121926128664766> Матч #{md['display_id']} аннулирован.", ephemeral=True)

    @discord.slash_command(name="report", description="Пожаловаться на игрока", guild_ids=[GUILD_ID])
    async def report(self, ctx, player: discord.Member, reason: str):
        if player.id == ctx.author.id:
            return await ctx.respond("<:no:1503121885674868938> Нельзя жаловаться на себя!", ephemeral=True)
        admin_channel = self.bot.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            embed = discord.Embed(title="🚨 Репорт", color=0xe74c3c)
            embed.add_field(name="Нарушитель", value=f"{player.mention} ({player.id})", inline=True)
            embed.add_field(name="Отправитель", value=f"{ctx.author.mention} ({ctx.author.id})", inline=True)
            embed.add_field(name="Причина", value=reason, inline=False)
            await admin_channel.send(embed=embed)
        await ctx.respond(f"<:yes:1503121926128664766> Жалоба на {player.mention} отправлена.", ephemeral=True)

    @discord.slash_command(name="auto_stop", description="Остановить", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def auto_stop(self, ctx):
        self.auto_mode = False
        if self.auto_task:
            self.auto_task.cancel()
        await ctx.respond("<:yes:1503121926128664766> Остановлены.", ephemeral=True)

    @discord.slash_command(name="auto_start", description="Запустить", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def auto_start(self, ctx):
        if self.auto_mode:
            return await ctx.respond("<:no:1503121885674868938> Уже запущены!", ephemeral=True)
        self.auto_mode = True
        self.auto_task = asyncio.create_task(self._auto_loop())
        await ctx.respond("<:yes:1503121926128664766> Запущены!", ephemeral=True)

    @discord.slash_command(name="gsi_status", description="Статус", guild_ids=[GUILD_ID])
    async def gsi_status(self, ctx):
        from gsi_data import gsi_data
        cur = gsi_data.get_current()
        embed = discord.Embed(title="📡 Статус", color=0x2c2f33)
        embed.add_field(name="GSI", value="<:yes:1503121926128664766> Активен" if cur else "⏳ Ожидание", inline=True)
        embed.add_field(name="Авто", value="<:yes:1503121926128664766> Вкл" if self.auto_mode else "<:no:1503121885674868938> Выкл", inline=True)
        embed.add_field(name="5x5", value=f"#{self.match_counter.get('5x5', 0)}", inline=True)
        embed.add_field(name="1x1", value=f"#{self.match_counter.get('1x1', 0)}", inline=True)
        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(name="match_history", description="История", guild_ids=[GUILD_ID])
    async def match_history(self, ctx):
        conn = models.get_connection()
        rows = conn.execute("SELECT id, winner, team_radiant, team_dire, finished_at FROM tournaments WHERE status='finished' ORDER BY finished_at DESC LIMIT 5").fetchall()
        conn.close()
        matches = [{"id": r["id"], "winner": r["winner"], "team_radiant": json.loads(r["team_radiant"]), "team_dire": json.loads(r["team_dire"]), "finished_at": r["finished_at"]} for r in rows]
        await ctx.respond(embed=create_history_embed(matches))

    @discord.slash_command(name="reset_tournaments", description="Сброс", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def reset_tournaments(self, ctx):
        for g in self.active_gather.values():
            g["finalized"] = True
        self.active_gather.clear()
        self.active_matches.clear()
        await ctx.respond("<:yes:1503121926128664766> Сброшено.", ephemeral=True)

def setup(bot):
    bot.add_cog(Tournament(bot))
