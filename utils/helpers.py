from __future__ import annotations

import discord
from config import (
    WINNER_POINTS, LOSER_POINTS, EMOJI_CARRY, EMOJI_MID, EMOJI_OFFLANE, EMOJI_SUP4, EMOJI_SUP5,
    EMOJI_RADIANT, EMOJI_DIRE, EMOJI_BET, EMOJI_POINTS, EMOJI_CLOCK, EMOJI_KILLS, EMOJI_DEATHS, EMOJI_ASSISTS,
)
from utils.game_modes import max_players, mode_title, is_small_lobby
import sqlite3
from config import DATABASE_PATH

EMBED_COLOR = 0x2c2f33
HERO_IMAGE_URL = "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/{}.png"
ITEM_IMAGE_URL = "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/items/{}.png"

CARRY_EMOJI_ID = 1502596075045781714
MID_EMOJI_ID = 1502596096478810112
OFFLANE_EMOJI_ID = 1502596113537044491
SUP4_EMOJI_ID = 1502596130838548541
SUP5_EMOJI_ID = 1502596151688433746
LEAVE_EMOJI_ID = 1502699019993092167

def get_clan_tag(discord_id: int) -> str:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT c.tag FROM clans c JOIN clan_members cm ON c.id = cm.clan_id WHERE cm.discord_id = ?", (discord_id,)).fetchone()
    conn.close()
    return f"[{row['tag']}]" if row else ""

def make_emoji(emoji_id: int) -> discord.PartialEmoji:
    return discord.PartialEmoji(name="emoji", id=emoji_id)

def create_gather_embed(time_left: int, mode: str, players: dict, slots: dict | None = None) -> discord.Embed:
    mx = max_players(mode)
    progress = len(players)
    m, s = time_left // 60, time_left % 60
    embed = discord.Embed(
        title=mode_title(mode),
        description=f"**{progress}/{mx}**  •  {EMOJI_CLOCK} {m:02d}:{s:02d}",
        color=EMBED_COLOR,
    )
    if mode == "2x2" and slots:
        slot_labels = {
            "r1": f"{EMOJI_RADIANT} Свет #1",
            "r2": f"{EMOJI_RADIANT} Свет #2",
            "d1": f"{EMOJI_DIRE} Тьма #1",
            "d2": f"{EMOJI_DIRE} Тьма #2",
        }
        lines = []
        for key, label in slot_labels.items():
            uid = slots.get(key)
            if uid:
                tag = get_clan_tag(uid)
                lines.append(f"{EMOJI_MID} {label}: {tag} <@{uid}>")
            else:
                lines.append(f"{EMOJI_MID} {label}: *свободно*")
        embed.add_field(name="Слоты (мид)", value="\n".join(lines), inline=False)
    elif players:
        lines = []
        for uid, pos in players.items():
            tag = get_clan_tag(uid)
            emoji = {1: EMOJI_CARRY, 2: EMOJI_MID, 3: EMOJI_OFFLANE, 4: EMOJI_SUP4, 5: EMOJI_SUP5}.get(pos, "❓")
            lines.append(f"{emoji} {tag} <@{uid}> — Pos {pos}")
        embed.add_field(name="Игроки", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Игроки", value="🔲 Ожидание игроков...", inline=False)
    footers = {
        "5x5": "Выберите позицию кнопкой ниже",
        "1x1": "Нажмите «Вступить» для мид-дуэли",
        "2x2": "Выберите слот: 2 на мид Света, 2 на мид Тьмы",
    }
    embed.set_footer(text=footers.get(mode, ""))
    return embed


def create_mode_pick_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎮 Выбор режима турнира",
        description=(
            "Администратор выбирает режим — после этого откроется **набор игроков**.\n\n"
            "• **5x5** — классика, 10 игроков, драфт\n"
            "• **1x1** — мид-дуэль, 2 игрока\n"
            "• **2x2** — 4 игрока, по 2 на мид с каждой стороны"
        ),
        color=EMBED_COLOR,
    )
    embed.set_footer(text="Только для администраторов сервера")
    return embed

