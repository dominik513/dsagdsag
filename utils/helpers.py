from __future__ import annotations

import discord
from config import (
    WINNER_POINTS, LOSER_POINTS, EMOJI_CARRY, EMOJI_MID, EMOJI_OFFLANE, EMOJI_SUP4, EMOJI_SUP5,
    EMOJI_RADIANT, EMOJI_DIRE, EMOJI_BET, EMOJI_POINTS, EMOJI_CLOCK, EMOJI_KILLS, EMOJI_DEATHS, EMOJI_ASSISTS,
)
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

def create_gather_embed(time_left: int, mode: str, players: dict) -> discord.Embed:
    max_players = 10 if mode == "5x5" else 2
    progress = len(players)
    m, s = time_left // 60, time_left % 60
    title = "Сбор 5x5" if mode == "5x5" else "Мид-дуэль"
    embed = discord.Embed(title=title, description=f"**{progress}/{max_players}**  •  {EMOJI_CLOCK} {m:02d}:{s:02d}", color=EMBED_COLOR)
    if players:
        lines = []
        for uid, pos in players.items():
            tag = get_clan_tag(uid)
            emoji = {1: EMOJI_CARRY, 2: EMOJI_MID, 3: EMOJI_OFFLANE, 4: EMOJI_SUP4, 5: EMOJI_SUP5}.get(pos, "❓")
            lines.append(f"{emoji} {tag} <@{uid}> — Pos {pos}")
        embed.add_field(name="Игроки", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Игроки", value="🔲 Ожидание игроков...", inline=False)
    embed.set_footer(text="Выберите позицию кнопкой ниже")
    return embed

def create_teams_embed(tid: int, lobby_name: str, password: str, mode: str, pos_r: dict, pos_d: dict) -> discord.Embed:
    embed = discord.Embed(title=f"⚔️ Матч #{tid}" if mode == "5x5" else f"🔥 Мид-дуэль #{tid}", color=EMBED_COLOR)
    if mode == "1x1":
        tag_r = get_clan_tag(pos_r[2])
        tag_d = get_clan_tag(pos_d[2])
        embed.add_field(name=f"{EMOJI_RADIANT} Свет", value=f"{EMOJI_MID} {tag_r} <@{pos_r[2]}> — Mid", inline=True)
        embed.add_field(name=f"{EMOJI_DIRE} Тьма", value=f"{EMOJI_MID} {tag_d} <@{pos_d[2]}> — Mid", inline=True)
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
    title = "🔥 Мид-дуэль" if mode == "1x1" else "⚔️ Матч 5x5"
    embed = discord.Embed(title=f"{title} #{tid}", color=colors.get(state, EMBED_COLOR))
    m, s = clock // 60, clock % 60
    if state == "in_progress":
        embed.description = f"{EMOJI_RADIANT} **{score[0]}** - **{score[1]}** {EMOJI_DIRE} | {EMOJI_CLOCK} {m:02d}:{s:02d}"
    elif state == "finished":
        embed.description = f"Завершён | {EMOJI_RADIANT} **{score[0]}** - **{score[1]}** {EMOJI_DIRE} | {EMOJI_CLOCK} {m:02d}:{s:02d}"
    else:
        embed.description = "⏳ Ожидание..."
    if mode == "1x1":
        tag_r = get_clan_tag(radiant[0])
        tag_d = get_clan_tag(dire[0])
        r_hero = heroes.get(str(radiant[0]), "") if heroes else ""
        d_hero = heroes.get(str(dire[0]), "") if heroes else ""
        r_text = f"{tag_r} <@{radiant[0]}>"
        d_text = f"{tag_d} <@{dire[0]}>"
        if r_hero:
            r_text += f"\n*{r_hero}*"
            embed.set_thumbnail(url=HERO_IMAGE_URL.format(r_hero.lower().replace(" ", "_")))
        if d_hero:
            d_text += f"\n*{d_hero}*"
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
        mode = "1x1" if len(m["team_radiant"]) == 1 else "5x5"
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
