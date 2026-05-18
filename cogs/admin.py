import discord
from discord.ext import commands

from config import GUILD_ID, ADMIN_CHANNEL_ID
from database import models


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="integrity_config", description="Пороги антиабуза (админ)", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def integrity_config(self, ctx: discord.ApplicationContext):
        from config import (
            INTEGRITY_MIN_MAPPED_PLAYERS,
            INTEGRITY_MIN_DEATHS_5X5,
            INTEGRITY_MIN_DEATHS_1X1,
            INTEGRITY_MAX_KDA_FEED,
            INTEGRITY_BLOWOUT_SCORE_DIFF,
            INTEGRITY_BLOWOUT_MAX_MINUTES,
            MATCH_LOG_CHANNEL_ID,
            FEED_PENALTY_POINTS,
            MVP_BONUS_POINTS,
        )
        await ctx.defer(ephemeral=True)
        embed = discord.Embed(title="🛡️ Антиабуз", color=0x2c2f33)
        embed.add_field(name="Мин. привязанных игроков GSI", value=str(INTEGRITY_MIN_MAPPED_PLAYERS), inline=True)
        embed.add_field(name="Смертей для фида 5x5", value=str(INTEGRITY_MIN_DEATHS_5X5), inline=True)
        embed.add_field(name="Смертей для фида 1x1", value=str(INTEGRITY_MIN_DEATHS_1X1), inline=True)
        embed.add_field(name="Порог KDA фида", value=str(INTEGRITY_MAX_KDA_FEED), inline=True)
        embed.add_field(name="Разгром (счёт)", value=str(INTEGRITY_BLOWOUT_SCORE_DIFF), inline=True)
        embed.add_field(name="Разгром (мин)", value=str(INTEGRITY_BLOWOUT_MAX_MINUTES), inline=True)
        embed.add_field(name="Штраф за фид", value=str(FEED_PENALTY_POINTS), inline=True)
        embed.add_field(name="MVP бонус", value=str(MVP_BONUS_POINTS), inline=True)
        log_ch = f"<#{MATCH_LOG_CHANNEL_ID}>" if MATCH_LOG_CHANNEL_ID else "не задан"
        embed.add_field(name="Канал логов", value=log_ch, inline=False)
        await ctx.followup.send(embed=embed, ephemeral=True)

    @discord.slash_command(name="player_flags", description="Статистика игрока для модерации", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def player_flags(self, ctx: discord.ApplicationContext, player: discord.Member):
        await ctx.defer(ephemeral=True)
        p = models.get_player(player.id)
        if not p:
            return await ctx.followup.send("Игрок не найден в БД.", ephemeral=True)
        embed = discord.Embed(title=f"🔍 {player.display_name}", color=0x2c2f33)
        embed.add_field(name="Dota ник", value=p.get("dota_name") or "не привязан", inline=True)
        embed.add_field(name="Очки", value=str(p.get("points", 0)), inline=True)
        embed.add_field(name="Серия побед", value=str(p.get("win_streak", 0)), inline=True)
    embed.add_field(name="W/L", value=f"{p.get('wins', 0)}/{p.get('losses', 0)}", inline=True)
    k, d, a = models.get_player_kda(player.id)
    embed.add_field(name="K/D/A", value=f"{k}/{d}/{a}", inline=True)
        await ctx.followup.send(embed=embed, ephemeral=True)
        admin_ch = self.bot.get_channel(ADMIN_CHANNEL_ID)
        if admin_ch:
            await admin_ch.send(f"📎 Модератор {ctx.author.mention} проверил {player.mention}")


def setup(bot):
    bot.add_cog(Admin(bot))
