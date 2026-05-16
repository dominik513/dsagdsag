import discord
from discord.ext import commands
from database import models
from config import REQUESTS_CHANNEL_ID, GUILD_ID

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _reply(self, ctx: discord.ApplicationContext, *args, **kwargs):
        """
        Безопасный ответ на slash-команду.
        Если interaction истёк (Unknown interaction) — не роняем команду.
        """
        try:
            # если уже ответили/задеферили — используем followup
            if hasattr(ctx, "interaction") and ctx.interaction and ctx.interaction.response.is_done():
                return await ctx.followup.send(*args, **kwargs)
            return await ctx.respond(*args, **kwargs)
        except Exception:
            try:
                return await ctx.followup.send(*args, **kwargs)
            except Exception:
                return

    @discord.slash_command(name="shop", description="Открыть магазин наград", guild_ids=[GUILD_ID])
    async def shop(self, ctx: discord.ApplicationContext):
        # ВАЖНО: сначала acknowledge, потом БД, иначе Discord может дать 10062 Unknown interaction
        try:
            await ctx.defer(ephemeral=True)
        except Exception:
            pass
        items = models.get_shop_items()
        if not items:
            await self._reply(ctx, "🛒 Магазин пуст.", ephemeral=True)
            return
        roles = [i for i in items if i["type"] == "role"]
        dota_plus = [i for i in items if i["type"] == "dota_plus"]
        other_items = [i for i in items if i["type"] == "item"]
        embed = discord.Embed(title="🛒 Магазин наград", color=0xf1c40f)
        if roles:
            roles_text = "\n".join([f"**#{r['id']} — {r['name']}** — {r['price']} очков" for r in roles])
            embed.add_field(name="🎭 Роли Discord", value=roles_text, inline=False)
        if dota_plus:
            dp_text = "\n".join([f"**#{d['id']} — {d['name']}** — {d['price']} очков" for d in dota_plus])
            embed.add_field(name="✨ Dota Plus", value=dp_text, inline=False)
        if other_items:
            oi_text = "\n".join([f"**#{i['id']} — {i['name']}** — {i['price']} очков" for i in other_items])
            embed.add_field(name="🎁 Предметы", value=oi_text, inline=False)
        embed.set_footer(text="/buy <id> для покупки")
        await self._reply(ctx, embed=embed, ephemeral=True)

    @discord.slash_command(name="buy", description="Купить товар", guild_ids=[GUILD_ID])
    async def buy(self, ctx: discord.ApplicationContext, item_id: int):
        try:
            await ctx.defer(ephemeral=True)
        except Exception:
            pass
        item = models.get_shop_item(item_id)
        if not item:
            await self._reply(ctx, "<:no:1503121885674868938> Товар не найден.", ephemeral=True)
            return
        player = models.get_player(ctx.author.id)
        if not player:
            await self._reply(ctx, "<:no:1503121885674868938> Вы не участвовали в турнирах.", ephemeral=True)
            return
        if player["points"] < item["price"]:
            await self._reply(ctx, f"<:no:1503121885674868938> Недостаточно очков! У вас: {player['points']}, нужно: {item['price']}", ephemeral=True)
            return
        if item["type"] == "role":
            if models.has_player_role(ctx.author.id, item["role_id"]):
                await self._reply(ctx, "<:no:1503121885674868938> У вас уже есть эта роль!", ephemeral=True)
                return
            # покупка роли — не матч, статистику wins/losses не трогаем
            models.add_points(ctx.author.id, -item["price"], count_match=False)
            guild = self.bot.get_guild(ctx.guild.id)
            role = guild.get_role(item["role_id"])
            if role:
                try:
                    await ctx.author.add_roles(role)
                except discord.Forbidden:
                    models.add_points(ctx.author.id, item["price"], count_match=False)
                    await self._reply(ctx, "⚠️ Не удалось выдать роль. Очки возвращены.", ephemeral=True)
                    return
            models.add_player_role(ctx.author.id, item["role_id"], item["name"])
            await self._reply(ctx, f"<:yes:1503121926128664766> Вы купили роль **{item['name']}** за {item['price']} очков!", ephemeral=True)
        elif item["type"] in ("dota_plus", "item"):
            # заявка на награду — не матч, статистику wins/losses не трогаем
            models.add_points(ctx.author.id, -item["price"], count_match=False)
            req_id = models.create_request(ctx.author.id, item_id, f"Заявка на {item['name']}")
            requests_channel = self.bot.get_channel(REQUESTS_CHANNEL_ID)
            if requests_channel:
                embed = discord.Embed(
                    title=f"📩 Заявка #{req_id}",
                    description=f"Игрок: {ctx.author.mention}\nТовар: **{item['name']}**\nЦена: {item['price']} очков",
                    color=0x9b59b6
                )
                await requests_channel.send(embed=embed)
            await self._reply(ctx, f"<:yes:1503121926128664766> Заявка на **{item['name']}** создана!", ephemeral=True)

    @discord.slash_command(name="pending_requests", description="Необработанные заявки", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def pending_requests(self, ctx: discord.ApplicationContext):
        try:
            await ctx.defer(ephemeral=True)
        except Exception:
            pass
        requests = models.get_pending_requests()
        if not requests:
            await self._reply(ctx, "<:yes:1503121926128664766> Нет заявок.", ephemeral=True)
            return
        embed = discord.Embed(title="📋 Заявки", color=0xf39c12)
        for req in requests[:25]:
            embed.add_field(
                name=f"#{req['id']} — {req['username']}",
                value=f"Товар: **{req['item_name']}**\nДата: {req['created_at']}",
                inline=False
            )
        await self._reply(ctx, embed=embed, ephemeral=True)

    @discord.slash_command(name="approve_request", description="Одобрить заявку", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def approve_request(self, ctx: discord.ApplicationContext, request_id: int):
        try:
            await ctx.defer(ephemeral=True)
        except Exception:
            pass
        models.resolve_request(request_id, "approved", f"Одобрено {ctx.author.name}")
        await self._reply(ctx, f"<:yes:1503121926128664766> Заявка #{request_id} одобрена!", ephemeral=True)

    @discord.slash_command(name="reject_request", description="Отклонить заявку", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def reject_request(self, ctx: discord.ApplicationContext, request_id: int, reason: str = None):
        try:
            await ctx.defer(ephemeral=True)
        except Exception:
            pass
        models.resolve_request(request_id, "rejected", reason or "Отклонено")
        await self._reply(ctx, f"<:no:1503121885674868938> Заявка #{request_id} отклонена.", ephemeral=True)

def setup(bot):
    bot.add_cog(Shop(bot))