def _mid_team_lines(uids: list) -> str:
    lines = []
    for uid in uids:
        tag = get_clan_tag(uid)
        lines.append(f"{EMOJI_MID} {tag} <@{uid}> — Mid")
    return "\n".join(lines) if lines else "—"


def create_teams_embed(tid: int, lobby_name: str, password: str, mode: str, pos_r: dict, pos_d: dict) -> discord.Embed:
    titles = {"5x5": f"⚔️ Матч #{tid}", "1x1": f"🔥 Мид-дуэль #{tid}", "2x2": f"🔥 Мид 2x2 #{tid}"}
    embed = discord.Embed(title=titles.get(mode, f"⚔️ Матч #{tid}"), color=EMBED_COLOR)
    if mode == "1x1":
        tag_r = get_clan_tag(pos_r[2])
        tag_d = get_clan_tag(pos_d[2])
        embed.add_field(name=f"{EMOJI_RADIANT} Свет", value=f"{EMOJI_MID} {tag_r} <@{pos_r[2]}> — Mid", inline=True)
        embed.add_field(name=f"{EMOJI_DIRE} Тьма", value=f"{EMOJI_MID} {tag_d} <@{pos_d[2]}> — Mid", inline=True)
    elif mode == "2x2":
        r_uids = list(pos_r.values())
        d_uids = list(pos_d.values())
        embed.add_field(name=f"{EMOJI_RADIANT} Свет", value=_mid_team_lines(r_uids), inline=True)
        embed.add_field(name=f"{EMOJI_DIRE} Тьма", value=_mid_team_lines(d_uids), inline=True)
    else:
        r_lines, d_lines = [], []
        for p, uid in sorted(pos_r.items()):
            tag = get_clan_tag(uid)
            emoji = {1: EMOJI_CARRY, 2: EMOJI_MID, 3: EMOJI_OFFLANE, 4: EMOJI_SUP4, 5: EMOJI_SUP5}.get(p, "❓")
            r_lines.append(f"{emoji} Pos {p}: {tag} <@{uid}>")
        for p, uid in sorted(pos_d.items()):
            tag = get_clan_tag(uid)
            emoji = {1: EMOJI_CARRY, 2: EMOJI_MID, 3: EMOJI_OFFLANE, 4: EMOJI_SUP4, 5: EMOJI_SUP5}.get(p, "❓")
            d_lines.append(f"{emoji} Pos {p}: {tag} <@{uid}>")
        embed.add_field(name=f"{EMOJI_RADIANT} Свет", value="\n".join(r_lines), inline=True)
        embed.add_field(name=f"{EMOJI_DIRE} Тьма", value="\n".join(d_lines), inline=True)
    embed.add_field(name="Лобби", value=f"`{lobby_name}` | `{password}`", inline=False)
    return embed

