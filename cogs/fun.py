import os
import random
from datetime import timedelta

import discord
from discord.ext import commands

from database import models
from config import GUILD_ID


def _format_left(seconds_left: int) -> str:
    # округляем в читаемый вид (часы/минуты)
    td = timedelta(seconds=seconds_left)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if hours <= 0:
        return f"{minutes} мин."
    return f"{hours} ч. {minutes} мин."


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _reply(self, ctx: discord.ApplicationContext, content: str, *, ephemeral: bool = False):
        """
        Безопасный ответ на slash-команду.
        На хостингах/под нагрузкой Discord может пометить interaction как истёкший -> Unknown interaction.
        Поэтому используем defer + followup.
        """
        try:
            # если уже ответили/задеферили — просто followup
            if hasattr(ctx, "interaction") and ctx.interaction and ctx.interaction.response.is_done():
                return await ctx.followup.send(content, ephemeral=ephemeral)
            return await ctx.respond(content, ephemeral=ephemeral)
        except Exception:
            # fallback на followup (если respond уже невалиден)
            try:
                return await ctx.followup.send(content, ephemeral=ephemeral)
            except Exception:
                return

    @discord.slash_command(name="daily", description="Ежедневный бонус (1 раз в 24 часа)", guild_ids=[GUILD_ID])
    async def daily(self, ctx: discord.ApplicationContext):
        # чтобы Discord не писал "Приложение не отвечает" на медленном диске/БД — сразу defer
        await ctx.defer(ephemeral=True)
        try:
            reward = int(os.getenv("DAILY_REWARD", "15"))
        except Exception:
            reward = 15

        try:
            models.get_or_create_player(ctx.author.id, ctx.author.name)
            ok, left = models.can_claim_daily(ctx.author.id)
            if not ok:
                return await self._reply(ctx, f"⏳ Вы уже получали daily. Следующий через **{_format_left(left)}**.", ephemeral=True)

            models.claim_daily(ctx.author.id, reward)
            player = models.get_player(ctx.author.id)
            await self._reply(ctx, f"<:yes:1503121926128664766> Daily: **+{reward}** очков! Теперь у вас: **{player['points']}**", ephemeral=True)
        except Exception as e:
            await self._reply(ctx, f"⚠️ Ошибка daily: `{e}`", ephemeral=True)

    @discord.slash_command(name="sync", description="Синхронизировать slash-команды (админ)", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def sync(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        try:
            guild = self.bot.get_guild(GUILD_ID) or ctx.guild
            gid = guild.id if guild else None
            if not gid:
                return await self._reply(ctx, "⚠️ Не удалось определить сервер (guild).", ephemeral=True)
            await self.bot.sync_commands(guild_ids=[gid])
            await self._reply(ctx, "<:yes:1503121926128664766> Команды синхронизированы. Подожди 1–2 минуты и проверь /daily.", ephemeral=True)
        except Exception as e:
            await self._reply(ctx, f"⚠️ Sync ошибка: `{e}`", ephemeral=True)

    @discord.slash_command(name="coinflip", description="Подбросить монетку", guild_ids=[GUILD_ID])
    async def coinflip(self, ctx: discord.ApplicationContext):
        try:
            await ctx.defer()
        except Exception:
            # если interaction уже истёк — просто попробуем ответить как получится
            pass
        res = random.choice(["Орёл", "Решка"])
        await self._reply(ctx, f"🪙 {res}")

    @discord.slash_command(name="roll", description="Случайное число", guild_ids=[GUILD_ID])
    async def roll(self, ctx: discord.ApplicationContext, max_value: int = 100):
        try:
            await ctx.defer()
        except Exception:
            pass
        if max_value < 2 or max_value > 1000000:
            return await self._reply(ctx, "Укажите max_value от 2 до 1 000 000.", ephemeral=True)
        num = random.randint(1, max_value)
        await self._reply(ctx, f"🎲 Выпало: **{num}** (1–{max_value})")

    @discord.slash_command(name="choose", description="Выбрать случайный вариант (разделяй варианты через | )", guild_ids=[GUILD_ID])
    async def choose(self, ctx: discord.ApplicationContext, options: str):
        await ctx.defer()
        parts = [p.strip() for p in options.split("|") if p.strip()]
        if len(parts) < 2:
            return await self._reply(ctx, "Нужно минимум 2 варианта. Пример: `пудж | инвокер | джагер`", ephemeral=True)
        pick = random.choice(parts)
        await self._reply(ctx, f"✅ Выбираю: **{pick}**")

    @discord.slash_command(name="8ball", description="Шар предсказаний", guild_ids=[GUILD_ID])
    async def eightball(self, ctx: discord.ApplicationContext, question: str):
        await ctx.defer()
        answers = [
            "Да.",
            "Нет.",
            "Скорее да.",
            "Скорее нет.",
            "Точно!",
            "Не думаю.",
            "Спроси позже.",
            "Шансы хорошие.",
            "Шансы плохие.",
            "50/50.",
        ]
        await self._reply(ctx, f"🎱 Вопрос: *{question}*\nОтвет: **{random.choice(answers)}**")


def setup(bot):
    bot.add_cog(Fun(bot))
