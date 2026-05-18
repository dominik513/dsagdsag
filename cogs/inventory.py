import discord
from discord.ext import commands
from database import models
from config import (
    EMOJI_PROFILE_POINTS, EMOJI_PROFILE_WINS, EMOJI_PROFILE_LOSSES,
    EMOJI_PROFILE_WINRATE, EMOJI_PROFILE_MATCHES,
    EMOJI_KILLS, EMOJI_DEATHS, EMOJI_ASSISTS, GUILD_ID
)

RANK_COLORS_5x5 = {
    "Мусор": 0x808080, "Бронза": 0xcd7f32, "Серебро": 0xc0c0c0,
    "Золото": 0xffd700, "Платина": 0x00ced1, "Алмаз": 0x9b59b6,
    "Мастер": 0xe74c3c, "Элита": 0xff6600, "Легенда": 0x00ff88, "Титан": 0xff4444,
}

RANK_COLORS_1x1 = {
    "Static": 0x808080, "Null": 0x666666, "Pulse": 0x00ffcc,
    "Vein": 0x8b0000, "Echo": 0x4169e1, "Haze": 0x9932cc,
    "Vanta": 0x0a0a0a, "Abyss": 0x000080, "Phantom": 0xff69b4, "Eclipse": 0xff4500,
}

class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_rank_color(self, rank_name: str, mode: str = "5x5") -> int:
        colors = RANK_COLORS_5x5 if mode == "5x5" else RANK_COLORS_1x1
        for name, color in colors.items():
            if name in rank_name:
                return color
        return 0x2c2f33

    @discord.slash_command(name="profile", description="Ваш профиль", guild_ids=[GUILD_ID])
    async def profile(self, ctx: discord.ApplicationContext, member: discord.Member = None):
        target = member or ctx.author
        player = models.get_player(target.id)
        if not player:
            await ctx.respond(f"<:no:1503121885674868938> {target.mention} ещё не играл.", ephemeral=True)
            return
        stats = models.get_player_stats(target.id)
        roles = models.get_player_roles(target.id)
        kills, deaths, assists = models.get_player_kda(target.id)
        kda_ratio = round((kills + assists) / max(1, deaths), 2)
        winrate = round(stats['wins'] / max(1, stats['total_matches']) * 100)
        rating_5, rank_name_5, emoji_5 = models.get_zxc_rating(target.id, "5x5")
        rating_1, rank_name_1, emoji_1 = models.get_zxc_rating(target.id, "1x1")
        calib_5 = models.is_calibrated(target.id, "5x5")
        calib_1 = models.is_calibrated(target.id, "1x1")
        rank_color = self.get_rank_color(rank_name_5, "5x5")
        embed = discord.Embed(color=rank_color)
        embed.set_author(name=f"{target.display_name}", icon_url=target.avatar.url if target.avatar else None)
        rank_5_text = f"{emoji_5} **{rank_name_5}**"
        rank_1_text = f"{emoji_1} **{rank_name_1}**"
        embed.description = f"**5x5:** {rank_5_text}\n**1x1:** {rank_1_text}"
        conn = models.get_connection()
        clan_row = conn.execute(
            "SELECT c.name, c.tag FROM clans c JOIN clan_members cm ON c.id = cm.clan_id WHERE cm.discord_id = ?",
            (target.id,)
        ).fetchone()
        conn.close()
        if clan_row:
            embed.add_field(name="🏰 Клан", value=f"**[{clan_row['tag']}] {clan_row['name']}**", inline=False)
        embed.add_field(name="▬▬▬▬▬▬▬▬▬▬▬▬", value="", inline=False)
        embed.add_field(name=f"{EMOJI_PROFILE_POINTS} Очки", value=f"**{player['points']}**", inline=True)
        embed.add_field(name=f"{EMOJI_PROFILE_MATCHES} Матчей", value=f"**{stats['total_matches']}**", inline=True)
        embed.add_field(name=f"{EMOJI_PROFILE_WINRATE} Винрейт", value=f"**{winrate}%**", inline=True)
        embed.add_field(name=f"{EMOJI_PROFILE_WINS} Победы", value=f"**{stats['wins']}**", inline=True)
        embed.add_field(name=f"{EMOJI_PROFILE_LOSSES} Поражения", value=f"**{stats['losses']}**", inline=True)
        streak, best_streak = models.get_win_streak_info(target.id)
        embed.add_field(name="🔥 Серия", value=f"**{streak}** (рек. {best_streak})", inline=True)
        if calib_5 or calib_1:
            embed.add_field(name=f"{EMOJI_KILLS} Убийств", value=f"**{kills}**", inline=True)
            embed.add_field(name=f"{EMOJI_DEATHS} Смертей", value=f"**{deaths}**", inline=True)
            embed.add_field(name=f"{EMOJI_ASSISTS} Ассистов", value=f"**{assists}**", inline=True)
        if stats['fav_position']:
            pos_names = {1: "Carry", 2: "Mid", 3: "Offlane", 4: "Sup 4", 5: "Sup 5"}
            embed.add_field(name="⭐ Позиция", value=f"**{pos_names.get(stats['fav_position'], '—')}**", inline=True)
        if roles:
            embed.add_field(name="🎭 Роли", value=" ".join([f"<@&{r['role_id']}>" for r in roles]), inline=False)
        embed.set_footer(text=f"ID: {target.id}")
        await ctx.respond(embed=embed)

    @discord.slash_command(name="leaderboard", description="Топ по ZXC", guild_ids=[GUILD_ID])
    async def leaderboard(self, ctx: discord.ApplicationContext, mode: str = "5x5"):
        if mode not in ("5x5", "1x1"):
            return await ctx.respond("Укажите 5x5 или 1x1", ephemeral=True)
        conn = models.get_connection()
        zxc_col = "zxc_5x5" if mode == "5x5" else "zxc_1x1"
        calib_col = "calibration_5x5" if mode == "5x5" else "calibration_1x1"
        rows = conn.execute(
            f"SELECT discord_id, {zxc_col}, {calib_col} FROM players WHERE {calib_col} >= 5 ORDER BY {zxc_col} DESC LIMIT 15"
        ).fetchall()
        conn.close()
        if not rows:
            return await ctx.respond(f"📊 Нет откалиброванных игроков в {mode}.", ephemeral=True)
        embed = discord.Embed(title=f"🏆 ZXC {mode}", color=0x2c2f33)
        text = ""
        for i, row in enumerate(rows, 1):
            rating = row[zxc_col] or 1000
            _, _, emoji = models.get_zxc_rating(row['discord_id'], mode)
            text += f"**{i}.** {emoji} <@{row['discord_id']}> — {rating} ZXC\n"
        embed.description = text
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(Inventory(bot))