def create_live_match_embed(tid: int, mode: str, radiant: list, dire: list, pos_r: dict, pos_d: dict, score=(0,0), clock=0, state="waiting", heroes: dict = None) -> discord.Embed:
    colors = {"waiting": EMBED_COLOR, "in_progress": 0x43b581, "finished": 0xfaa61a}
    titles = {"5x5": "⚔️ Матч 5x5", "1x1": "🔥 Мид-дуэль", "2x2": "🔥 Мид 2x2"}
    embed = discord.Embed(title=f"{titles.get(mode, '⚔️ Матч')} #{tid}", color=colors.get(state, EMBED_COLOR))
    m, s = clock // 60, clock % 60
    if state == "in_progress":
        embed.description = f"{EMOJI_RADIANT} **{score[0]}** - **{score[1]}** {EMOJI_DIRE} | {EMOJI_CLOCK} {m:02d}:{s:02d}"
    elif state == "finished":
        embed.description = f"Завершён | {EMOJI_RADIANT} **{score[0]}** - **{score[1]}** {EMOJI_DIRE} | {EMOJI_CLOCK} {m:02d}:{s:02d}"
    else:
        embed.description = "⏳ Ожидание..."
    if is_small_lobby(mode):
        if mode == "1x1":
            r_list, d_list = radiant[:1], dire[:1]
        else:
            r_list, d_list = radiant, dire

        def _side(uids: list) -> str:
            parts = []
            for uid in uids:
                tag = get_clan_tag(uid)
                line = f"{tag} <@{uid}>"
                h = heroes.get(str(uid), "") if heroes else ""
                if h:
                    line += f"\n*{h}*"
                parts.append(line)
            return "\n".join(parts) if parts else "—"

        r_text = _side(r_list)
        d_text = _side(d_list)
        if heroes and r_list:
            h0 = heroes.get(str(r_list[0]), "")
            if h0:
                embed.set_thumbnail(url=HERO_IMAGE_URL.format(h0.lower().replace(" ", "_")))
        embed.add_field(name=f"{EMOJI_RADIANT} Свет", value=r_text, inline=True)
        embed.add_field(name=f"{EMOJI_DIRE} Тьма", value=d_text, inline=True)
    else:
        r_lines = []
        for uid in radiant:
            tag = get_clan_tag(uid)
            hero = heroes.get(str(uid), "") if heroes else ""
            line = f"{tag} <@{uid}>"
            if hero:
                line += f" — *{hero}*"
                embed.set_thumbnail(url=HERO_IMAGE_URL.format(hero.lower().replace(" ", "_")))
            r_lines.append(line)
        d_lines = []
        for uid in dire:
            tag = get_clan_tag(uid)
            hero = heroes.get(str(uid), "") if heroes else ""
            line = f"{tag} <@{uid}>"
            if hero:
                line += f" — *{hero}*"
            d_lines.append(line)
        embed.add_field(name=f"{EMOJI_RADIANT} Свет", value="\n".join(r_lines), inline=False)
        embed.add_field(name=f"{EMOJI_DIRE} Тьма", value="\n".join(d_lines), inline=False)
    return embed

def create_result_embed(tid: int, winner_name: str, score: tuple, clock: int, mode: str, radiant: list, dire: list, heroes: dict = None, items: dict = None, networth: dict = None) -> discord.Embed:
    embed = discord.Embed(
        title=f"🏆 Матч #{tid} завершён",
        description=(
            f"**{winner_name}** одержали победу!\n"
            f"{EMOJI_RADIANT} **{score[0]}** — **{score[1]}** {EMOJI_DIRE}\n"
            f"{EMOJI_CLOCK} **{clock // 60}:{clock % 60:02d}**\n\n"
            f"{EMOJI_POINTS} +{WINNER_POINTS} / +{LOSER_POINTS} очков"
        ),
        color=0x43b581 if winner_name.startswith("☀️") else 0xe74c3c
    )
    r_parts = []
    for uid in radiant:
        tag = get_clan_tag(uid)
        parts = [f"{tag} <@{uid}>"]
        if heroes and str(uid) in heroes:
            parts.append(f"🦸 *{heroes[str(uid)]}*")
        if networth and str(uid) in networth:
            parts.append(f"{EMOJI_BET} {networth[str(uid)]}")
        r_parts.append(" | ".join(parts))
    embed.add_field(name=f"{EMOJI_RADIANT} Силы Света", value="\n".join(r_parts) if r_parts else "—", inline=False)
    d_parts = []
    for uid in dire:
        tag = get_clan_tag(uid)
        parts = [f"{tag} <@{uid}>"]
        if heroes and str(uid) in heroes:
            parts.append(f"🦸 *{heroes[str(uid)]}*")
        if networth and str(uid) in networth:
            parts.append(f"{EMOJI_BET} {networth[str(uid)]}")
        d_parts.append(" | ".join(parts))
    embed.add_field(name=f"{EMOJI_DIRE} Силы Тьмы", value="\n".join(d_parts) if d_parts else "—", inline=False)
    if items:
        all_items = []
        for uid in radiant + dire:
            if str(uid) in items and items[str(uid)]:
                item_icons = " ".join([f"<:item:{i}>" if isinstance(i, int) else f"`{i}`" for i in items[str(uid)][:6]])
                if item_icons:
                    all_items.append(f"<@{uid}>: {item_icons}")
        if all_items:
            embed.add_field(name="🎒 Предметы", value="\n".join(all_items[:10]), inline=False)
    embed.set_footer(text="Спасибо за игру!")
    return embed

