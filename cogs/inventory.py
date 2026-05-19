# =========================================================
#                       inventory.py
# =========================================================
from __future__ import annotations

import discord
from discord.ext import commands

from database import models
from database.connection import get_connection

from config import GUILD_ID

from utils.profile_card import build_profile_banner_png


RANK_COLORS_5x5 = {
    "Мусор": 0x808080,
    "Бронза": 0xcd7f32,
    "Серебро": 0xc0c0c0,
    "Золото": 0xffd700,
    "Платина": 0x00ced1,
    "Алмаз": 0x9b59b6,
    "Мастер": 0xe74c3c,
    "Элита": 0xff6600,
    "Легенда": 0x00ff88,
    "Титан": 0xff4444,
}


RANK_COLORS_1x1 = {
    "Static": 0x808080,
    "Null": 0x666666,
    "Pulse": 0x00ffcc,
    "Vein": 0x8b0000,
    "Echo": 0x4169e1,
    "Haze": 0x9932cc,
    "Vanta": 0x0a0a0a,
    "Abyss": 0x000080,
    "Phantom": 0xff69b4,
    "Eclipse": 0xff4500,
}


class Inventory(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    def get_rank_color(
        self,
        rank_name: str,
        mode: str = "5x5",
    ):

        colors = (
            RANK_COLORS_5x5
            if mode == "5x5"
            else RANK_COLORS_1x1
        )

        for name, color in colors.items():

            if name.lower() in str(rank_name).lower():
                return color

        return 0x5865F2

    @discord.slash_command(
        name="profile",
        description="Профиль игрока",
        guild_ids=[GUILD_ID],
    )
    async def profile(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member = None,
    ):

        await ctx.defer()

        target = member or ctx.author

        player = models.get_player(target.id)

        if not player:

            return await ctx.followup.send(
                "Игрок ещё не играл.",
                ephemeral=True,
            )

        wins = int(player.get("wins", 0) or 0)

        losses = int(player.get("losses", 0) or 0)

        kills, deaths, assists = (
            models.get_player_kda(target.id)
        )

        kda_ratio = round(
            (kills + assists) / max(1, deaths),
            2,
        )

        rating_5, rank_name_5, _ = (
            models.get_zxc_rating(
                target.id,
                "5x5",
            )
        )

        rating_1, rank_name_1, _ = (
            models.get_zxc_rating(
                target.id,
                "1x1",
            )
        )

        conn = get_connection()

        row = conn.execute(
            """
            SELECT
                calibration_5x5,
                calibration_1x1
            FROM players
            WHERE discord_id = ?
            """,
            (target.id,),
        ).fetchone()

        clan_row = conn.execute(
            """
            SELECT
                c.name,
                c.tag
            FROM clans c
            JOIN clan_members cm
                ON c.id = cm.clan_id
            WHERE cm.discord_id = ?
            """,
            (target.id,),
        ).fetchone()

        conn.close()

        calib5_n = int(
            row["calibration_5x5"] or 0
        ) if row else 0

        calib1_n = int(
            row["calibration_1x1"] or 0
        ) if row else 0

        clan_tag = (
            clan_row["tag"]
            if clan_row
            else ""
        )

        clan_name = (
            clan_row["name"]
            if clan_row
            else ""
        )

        avatar_bytes = None

        try:
            avatar_bytes = await target.display_avatar.read()
        except Exception:
            pass

        rank_color = self.get_rank_color(
            rank_name_5,
            "5x5",
        )

        accent_rgb = (
            (rank_color >> 16) & 255,
            (rank_color >> 8) & 255,
            rank_color & 255,
        )

        png = build_profile_banner_png(
            username=target.display_name,

            avatar_bytes=avatar_bytes,

            accent_rgb=accent_rgb,

            points=int(
                player.get("points", 0) or 0
            ),

            wins=wins,
            losses=losses,

            zxc_5=int(rating_5 or 1000),
            rank_5=str(rank_name_5),

            calib_5=calib5_n,

            zxc_1=int(rating_1 or 1000),
            rank_1=str(rank_name_1),

            calib_1=calib1_n,

            kda_ratio=float(kda_ratio),

            clan_tag=str(clan_tag),
            clan_name=str(clan_name),
        )

        file = discord.File(
            fp=png,
            filename="profile.png",
        )

        matches = wins + losses
        winrate = int(
            round(
                (wins / max(1, matches)) * 100
            )
        )

        embed = discord.Embed(
            color=rank_color
        )
        embed.set_author(
            name=target.display_name,
            icon_url=target.display_avatar.url if target.display_avatar else None,
        )
        embed.set_image(
            url="attachment://profile.png"
        )
        embed.add_field(
            name="Очки",
            value=f"**{int(player.get('points', 0) or 0)}**",
            inline=True,
        )
        embed.add_field(
            name="Матчей",
            value=f"**{matches}**",
            inline=True,
        )
        embed.add_field(
            name="Винрейт",
            value=f"**{winrate}%**",
            inline=True,
        )
        embed.add_field(
            name="W / L",
            value=f"**{wins} / {losses}**",
            inline=True,
        )
        embed.add_field(
            name="KDA",
            value=f"**{kda_ratio}**",
            inline=True,
        )
        embed.add_field(
            name="Ранги",
            value=(
                f"**5x5:** {rank_name_5} ({int(rating_5 or 1000)}) | калиб {calib5_n}/5\n"
                f"**1x1:** {rank_name_1} ({int(rating_1 or 1000)}) | калиб {calib1_n}/5"
            )[:1024],
            inline=False,
        )
        if clan_tag or clan_name:
            embed.add_field(
                name="Клан",
                value=f"**[{clan_tag}] {clan_name}**",
                inline=False,
            )

        await ctx.followup.send(
            embed=embed,
            file=file,
        )


def setup(bot):
    bot.add_cog(Inventory(bot))
