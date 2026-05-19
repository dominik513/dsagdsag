"""Развлечения и удержание: бонусы, азарт, дуэли, топы."""
from __future__ import annotations

import random

import discord
from discord.ext import commands

from database import models
from config import (
    GUILD_ID,
    WEEKLY_REWARD,
    LUCKY_COOLDOWN_HOURS,
    LUCKY_MIN,
    LUCKY_MAX,
    LUCKY_JACKPOT,
    LUCKY_JACKPOT_CHANCE,
    ACTIVITY_BASE_REWARD,
    ACTIVITY_STREAK_CAP,
    GAMBLE_MIN,
    GAMBLE_MAX,
    GAMBLE_COOLDOWN_SEC,
    GAMBLE_PAYOUT_MULT,
    DUEL_MIN,
    DUEL_MAX,
    DUEL_TIMEOUT_SEC,
    EMOJI_POINTS,
)

DOTA_HEROES_FUN = [
    "Pudge", "Invoker", "Shadow Fiend", "Juggernaut", "Crystal Maiden",
    "Anti-Mage", "Axe", "Queen of Pain", "Tinker", "Morphling",
    "Earthshaker", "Storm Spirit", "Lina", "Sniper", "Techies",
]

EMBED_COLOR = 0x5865F2


def _format_left(seconds_left: int) -> str:
    hours = seconds_left // 3600
    minutes = (seconds_left % 3600) // 60
    if hours <= 0:
        return f"{minutes} мин."
    return f"{hours} ч. {minutes} мин."


class DuelView(discord.ui.View):
    def __init__(self, cog: "Engagement", challenger_id: int, target_id: int, amount: int):
        super().__init__(timeout=DUEL_TIMEOUT_SEC)
        self.cog = cog
        self.challenger_id = challenger_id
        self.target_id = target_id
        self.amount = amount
        self.resolved = False

    async def _finish(self, interaction: discord.Interaction, accepted: bool):
        if self.resolved:
            return
        if interaction.user.id != self.target_id:
            return await interaction.response.send_message(
                "<:no:1503121885674868938> Это не ваш вызов!",
                ephemeral=True,
            )
        self.resolved = True
        self.stop()
        self.cog.pending_duels.pop(self.target_id, None)

        if not accepted:
            embed = discord.Embed(
                title="⚔️ Дуэль отклонена",
                description=f"<@{self.target_id}> отказался от дуэли на **{self.amount}** очков.",
                color=0xE74C3C,
            )
            await interaction.response.edit_message(embed=embed, view=None)
            return

        await interaction.response.defer()
        models.get_or_create_player(self.challenger_id, str(self.challenger_id))
        models.get_or_create_player(self.target_id, str(self.target_id))
        p1 = models.get_player(self.challenger_id)
        p2 = models.get_player(self.target_id)
        if not p1 or p1["points"] < self.amount:
            return await interaction.followup.edit_message(
                content="<:no:1503121885674868938> У вызывающего не хватает очков.",
                view=None,
            )
        if not p2 or p2["points"] < self.amount:
            return await interaction.followup.edit_message(
                content="<:no:1503121885674868938> У вас не хватает очков для дуэли.",
                view=None,
            )

        models.add_points(self.challenger_id, -self.amount, count_match=False)
        models.add_points(self.target_id, -self.amount, count_match=False)
        roll_c = random.randint(1, 100)
        roll_t = random.randint(1, 100)
        if roll_c >= roll_t:
            winner, loser = self.challenger_id, self.target_id
        else:
            winner, loser = self.target_id, self.challenger_id
        pot = self.amount * 2
        models.add_points(winner, pot, count_match=False)
        models.record_duel_result(winner, loser)

        embed = discord.Embed(title="⚔️ Дуэль завершена!", color=0x43B581)
        embed.add_field(
            name="Бросок",
            value=f"<@{self.challenger_id}>: **{roll_c}**\n<@{self.target_id}>: **{roll_t}**",
            inline=True,
        )
        embed.add_field(
            name="Победитель",
            value=f"<@{winner}> забирает **{pot}** {EMOJI_POINTS}",
            inline=True,
        )
        await interaction.followup.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.green)
    async def accept(self, button, interaction):
        await self._finish(interaction, True)

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.red)
    async def decline(self, button, interaction):
        await self._finish(interaction, False)


class Engagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_duels: dict[int, dict] = {}

    async def _reply(self, ctx: discord.ApplicationContext, content: str = None, *, embed=None, ephemeral: bool = False):
        try:
            if ctx.interaction.response.is_done():
                return await ctx.followup.send(content=content, embed=embed, ephemeral=ephemeral)
            return await ctx.respond(content=content, embed=embed, ephemeral=ephemeral)
        except Exception:
            try:
                return await ctx.followup.send(content=content, embed=embed, ephemeral=ephemeral)
            except Exception:
                return

    @discord.slash_command(name="weekly", description="Еженедельный бонус (раз в 7 дней)", guild_ids=[GUILD_ID])
    async def weekly(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        models.get_or_create_player(ctx.author.id, ctx.author.name)
        ok, left = models.claim_weekly(ctx.author.id, WEEKLY_REWARD)
        if not ok:
            return await self._reply(
                ctx,
                f"⏳ Weekly уже получен. Следующий через **{_format_left(left)}**.",
                ephemeral=True,
            )
        player = models.get_player(ctx.author.id)
        await self._reply(
            ctx,
            f"<:yes:1503121926128664766> Weekly: **+{WEEKLY_REWARD}** очков!\n"
            f"Баланс: **{player['points']}** {EMOJI_POINTS}",
            ephemeral=True,
        )

    @discord.slash_command(name="lucky", description="Лутбокс очков (кулдаун 12ч)", guild_ids=[GUILD_ID])
    async def lucky(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        models.get_or_create_player(ctx.author.id, ctx.author.name)
        cd = LUCKY_COOLDOWN_HOURS * 3600
        ok, left, amount, jackpot = models.claim_lucky(
            ctx.author.id,
            cooldown_seconds=cd,
            min_reward=LUCKY_MIN,
            max_reward=LUCKY_MAX,
            jackpot=LUCKY_JACKPOT,
            jackpot_chance_percent=LUCKY_JACKPOT_CHANCE,
        )
        if not ok:
            return await self._reply(
                ctx,
                f"⏳ Лутбокс на кулдауне. Через **{_format_left(left)}**.",
                ephemeral=True,
            )
        player = models.get_player(ctx.author.id)
        extra = " 🎰 **ДЖЕКПОТ!**" if jackpot else ""
        await self._reply(
            ctx,
            f"🎁 Выпало: **+{amount}** очков!{extra}\nБаланс: **{player['points']}**",
            ephemeral=True,
        )

    @discord.slash_command(name="activity", description="Серия активности — заходи каждый день", guild_ids=[GUILD_ID])
    async def activity(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        models.get_or_create_player(ctx.author.id, ctx.author.name)
        ok, left, streak, reward = models.claim_activity_streak(
            ctx.author.id,
            base_reward=ACTIVITY_BASE_REWARD,
            streak_cap=ACTIVITY_STREAK_CAP,
        )
        if not ok:
            cur, best, claimed = models.get_activity_streak_info(ctx.author.id)
            return await self._reply(
                ctx,
                f"⏳ Уже забрали сегодня.\n"
                f"Серия: **{cur}** (рекорд **{best}**)\n"
                f"Следующий бонус через **{_format_left(left)}**.",
                ephemeral=True,
            )
        player = models.get_player(ctx.author.id)
        await self._reply(
            ctx,
            f"📅 День **{streak}** подряд! +**{reward}** очков\n"
            f"Баланс: **{player['points']}** {EMOJI_POINTS}\n"
            f"_Не пропускайте дни — бонус растёт!_",
            ephemeral=True,
        )

    @discord.slash_command(name="gamble", description="Ставка 50/50 — удвоить очки (почти)", guild_ids=[GUILD_ID])
    async def gamble(self, ctx: discord.ApplicationContext, amount: int):
        await ctx.defer(ephemeral=True)
        if amount < GAMBLE_MIN or amount > GAMBLE_MAX:
            return await self._reply(
                ctx,
                f"<:no:1503121885674868938> Ставка от **{GAMBLE_MIN}** до **{GAMBLE_MAX}**.",
                ephemeral=True,
            )
        models.get_or_create_player(ctx.author.id, ctx.author.name)
        ok, msg, _delta = models.play_gamble(
            ctx.author.id,
            amount,
            cooldown_seconds=GAMBLE_COOLDOWN_SEC,
            payout_mult=GAMBLE_PAYOUT_MULT,
        )
        player = models.get_player(ctx.author.id)
        if not ok:
            return await self._reply(ctx, f"<:no:1503121885674868938> {msg}", ephemeral=True)
        await self._reply(
            ctx,
            f"{'<:yes:1503121926128664766>' if 'Победа' in msg else '<:no:1503121885674868938>'} {msg}\n"
            f"Баланс: **{player['points']}**",
            ephemeral=True,
        )

    @discord.slash_command(name="duel", description="Вызвать на дуэль за очки", guild_ids=[GUILD_ID])
    async def duel(self, ctx: discord.ApplicationContext, opponent: discord.Member, amount: int):
        if opponent.bot or opponent.id == ctx.author.id:
            return await ctx.respond("<:no:1503121885674868938> Некорректный соперник.", ephemeral=True)
        if amount < DUEL_MIN or amount > DUEL_MAX:
            return await ctx.respond(
                f"<:no:1503121885674868938> Ставка от **{DUEL_MIN}** до **{DUEL_MAX}**.",
                ephemeral=True,
            )
        if opponent.id in self.pending_duels:
            return await ctx.respond("<:no:1503121885674868938> У игрока уже есть вызов.", ephemeral=True)
        models.get_or_create_player(ctx.author.id, ctx.author.name)
        player = models.get_player(ctx.author.id)
        if not player or player["points"] < amount:
            return await ctx.respond("<:no:1503121885674868938> Недостаточно очков.", ephemeral=True)

        embed = discord.Embed(
            title="⚔️ Вызов на дуэль!",
            description=(
                f"<@{ctx.author.id}> вызывает <@{opponent.id}>!\n\n"
                f"Ставка: **{amount}** {EMOJI_POINTS} с каждого\n"
                f"Победитель забирает **{amount * 2}** очков."
            ),
            color=EMBED_COLOR,
        )
        embed.set_footer(text=f"Ответ в течение {DUEL_TIMEOUT_SEC} сек.")
        view = DuelView(self, ctx.author.id, opponent.id, amount)
        await ctx.respond(f"{opponent.mention}", embed=embed, view=view)
        self.pending_duels[opponent.id] = {
            "challenger": ctx.author.id,
            "amount": amount,
        }

    @discord.slash_command(name="leaderboard", description="Топ игроков сервера", guild_ids=[GUILD_ID])
    async def leaderboard(
        self,
        ctx: discord.ApplicationContext,
        category: str = discord.Option(
            choices=["points", "wins", "streak", "zxc"],
            description="Категория",
            default="points",
        ),
    ):
        await ctx.defer()
        titles = {
            "points": f"{EMOJI_POINTS} Топ по очкам",
            "wins": "🏆 Топ по победам",
            "streak": "🔥 Топ по серии",
            "zxc": "📈 Топ ZXC 5x5",
        }
        rows = models.get_leaderboard(category, 10)
        embed = discord.Embed(title=titles.get(category, "Топ"), color=EMBED_COLOR)
        if not rows:
            embed.description = "Пока пусто."
        else:
            lines = []
            for i, r in enumerate(rows, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
                if category == "points":
                    val = r.get("points", 0)
                elif category == "wins":
                    val = f"{r.get('wins', 0)} W"
                elif category == "streak":
                    val = f"{r.get('win_streak', 0)} (рек. {r.get('best_win_streak', 0)})"
                else:
                    val = r.get("zxc_5x5", 1000)
                lines.append(f"{medal} <@{r['discord_id']}> — **{val}**")
            embed.description = "\n".join(lines)
        await self._reply(ctx, embed=embed)

    @discord.slash_command(name="compare", description="Сравнить статистику с игроком", guild_ids=[GUILD_ID])
    async def compare(self, ctx: discord.ApplicationContext, member: discord.Member):
        await ctx.defer(ephemeral=True)
        models.get_or_create_player(ctx.author.id, ctx.author.name)
        models.get_or_create_player(member.id, member.name)
        a = models.get_player(ctx.author.id)
        b = models.get_player(member.id)
        if not a or not b:
            return await self._reply(ctx, "Нет данных.", ephemeral=True)

        def wr(p):
            t = (p.get("wins") or 0) + (p.get("losses") or 0)
            return round((p.get("wins") or 0) / t * 100, 1) if t else 0.0

        embed = discord.Embed(title=f"📊 {ctx.author.display_name} vs {member.display_name}", color=EMBED_COLOR)
        embed.add_field(
            name=ctx.author.display_name,
            value=(
                f"{EMOJI_POINTS} **{a.get('points', 0)}**\n"
                f"🏆 {a.get('wins', 0)}W / {a.get('losses', 0)}L ({wr(a)}%)\n"
                f"ZXC 5x5: **{a.get('zxc_5x5', 1000)}**"
            ),
            inline=True,
        )
        embed.add_field(
            name=member.display_name,
            value=(
                f"{EMOJI_POINTS} **{b.get('points', 0)}**\n"
                f"🏆 {b.get('wins', 0)}W / {b.get('losses', 0)}L ({wr(b)}%)\n"
                f"ZXC 5x5: **{b.get('zxc_5x5', 1000)}**"
            ),
            inline=True,
        )
        diff = (a.get("points") or 0) - (b.get("points") or 0)
        embed.set_footer(text=f"Разница в очках: {diff:+d}")
        await self._reply(ctx, embed=embed, ephemeral=True)

    @discord.slash_command(name="achievements", description="Ваши достижения", guild_ids=[GUILD_ID])
    async def achievements(self, ctx: discord.ApplicationContext, member: discord.Member = None):
        await ctx.defer(ephemeral=True)
        target = member or ctx.author
        models.get_or_create_player(target.id, target.name)
        badges = models.get_player_achievements(target.id)
        embed = discord.Embed(
            title=f"🏅 Достижения — {target.display_name}",
            description="\n".join(f"• {b}" for b in badges),
            color=EMBED_COLOR,
        )
        p = models.get_player(target.id)
        if p:
            embed.add_field(
                name="Статистика",
                value=(
                    f"Матчей: **{p.get('tournaments', 0)}** | "
                    f"Дуэли: **{p.get('duel_wins', 0)}**W / **{p.get('duel_losses', 0)}**L"
                ),
                inline=False,
            )
        await self._reply(ctx, embed=embed, ephemeral=True)

    @discord.slash_command(name="random_hero", description="Случайный герой на игру", guild_ids=[GUILD_ID])
    async def random_hero(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        hero = random.choice(DOTA_HEROES_FUN)
        await self._reply(ctx, f"🎲 Сегодня играй: **{hero}**!")

    @discord.slash_command(name="rps", description="Камень-ножницы-бумага с игроком", guild_ids=[GUILD_ID])
    async def rps(self, ctx: discord.ApplicationContext, opponent: discord.Member):
        if opponent.bot or opponent.id == ctx.author.id:
            return await ctx.respond("<:no:1503121885674868938> Некорректный соперник.", ephemeral=True)
        choices = {"камень": "🪨", "ножницы": "✂️", "бумага": "📄"}
        a, b = random.choice(list(choices.keys())), random.choice(list(choices.keys()))
        if a == b:
            result = "Ничья!"
        elif (a, b) in (("камень", "ножницы"), ("ножницы", "бумага"), ("бумага", "камень")):
            result = f"Победил {ctx.author.mention}!"
        else:
            result = f"Победил {opponent.mention}!"
        await ctx.respond(
            f"{choices[a]} **{ctx.author.display_name}**: {a}\n"
            f"{choices[b]} **{opponent.display_name}**: {b}\n\n"
            f"**{result}**"
        )

    @discord.slash_command(name="fun_help", description="Все развлекательные команды", guild_ids=[GUILD_ID])
    async def fun_help(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(
            title="🎮 Развлечения и бонусы",
            description="Команды, чтобы не скучать и копить очки:",
            color=EMBED_COLOR,
        )
        embed.add_field(
            name="💰 Бонусы",
            value=(
                "`/daily` — раз в 24ч\n"
                "`/weekly` — раз в 7 дней\n"
                "`/lucky` — лутбокс (12ч)\n"
                "`/activity` — серия заходов"
            ),
            inline=False,
        )
        embed.add_field(
            name="🎲 Азарт и PvP",
            value=(
                "`/gamble` — ставка 50/50\n"
                "`/duel` — дуэль с игроком\n"
                "`/rps` — камень-ножницы-бумага\n"
                "`/coinflip` `/roll` `/8ball`"
            ),
            inline=False,
        )
        embed.add_field(
            name="📊 Социальное",
            value=(
                "`/leaderboard` — топы\n"
                "`/compare` — сравнить с другом\n"
                "`/achievements` — достижения\n"
                "`/tip` — перевод очков"
            ),
            inline=False,
        )
        embed.add_field(
            name="🎯 Dota",
            value="`/random_hero` — рандом герой\n`/streak` `/lastmatch`",
            inline=False,
        )
        embed.set_footer(text="Играйте турниры — больше очков и достижений!")
        await ctx.respond(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(Engagement(bot))