def create_void_embed(tid: int, reason: str, mode: str, score: tuple, clock: int) -> discord.Embed:
    m, s = clock // 60, clock % 60
    embed = discord.Embed(
        title=f"🚫 Матч #{tid} аннулирован",
        description=(
            f"**Причина:** {reason}\n"
            f"Режим: **{mode}** | {EMOJI_RADIANT} **{score[0]}** — **{score[1]}** {EMOJI_DIRE}\n"
            f"{EMOJI_CLOCK} {m:02d}:{s:02d}\n\n"
            "Очки и рейтинг **не начислены**. Ставки **возвращены**."
        ),
        color=0xe74c3c,
    )
    embed.set_footer(text="При ошибке обратитесь к администратору")
    return embed


def create_match_log_embed(
    tid: int,
    mode: str,
    winner: str,
    score: tuple,
    clock: int,
    radiant: list,
    dire: list,
    stats_by_uid: dict,
    heroes: dict | None = None,
    *,
    voided: bool = False,
    void_reason: str | None = None,
    mvp_uid: int | None = None,
    integrity_issues: list | None = None,
) -> discord.Embed:
    m, s = clock // 60, clock % 60
    winner_label = "☀️ Свет" if winner == "radiant" else "🌑 Тьма"
    title = f"📋 Лог матча #{tid}" + (" — АННУЛИРОВАН" if voided else "")
    embed = discord.Embed(
        title=title,
        description=(
            f"{'🚫 ' + void_reason if voided and void_reason else f'Победитель: **{winner_label}**'}\n"
            f"{EMOJI_RADIANT} **{score[0]}** — **{score[1]}** {EMOJI_DIRE} | {EMOJI_CLOCK} {m:02d}:{s:02d} | {mode}"
        ),
        color=0xe74c3c if voided else 0x5865f2,
    )

    def _lines(team: list, side: str) -> list[str]:
        out = []
        for uid in team:
            st = stats_by_uid.get(uid, {})
            k = st.get("kills", 0)
            d = st.get("deaths", 0)
            a = st.get("assists", 0)
            lh = st.get("last_hits", 0)
            dn = st.get("denies", 0)
            nw = st.get("net_worth", 0)
            tag = get_clan_tag(uid)
            hero = ""
            if heroes:
                hero = heroes.get(str(uid)) or heroes.get(uid) or st.get("hero", "")
            mvp_mark = " ⭐" if mvp_uid == uid else ""
            hero_part = f" | {hero}" if hero else ""
            out.append(
                f"{tag} <@{uid}>{mvp_mark}{hero_part}\n"
                f"{EMOJI_KILLS}{k} {EMOJI_DEATHS}{d} {EMOJI_ASSISTS}{a} | LH **{lh}** DN **{dn}** | {EMOJI_BET} **{nw}**"
            )
        return out

    r_lines = _lines(radiant, "radiant")
    d_lines = _lines(dire, "dire")
    embed.add_field(name=f"{EMOJI_RADIANT} Свет", value="\n".join(r_lines) if r_lines else "—", inline=False)
    embed.add_field(name=f"{EMOJI_DIRE} Тьма", value="\n".join(d_lines) if d_lines else "—", inline=False)

    if integrity_issues:
        issues_text = "\n".join(f"• `{i.code}`: {i.detail}" for i in integrity_issues[:8])
        embed.add_field(name="⚠️ Проверка честности", value=issues_text, inline=False)

    return embed


