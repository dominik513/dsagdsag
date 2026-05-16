import discord
from discord.ext import commands
from database import models
from config import GUILD_ID

class RolesShop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="add_shop_role", description="Добавить роль в магазин", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def add_shop_role(self, ctx: discord.ApplicationContext, role: discord.Role, price: int, description: str = None):
        item_id = models.add_shop_item("role", role.name, price, description, role.id)
        await ctx.respond(f"<:yes:1503121926128664766> Роль {role.mention} добавлена в магазин (ID товара: {item_id}, цена: {price})", ephemeral=True)

    @discord.slash_command(name="add_shop_dota_plus", description="Добавить Dota Plus в магазин", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def add_shop_dota_plus(self, ctx: discord.ApplicationContext, name: str, price: int, description: str = None):
        item_id = models.add_shop_item("dota_plus", name, price, description)
        await ctx.respond(f"<:yes:1503121926128664766> Dota Plus '{name}' добавлен в магазин (ID товара: {item_id}, цена: {price})", ephemeral=True)

    @discord.slash_command(name="add_shop_item", description="Добавить предмет в магазин", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def add_shop_item(self, ctx: discord.ApplicationContext, name: str, price: int, description: str = None):
        item_id = models.add_shop_item("item", name, price, description)
        await ctx.respond(f"<:yes:1503121926128664766> Предмет '{name}' добавлен в магазин (ID товара: {item_id}, цена: {price})", ephemeral=True)

    @discord.slash_command(name="remove_shop_item", description="Убрать товар из магазина", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def remove_shop_item(self, ctx: discord.ApplicationContext, item_id: int):
        models.delete_shop_item(item_id)
        await ctx.respond(f"<:yes:1503121926128664766> Товар #{item_id} убран из магазина.", ephemeral=True)

    @discord.slash_command(name="points_add", description="Выдать очки игроку", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def points_add(self, ctx: discord.ApplicationContext, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.respond("<:no:1503121885674868938> Укажите amount > 0.", ephemeral=True)
        models.get_or_create_player(member.id, member.name)
        models.add_points(member.id, amount, count_match=False)
        player = models.get_player(member.id)
        await ctx.respond(f"<:yes:1503121926128664766> Выдано **{amount}** очков игроку {member.mention}. Теперь: **{player['points']}**", ephemeral=True)

    @discord.slash_command(name="points_take", description="Списать очки у игрока", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def points_take(self, ctx: discord.ApplicationContext, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.respond("<:no:1503121885674868938> Укажите amount > 0.", ephemeral=True)
        models.get_or_create_player(member.id, member.name)
        models.add_points(member.id, -amount, count_match=False)
        player = models.get_player(member.id)
        await ctx.respond(f"<:yes:1503121926128664766> Списано **{amount}** очков у {member.mention}. Теперь: **{player['points']}**", ephemeral=True)

    @discord.slash_command(name="points_set", description="Установить точное число очков игроку", guild_ids=[GUILD_ID])
    @commands.has_permissions(administrator=True)
    async def points_set(self, ctx: discord.ApplicationContext, member: discord.Member, amount: int):
        if amount < 0:
            return await ctx.respond("<:no:1503121885674868938> amount не может быть < 0.", ephemeral=True)
        models.get_or_create_player(member.id, member.name)
        models.set_points(member.id, amount)
        await ctx.respond(f"<:yes:1503121926128664766> Установлено **{amount}** очков игроку {member.mention}.", ephemeral=True)

def setup(bot):
    bot.add_cog(RolesShop(bot))
