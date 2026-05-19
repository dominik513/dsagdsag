from __future__ import annotations

import json

import discord
from discord.ext import commands

from config import GUILD_ID, ADMIN_CHANNEL_ID
from database import models


def _admin_only():
    return commands.has_permissions(administrator=True)


def _mention(user: discord.User) -> str:
    return user.mention


def _player_embed(p: dict, user: discord.User = None) -> discord.Embed:
    title = user.display_name if user else p.get("username", str(p["discord_id"]))
    embed = discord.Embed(title=f"📋 Игрок: {title}", color=0x2C2F33)
    embed.add_field(name="Discord ID", value=str(p["discord_id"]), inline=False)
    embed.add_field(name="Очки", value=str(p.get("points", 0)), inline=True)
    embed.add_field(name="W / L / Матчей", value=f"{p.get('wins', 0)} / {p.get('losses', 0)} / {p.get('tournaments', 0)}", inline=True)
    embed.add_field(name="Серия / Рекорд", value=f"{p.get('win_streak', 0)} / {p.get('best_win_streak', 0)}", inline=True)
    embed.add_field(name="ZXC 5x5", value=f"{p.get('zxc_5x5', 1000)} (калиб {p.get('calibration_5x5', 0)}/5)", inline=True)
    embed.add_field(name="ZXC 1x1", value=f"{p.get('zxc_1x1', 1000)} (калиб {p.get('calibration_1x1', 0)}/5)", inline=True)
    embed.add_field(name="Dota ник", value=p.get("dota_name") or "—", inline=True)
    steam = p.get("steam_id")
    if steam:
        embed.add_field(
            name="Steam",
            value=f"[профиль](https://steamcommunity.com/profiles/{steam})",
            inline=True,
        )
    embed.add_field(
        name="K/D/A",
        value=f"{p.get('total_kills', 0)} / {p.get('total_deaths', 0)} / {p.get('total_assists', 0)}",
        inline=True,
    )
    return embed


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _defer_ok(self, ctx: discord.ApplicationContext):
        try:
            await ctx.defer(ephemeral=True)
        except Exception:
            pass

    @discord.slash_command(name="integrity_config", description="Пороги антиабуза (админ)", guild_ids=[GUILD_ID])
    @_admin_only()
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
        await self._defer_ok(ctx)
        embed = discord.Embed(title="🛡️ Антиабуз", color=0x2C2F33)
        embed.add_field(name="Мин. привязанных GSI", value=str(INTEGRITY_MIN_MAPPED_PLAYERS), inline=True)
        embed.add_field(name="Смертей фид 5x5", value=str(INTEGRITY_MIN_DEATHS_5X5), inline=True)
        embed.add_field(name="Смертей фид 1x1", value=str(INTEGRITY_MIN_DEATHS_1X1), inline=True)
        embed.add_field(name="Порог KDA фида", value=str(INTEGRITY_MAX_KDA_FEED), inline=True)
        embed.add_field(name="Разгром (счёт)", value=str(INTEGRITY_BLOWOUT_SCORE_DIFF), inline=True)
        embed.add_field(name="Разгром (мин)", value=str(INTEGRITY_BLOWOUT_MAX_MINUTES), inline=True)
        embed.add_field(name="Штраф за фид", value=str(FEED_PENALTY_POINTS), inline=True)
        embed.add_field(name="MVP бонус", value=str(MVP_BONUS_POINTS), inline=True)
        log_ch = f"<#{MATCH_LOG_CHANNEL_ID}>" if MATCH_LOG_CHANNEL_ID else "не задан"
        embed.add_field(name="Канал логов", value=log_ch, inline=False)
        await ctx.followup.send(embed=embed, ephemeral=True)

    @discord.slash_command(name="adm_player", description="[Админ] Полная карточка игрока в БД", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_player(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — нажмите и выберите из списка @"),
    ):
        await self._defer_ok(ctx)
        p = models.get_player_full(user.id)
        if not p:
            models.get_or_create_player(user.id, user.name)
            p = models.get_player_full(user.id)
        await ctx.followup.send(embed=_player_embed(p, user), ephemeral=True)

    @discord.slash_command(name="adm_set_points", description="[Админ] Установить очки", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_set_points(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
        amount: discord.Option(int, description="Очки", min_value=0),
    ):
        await self._defer_ok(ctx)
        models.get_or_create_player(user.id, user.name)
        models.set_points(user.id, amount)
        await ctx.followup.send(f"✅ {_mention(user)} — **{amount}** очков.", ephemeral=True)

    @discord.slash_command(name="adm_set_wl", description="[Админ] Победы / поражения / матчи", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_set_wl(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
        wins: discord.Option(int, description="Победы", required=False, min_value=0),
        losses: discord.Option(int, description="Поражения", required=False, min_value=0),
        tournaments: discord.Option(int, description="Всего матчей", required=False, min_value=0),
    ):
        await self._defer_ok(ctx)
        models.get_or_create_player(user.id, user.name)
        fields = {}
        if wins is not None:
            fields["wins"] = max(0, wins)
        if losses is not None:
            fields["losses"] = max(0, losses)
        if tournaments is not None:
            fields["tournaments"] = max(0, tournaments)
        if not fields:
            return await ctx.followup.send("Укажите хотя бы wins, losses или tournaments.", ephemeral=True)
        models.admin_update_player(user.id, **fields)
        p = models.get_player_full(user.id)
        await ctx.followup.send(
            f"✅ {_mention(user)}: W **{p['wins']}** L **{p['losses']}** матчей **{p['tournaments']}**",
            ephemeral=True,
        )

    @discord.slash_command(name="adm_add_wl", description="[Админ] Добавить победы/поражения/матчи", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_add_wl(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — нажмите поле и выберите @ник"),
        wins: discord.Option(int, description="Добавить побед", default=0, min_value=0),
        losses: discord.Option(int, description="Добавить поражений", default=0, min_value=0),
        tournaments: discord.Option(int, description="Добавить матчей", default=0, min_value=0),
    ):
        await self._defer_ok(ctx)
        models.get_or_create_player(user.id, user.name)
        models.admin_add_win_loss(user.id, wins=wins, losses=losses, tournaments=tournaments)
        p = models.get_player_full(user.id)
        await ctx.followup.send(
            f"✅ {_mention(user)}: +{wins}W +{losses}L +{tournaments}матчей → W **{p['wins']}** L **{p['losses']}**",
            ephemeral=True,
        )

    @discord.slash_command(
        name="adm_add_wl_id",
        description="[Админ] W/L по Discord ID (если нет в списке @)",
        guild_ids=[GUILD_ID],
    )
    @_admin_only()
    async def adm_add_wl_id(
        self,
        ctx: discord.ApplicationContext,
        user_id: discord.Option(str, description="Discord ID (ПКМ профиль → Копировать ID)"),
        wins: discord.Option(int, description="Добавить побед", default=0, min_value=0),
        losses: discord.Option(int, description="Добавить поражений", default=0, min_value=0),
        tournaments: discord.Option(int, description="Добавить матчей", default=0, min_value=0),
    ):
        await self._defer_ok(ctx)
        try:
            uid = int(user_id.strip())
        except ValueError:
            return await ctx.followup.send("user_id должен быть числом.", ephemeral=True)
        models.get_or_create_player(uid, str(uid))
        models.admin_add_win_loss(uid, wins=wins, losses=losses, tournaments=tournaments)
        p = models.get_player_full(uid)
        await ctx.followup.send(
            f"✅ <@{uid}>: +{wins}W +{losses}L → W **{p['wins']}** L **{p['losses']}**",
            ephemeral=True,
        )

    @discord.slash_command(name="adm_set_rank", description="[Админ] Выдать ранг по названию (Pulse, Золото…)", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_set_rank(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
        rank: discord.Option(str, description="Pulse, Vein, Золото, Титан…"),
        mode: discord.Option(str, description="5x5 или 1x1", default="1x1"),
        finish_calibration: discord.Option(bool, description="Сразу 5/5 калибровка", default=True),
    ):
        await self._defer_ok(ctx)
        if mode not in ("5x5", "1x1"):
            return await ctx.followup.send("mode: **5x5** или **1x1**", ephemeral=True)
        rating = models.rating_for_rank(rank, mode)
        if rating is None:
            names = ", ".join(models.list_rank_names(mode))
            return await ctx.followup.send(f"Неизвестный ранг. Для {mode}: {names}", ephemeral=True)
        models.get_or_create_player(user.id, user.name)
        key = "zxc_5x5" if mode == "5x5" else "zxc_1x1"
        models.admin_update_player(user.id, **{key: rating})
        if finish_calibration:
            models.admin_finish_calibration(user.id, mode)
        rname, _, emoji = models.get_zxc_rating(user.id, mode)
        await ctx.followup.send(
            f"✅ {_mention(user)} **{mode}** → ранг **{rname}** {emoji}\n"
            f"ZXC: **{rating}**" + (" | калибровка 5/5" if finish_calibration else ""),
            ephemeral=True,
        )

    @discord.slash_command(name="adm_set_zxc", description="[Админ] Рейтинг ZXC (число)", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_set_zxc(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
        rating: discord.Option(int, description="ZXC 0–3000", min_value=0, max_value=3000),
        mode: discord.Option(str, description="5x5 или 1x1", default="5x5"),
    ):
        await self._defer_ok(ctx)
        if mode not in ("5x5", "1x1"):
            return await ctx.followup.send("mode: 5x5 или 1x1", ephemeral=True)
        rating = max(0, min(3000, rating))
        models.get_or_create_player(user.id, user.name)
        key = "zxc_5x5" if mode == "5x5" else "zxc_1x1"
        models.admin_update_player(user.id, **{key: rating})
        await ctx.followup.send(f"✅ {_mention(user)} {mode}: **{rating}** ZXC", ephemeral=True)

    @discord.slash_command(name="adm_set_kda", description="[Админ] Суммарный K/D/A", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_set_kda(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
        kills: discord.Option(int, description="Убийства", min_value=0),
        deaths: discord.Option(int, description="Смерти", min_value=0),
        assists: discord.Option(int, description="Ассисты", min_value=0),
    ):
        await self._defer_ok(ctx)
        models.get_or_create_player(user.id, user.name)
        models.admin_update_player(
            user.id,
            total_kills=max(0, kills),
            total_deaths=max(0, deaths),
            total_assists=max(0, assists),
        )
        await ctx.followup.send(f"✅ K/D/A {_mention(user)}: **{kills}/{deaths}/{assists}**", ephemeral=True)

    @discord.slash_command(name="adm_calib_set", description="[Админ] Калибровка 0–5", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_calib_set(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
        value: discord.Option(int, description="0–5", min_value=0, max_value=5),
        mode: discord.Option(str, description="5x5 или 1x1", default="5x5"),
    ):
        await self._defer_ok(ctx)
        if mode not in ("5x5", "1x1"):
            return await ctx.followup.send("mode: 5x5 или 1x1", ephemeral=True)
        models.get_or_create_player(user.id, user.name)
        models.admin_set_calibration(user.id, mode, value)
        await ctx.followup.send(f"✅ {_mention(user)} калибровка {mode} → **{max(0, min(5, value))}/5**", ephemeral=True)

    @discord.slash_command(name="adm_calib_reset", description="[Админ] Сбросить калибровку (0/5)", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_calib_reset(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
        mode: discord.Option(str, description="5x5, 1x1 или both", default="both"),
    ):
        await self._defer_ok(ctx)
        models.get_or_create_player(user.id, user.name)
        models.admin_reset_calibration(user.id, mode)
        await ctx.followup.send(f"✅ Калибровка сброшена ({mode}) для {_mention(user)}", ephemeral=True)

    @discord.slash_command(name="adm_calib_done", description="[Админ] Отметить калибровку завершённой (5/5)", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_calib_done(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
        mode: discord.Option(str, description="5x5 или 1x1", default="5x5"),
    ):
        await self._defer_ok(ctx)
        if mode not in ("5x5", "1x1"):
            return await ctx.followup.send("mode: 5x5 или 1x1", ephemeral=True)
        models.get_or_create_player(user.id, user.name)
        models.admin_finish_calibration(user.id, mode)
        await ctx.followup.send(f"✅ {_mention(user)} — калибровка {mode} **5/5**", ephemeral=True)

    @discord.slash_command(name="adm_set_streak", description="[Админ] Серия побед", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_set_streak(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
        streak: discord.Option(int, description="Текущая серия", min_value=0),
        best: discord.Option(int, description="Рекорд серии", required=False, min_value=0),
    ):
        await self._defer_ok(ctx)
        models.get_or_create_player(user.id, user.name)
        fields = {"win_streak": max(0, streak)}
        if best is not None:
            fields["best_win_streak"] = max(0, best)
        models.admin_update_player(user.id, **fields)
        await ctx.followup.send(f"✅ Серия {_mention(user)}: **{streak}**", ephemeral=True)

    @discord.slash_command(name="adm_set_dota", description="[Админ] Dota-ник игрока", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_set_dota(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
        dota_name: discord.Option(str, description="Ник в Dota 2"),
    ):
        await self._defer_ok(ctx)
        models.get_or_create_player(user.id, user.name)
        models.set_player_dota_name(user.id, dota_name.strip())
        await ctx.followup.send(f"✅ Dota-ник {_mention(user)}: **{dota_name.strip()}**", ephemeral=True)

    @discord.slash_command(name="adm_reset_player", description="[Админ] Сброс статистики игрока", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_reset_player(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
        keep_points: discord.Option(bool, description="Сохранить очки?", default=True),
    ):
        await self._defer_ok(ctx)
        if not models.get_player(user.id):
            models.get_or_create_player(user.id, user.name)
        models.admin_reset_player_stats(user.id, keep_points=keep_points)
        msg = "очки сохранены" if keep_points else "включая очки"
        await ctx.followup.send(f"✅ Статистика {_mention(user)} сброшена ({msg}).", ephemeral=True)

    @discord.slash_command(name="adm_delete_player", description="[Админ] Удалить игрока из БД", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_delete_player(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
    ):
        await self._defer_ok(ctx)
        models.admin_delete_player(user.id)
        await ctx.followup.send(f"🗑️ Игрок {_mention(user)} удалён из БД.", ephemeral=True)

    @discord.slash_command(name="adm_export", description="[Админ] Экспорт данных игрока (JSON)", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_export(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
    ):
        await self._defer_ok(ctx)
        snap = models.export_player_snapshot(user.id)
        if not snap:
            return await ctx.followup.send("Игрок не найден.", ephemeral=True)
        text = json.dumps(snap, ensure_ascii=False, indent=2)
        if len(text) > 1900:
            text = text[:1900] + "\n..."
        await ctx.followup.send(f"```json\n{text}\n```\nСкопируйте для `/adm_import`", ephemeral=True)

    @discord.slash_command(name="adm_import", description="[Админ] Импорт JSON (восстановление)", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_import(self, ctx: discord.ApplicationContext, json_data: str):
        await self._defer_ok(ctx)
        try:
            data = json.loads(json_data.strip())
            if "discord_id" not in data:
                return await ctx.followup.send("В JSON нужен discord_id.", ephemeral=True)
            models.import_player_snapshot(data)
            p = models.get_player_full(int(data["discord_id"]))
            await ctx.followup.send(
                embed=_player_embed(p),
                content=f"✅ Импорт для <@{data['discord_id']}>",
                ephemeral=True,
            )
        except json.JSONDecodeError as e:
            await ctx.followup.send(f"❌ Неверный JSON: {e}", ephemeral=True)

    @discord.slash_command(name="adm_matches", description="[Админ] Список последних турниров", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_matches(self, ctx: discord.ApplicationContext, limit: int = 10):
        await self._defer_ok(ctx)
        limit = max(1, min(25, limit))
        rows = models.admin_list_tournaments(limit)
        if not rows:
            return await ctx.followup.send("Турниров нет.", ephemeral=True)
        lines = []
        for r in rows:
            reason = r.get("void_reason") or r.get("cancel_reason") or ""
            extra = f" ({reason[:40]})" if reason else ""
            lines.append(f"**#{r['id']}** `{r['status']}` winner={r.get('winner') or '—'}{extra}")
        embed = discord.Embed(title=f"Последние {len(rows)} турниров", description="\n".join(lines), color=0x5865F2)
        await ctx.followup.send(embed=embed, ephemeral=True)

    @discord.slash_command(name="adm_delete_match", description="[Админ] Удалить турнир по ID", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_delete_match(self, ctx: discord.ApplicationContext, tournament_id: int):
        await self._defer_ok(ctx)
        if models.admin_delete_tournament(tournament_id):
            await ctx.followup.send(f"✅ Турнир **#{tournament_id}** удалён.", ephemeral=True)
        else:
            await ctx.followup.send(f"Турнир **#{tournament_id}** не найден.", ephemeral=True)

    @discord.slash_command(name="adm_clear_logs", description="[Админ] Очистить логи матчей", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_clear_logs(self, ctx: discord.ApplicationContext, confirm: str):
        await self._defer_ok(ctx)
        if confirm.lower() != "да":
            return await ctx.followup.send("Напишите confirm=`да` для подтверждения.", ephemeral=True)
        n = models.admin_clear_match_logs()
        await ctx.followup.send(f"✅ Удалено записей логов: **{n}**", ephemeral=True)

    @discord.slash_command(name="adm_clear_tournaments", description="[Админ] Удалить ВСЕ турниры и логи", guild_ids=[GUILD_ID])
    @_admin_only()
    async def adm_clear_tournaments(self, ctx: discord.ApplicationContext, confirm: str):
        await self._defer_ok(ctx)
        if confirm.lower() != "удалить":
            return await ctx.followup.send("Напишите confirm=`удалить` для подтверждения.", ephemeral=True)
        n = models.admin_clear_all_tournaments()
        await ctx.followup.send(f"✅ Удалено турниров: **{n}** (логи и участники матчей тоже).", ephemeral=True)

    @discord.slash_command(name="player_flags", description="Краткая карточка игрока (мод)", guild_ids=[GUILD_ID])
    @_admin_only()
    async def player_flags(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.User, name="user", description="Игрок — выберите @ник из списка"),
    ):
        await self._defer_ok(ctx)
        p = models.get_player_full(user.id)
        if not p:
            return await ctx.followup.send("Игрок не найден в БД.", ephemeral=True)
        await ctx.followup.send(embed=_player_embed(p, user), ephemeral=True)
        admin_ch = self.bot.get_channel(ADMIN_CHANNEL_ID)
        if admin_ch:
            await admin_ch.send(f"📎 Модератор {ctx.author.mention} проверил {_mention(user)}")


def setup(bot):
    bot.add_cog(Admin(bot))