def create_history_embed(matches: list) -> discord.Embed:
    embed = discord.Embed(title="📜 История", color=EMBED_COLOR)
    if not matches:
        embed.description = "Нет матчей"
        return embed
    for m in matches:
        r_n = len(m["team_radiant"])
        if r_n >= 5:
            mode = "5x5"
        elif r_n == 2:
            mode = "2x2"
        else:
            mode = "1x1"
        winner = f"{EMOJI_RADIANT} Свет" if m["winner"] == "radiant" else f"{EMOJI_DIRE} Тьма"
        embed.add_field(name=f"#{m['id']} — {mode}", value=winner, inline=False)
    return embed

class PositionButtons(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    @discord.ui.button(label="Carry", style=discord.ButtonStyle.grey, emoji=make_emoji(CARRY_EMOJI_ID), custom_id="pos1")
    async def pos1(self, b, i): await self.cog.register_player(i, 1)
    @discord.ui.button(label="Mid", style=discord.ButtonStyle.grey, emoji=make_emoji(MID_EMOJI_ID), custom_id="pos2")
    async def pos2(self, b, i): await self.cog.register_player(i, 2)
    @discord.ui.button(label="Offlane", style=discord.ButtonStyle.grey, emoji=make_emoji(OFFLANE_EMOJI_ID), custom_id="pos3")
    async def pos3(self, b, i): await self.cog.register_player(i, 3)
    @discord.ui.button(label="Sup 4", style=discord.ButtonStyle.grey, emoji=make_emoji(SUP4_EMOJI_ID), custom_id="pos4")
    async def pos4(self, b, i): await self.cog.register_player(i, 4)
    @discord.ui.button(label="Sup 5", style=discord.ButtonStyle.grey, emoji=make_emoji(SUP5_EMOJI_ID), custom_id="pos5")
    async def pos5(self, b, i): await self.cog.register_player(i, 5)
    @discord.ui.button(label="Выйти", style=discord.ButtonStyle.grey, emoji=make_emoji(LEAVE_EMOJI_ID), custom_id="leave_btn")
    async def leave_btn(self, b, i): await self.cog.leave_player(i)

class SoloButtons(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    @discord.ui.button(label="Вступить", style=discord.ButtonStyle.grey, emoji=make_emoji(MID_EMOJI_ID), custom_id="solo_reg")
    async def solo(self, b, i): await self.cog.register_player(i)
    @discord.ui.button(label="Выйти", style=discord.ButtonStyle.grey, emoji=make_emoji(LEAVE_EMOJI_ID), custom_id="solo_leave")
    async def leave_btn(self, b, i): await self.cog.leave_player(i)


class DuoButtons(discord.ui.View):
    """2x2: два мида на каждую сторону."""

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Свет #1", style=discord.ButtonStyle.grey, emoji=make_emoji(MID_EMOJI_ID), custom_id="duo_r1", row=0)
    async def r1(self, b, i): await self.cog.register_player(i, team_slot="r1")

    @discord.ui.button(label="Свет #2", style=discord.ButtonStyle.grey, emoji=make_emoji(MID_EMOJI_ID), custom_id="duo_r2", row=0)
    async def r2(self, b, i): await self.cog.register_player(i, team_slot="r2")

    @discord.ui.button(label="Тьма #1", style=discord.ButtonStyle.grey, emoji=make_emoji(MID_EMOJI_ID), custom_id="duo_d1", row=1)
    async def d1(self, b, i): await self.cog.register_player(i, team_slot="d1")

    @discord.ui.button(label="Тьма #2", style=discord.ButtonStyle.grey, emoji=make_emoji(MID_EMOJI_ID), custom_id="duo_d2", row=1)
    async def d2(self, b, i): await self.cog.register_player(i, team_slot="d2")

    @discord.ui.button(label="Выйти", style=discord.ButtonStyle.grey, emoji=make_emoji(LEAVE_EMOJI_ID), custom_id="duo_leave", row=2)
    async def leave_btn(self, b, i): await self.cog.leave_player(i)
