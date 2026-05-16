import discord
from discord.ext import commands
from database import models
from config import GUILD_ID

EMBED_COLOR = 0x2c2f33
CLAN_CREATE_COST = 500

class ClanInviteView(discord.ui.View):
    def __init__(self, clan_name, clan_tag, clan_id, inviter_id, target_id):
        super().__init__(timeout=120)
        self.clan_name = clan_name
        self.clan_tag = clan_tag
        self.clan_id = clan_id
        self.inviter_id = inviter_id
        self.target_id = target_id

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.green)
    async def accept(self, button, interaction):
        if interaction.user.id != self.target_id:
            return await interaction.response.send_message("<:no:1503121885674868938> Не тебя приглашали!", ephemeral=True)
        models.get_or_create_player(self.target_id, interaction.user.name)
        conn = models.get_connection()
        check = conn.execute("SELECT clan_id FROM clan_members WHERE discord_id = ?", (self.target_id,)).fetchone()
        if check:
            conn.close()
            return await interaction.response.send_message("<:no:1503121885674868938> Ты уже в клане!", ephemeral=True)
        conn.execute("INSERT INTO clan_members (clan_id, discord_id) VALUES (?, ?)", (self.clan_id, self.target_id))
        conn.commit()
        chat_id = conn.execute("SELECT chat_id FROM clans WHERE id = ?", (self.clan_id,)).fetchone()["chat_id"]
        conn.close()
        if chat_id:
            guild = interaction.guild
            member = guild.get_member(self.target_id)
            channel = guild.get_channel(chat_id)
            if member and channel:
                await channel.set_permissions(member, read_messages=True, send_messages=True)
        await interaction.response.edit_message(content=f"<:yes:1503121926128664766> {interaction.user.mention} вступил в клан **[{self.clan_tag}] {self.clan_name}**!", view=None)

    @discord.ui.button(label="Отказаться", style=discord.ButtonStyle.red)
    async def decline(self, button, interaction):
        if interaction.user.id != self.target_id:
            return await interaction.response.send_message("<:no:1503121885674868938> Не тебя приглашали!", ephemeral=True)
        await interaction.response.edit_message(content=f"<:no:1503121885674868938> {interaction.user.mention} отказался.", view=None)

class ClanManageView(discord.ui.View):
    def __init__(self, clan_id, owner_id):
        super().__init__(timeout=None)
        self.clan_id = clan_id
        self.owner_id = owner_id

    @discord.ui.button(label="Аватар", style=discord.ButtonStyle.grey, emoji="<:avatar:1503137354414559263>", row=0)
    async def avatar_btn(self, button, interaction):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("<:no:1503121885674868938> Только владелец!", ephemeral=True)
        await interaction.response.send_modal(AvatarModal(self.clan_id))

    @discord.ui.button(label="Баннер", style=discord.ButtonStyle.grey, emoji="<:banner:1503137566063333376>", row=0)
    async def banner_btn(self, button, interaction):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("<:no:1503121885674868938> Только владелец!", ephemeral=True)
        await interaction.response.send_modal(BannerModal(self.clan_id))

    @discord.ui.button(label="Описание", style=discord.ButtonStyle.grey, emoji="<:description:1503137742991786074>", row=0)
    async def desc_btn(self, button, interaction):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("<:no:1503121885674868938> Только владелец!", ephemeral=True)
        await interaction.response.send_modal(DescriptionModal(self.clan_id))

    @discord.ui.button(label="Роль", style=discord.ButtonStyle.grey, emoji="<:role:1503137642060058754>", row=1)
    async def role_btn(self, button, interaction):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("<:no:1503121885674868938> Только владелец!", ephemeral=True)
        await interaction.response.send_modal(RoleModal(self.clan_id))

    @discord.ui.button(label="Удалить клан", style=discord.ButtonStyle.grey, emoji="<:no:1503121885674868938>", row=1)
    async def delete_btn(self, button, interaction):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("<:no:1503121885674868938> Только владелец!", ephemeral=True)
        await interaction.response.send_modal(DeleteClanModal(self.clan_id))

class AvatarModal(discord.ui.Modal):
    def __init__(self, clan_id):
        super().__init__(title="Установить аватар")
        self.clan_id = clan_id
        self.add_item(discord.ui.InputText(label="URL аватара", placeholder="https://i.imgur.com/..."))

    async def callback(self, interaction):
        conn = models.get_connection()
        conn.execute("UPDATE clans SET avatar = ? WHERE id = ?", (self.children[0].value, self.clan_id))
        conn.commit()
        conn.close()
        await interaction.response.send_message("<:yes:1503121926128664766> Аватар обновлён!", ephemeral=True)

class BannerModal(discord.ui.Modal):
    def __init__(self, clan_id):
        super().__init__(title="Установить баннер")
        self.clan_id = clan_id
        self.add_item(discord.ui.InputText(label="URL баннера", placeholder="https://i.imgur.com/..."))

    async def callback(self, interaction):
        conn = models.get_connection()
        conn.execute("UPDATE clans SET banner = ? WHERE id = ?", (self.children[0].value, self.clan_id))
        conn.commit()
        conn.close()
        await interaction.response.send_message("<:yes:1503121926128664766> Баннер обновлён!", ephemeral=True)

class DescriptionModal(discord.ui.Modal):
    def __init__(self, clan_id):
        super().__init__(title="Описание клана")
        self.clan_id = clan_id
        self.add_item(discord.ui.InputText(label="Описание", style=discord.InputTextStyle.long, max_length=500))

    async def callback(self, interaction):
        conn = models.get_connection()
        conn.execute("UPDATE clans SET description = ? WHERE id = ?", (self.children[0].value, self.clan_id))
        conn.commit()
        conn.close()
        await interaction.response.send_message("<:yes:1503121926128664766> Описание обновлено!", ephemeral=True)

class RoleModal(discord.ui.Modal):
    def __init__(self, clan_id):
        super().__init__(title="Назначить роль")
        self.clan_id = clan_id
        self.add_item(discord.ui.InputText(label="ID участника", placeholder="727489809068851281"))
        self.add_item(discord.ui.InputText(label="Роль", placeholder="Mid Player", max_length=30))

    async def callback(self, interaction):
        try:
            target_id = int(self.children[0].value)
        except:
            return await interaction.response.send_message("<:no:1503121885674868938> Неверный ID!", ephemeral=True)
        conn = models.get_connection()
        conn.execute("UPDATE clan_members SET role = ? WHERE clan_id = ? AND discord_id = ?", 
                     (self.children[1].value, self.clan_id, target_id))
        conn.commit()
        conn.close()
        await interaction.response.send_message("<:yes:1503121926128664766> Роль обновлена!", ephemeral=True)

class DeleteClanModal(discord.ui.Modal):
    def __init__(self, clan_id):
        super().__init__(title="Удалить клан")
        self.clan_id = clan_id
        self.add_item(discord.ui.InputText(label="Напишите DELETE для подтверждения", placeholder="DELETE"))

    async def callback(self, interaction):
        if self.children[0].value != "DELETE":
            return await interaction.response.send_message("<:no:1503121885674868938> Подтверждение неверно.", ephemeral=True)
        conn = models.get_connection()
        chat_id = conn.execute("SELECT chat_id FROM clans WHERE id = ?", (self.clan_id,)).fetchone()["chat_id"]
        if chat_id:
            channel = interaction.guild.get_channel(chat_id)
            if channel:
                await channel.delete()
        conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (self.clan_id,))
        conn.execute("DELETE FROM clans WHERE id = ?", (self.clan_id,))
        conn.commit()
        conn.close()
        await interaction.response.send_message("<:yes:1503121926128664766> Клан удалён.", ephemeral=True)

class Clans(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _get_clan_tag(self, discord_id: int) -> str:
        conn = models.get_connection()
        row = conn.execute("SELECT c.tag FROM clans c JOIN clan_members cm ON c.id = cm.clan_id WHERE cm.discord_id = ?", (discord_id,)).fetchone()
        conn.close()
        return f"[{row['tag']}]" if row else ""

    @discord.slash_command(name="clan_create", description="Создать клан (500 очков)", guild_ids=[GUILD_ID])
    async def clan_create(self, ctx, name: str, tag: str):
        if len(tag) > 5:
            return await ctx.respond("<:no:1503121885674868938> Тег не длиннее 5 символов!", ephemeral=True)
        models.get_or_create_player(ctx.author.id, ctx.author.name)
        player = models.get_player(ctx.author.id)
        if not player or player["points"] < CLAN_CREATE_COST:
            return await ctx.respond(f"<:no:1503121885674868938> Недостаточно очков! Нужно: **{CLAN_CREATE_COST}**", ephemeral=True)
        conn = models.get_connection()
        row = conn.execute("SELECT clan_id FROM clan_members WHERE discord_id = ?", (ctx.author.id,)).fetchone()
        if row:
            conn.close()
            return await ctx.respond("<:no:1503121885674868938> Вы уже в клане!", ephemeral=True)
        name_check = conn.execute("SELECT id FROM clans WHERE name = ?", (name,)).fetchone()
        if name_check:
            conn.close()
            return await ctx.respond("<:no:1503121885674868938> Название занято!", ephemeral=True)
        tag_check = conn.execute("SELECT id FROM clans WHERE tag = ?", (tag,)).fetchone()
        if tag_check:
            conn.close()
            return await ctx.respond("<:no:1503121885674868938> Тег занят!", ephemeral=True)
        # создание клана — не матч, статистику wins/losses не трогаем
        models.add_points(ctx.author.id, -CLAN_CREATE_COST, count_match=False)
        guild = ctx.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(f"clan-{tag}", overwrites=overwrites, topic=f"Клановый чат [{tag}] {name}")
        conn.execute("INSERT INTO clans (name, tag, owner_id, chat_id) VALUES (?, ?, ?, ?)", (name, tag, ctx.author.id, channel.id))
        conn.commit()
        clan_id = conn.execute("SELECT id FROM clans WHERE owner_id = ?", (ctx.author.id,)).fetchone()["id"]
        conn.execute("INSERT INTO clan_members (clan_id, discord_id) VALUES (?, ?)", (clan_id, ctx.author.id))
        conn.commit()
        conn.close()
        await ctx.respond(f"<:yes:1503121926128664766> Клан **[{tag}] {name}** создан! Канал: {channel.mention}")

    @discord.slash_command(name="clan_invite", description="Пригласить в клан", guild_ids=[GUILD_ID])
    async def clan_invite(self, ctx, member: discord.Member):
        conn = models.get_connection()
        row = conn.execute("SELECT c.id, c.name, c.tag, c.owner_id FROM clans c JOIN clan_members cm ON c.id = cm.clan_id WHERE cm.discord_id = ?", (ctx.author.id,)).fetchone()
        if not row:
            conn.close()
            return await ctx.respond("<:no:1503121885674868938> Вы не в клане!", ephemeral=True)
        if row["owner_id"] != ctx.author.id:
            conn.close()
            return await ctx.respond("<:no:1503121885674868938> Только владелец!", ephemeral=True)
        check = conn.execute("SELECT clan_id FROM clan_members WHERE discord_id = ?", (member.id,)).fetchone()
        if check:
            conn.close()
            return await ctx.respond("<:no:1503121885674868938> Игрок уже в клане!", ephemeral=True)
        conn.close()
        view = ClanInviteView(row["name"], row["tag"], row["id"], ctx.author.id, member.id)
        await ctx.send(f"{member.mention}, приглашение в **[{row['tag']}] {row['name']}**!", view=view)
        await ctx.respond("<:yes:1503121926128664766> Приглашение отправлено.", ephemeral=True)

    @discord.slash_command(name="clan_kick", description="Выгнать из клана", guild_ids=[GUILD_ID])
    async def clan_kick(self, ctx, member: discord.Member):
        if member.id == ctx.author.id:
            return await ctx.respond("<:no:1503121885674868938> Нельзя выгнать себя!", ephemeral=True)
        conn = models.get_connection()
        row = conn.execute("SELECT c.id, c.name, c.owner_id, c.chat_id FROM clans c JOIN clan_members cm ON c.id = cm.clan_id WHERE cm.discord_id = ?", (ctx.author.id,)).fetchone()
        if not row:
            conn.close()
            return await ctx.respond("<:no:1503121885674868938> Вы не в клане!", ephemeral=True)
        if row["owner_id"] != ctx.author.id:
            conn.close()
            return await ctx.respond("<:no:1503121885674868938> Только владелец!", ephemeral=True)
        check = conn.execute("SELECT 1 FROM clan_members WHERE clan_id = ? AND discord_id = ?", (row["id"], member.id)).fetchone()
        if not check:
            conn.close()
            return await ctx.respond("<:no:1503121885674868938> Игрок не в клане!", ephemeral=True)
        conn.execute("DELETE FROM clan_members WHERE clan_id = ? AND discord_id = ?", (row["id"], member.id))
        conn.commit()
        conn.close()
        if row["chat_id"]:
            channel = ctx.guild.get_channel(row["chat_id"])
            if channel:
                await channel.set_permissions(member, overwrite=None)
        await ctx.respond(f"👢 {member.mention} выгнан из **{row['name']}**.")

    @discord.slash_command(name="clan_leave", description="Выйти из клана", guild_ids=[GUILD_ID])
    async def clan_leave(self, ctx):
        conn = models.get_connection()
        row = conn.execute("SELECT c.id, c.name, c.owner_id, c.chat_id FROM clans c JOIN clan_members cm ON c.id = cm.clan_id WHERE cm.discord_id = ?", (ctx.author.id,)).fetchone()
        if not row:
            conn.close()
            return await ctx.respond("<:no:1503121885674868938> Вы не в клане!", ephemeral=True)
        if row["owner_id"] == ctx.author.id:
            conn.close()
            return await ctx.respond("<:no:1503121885674868938> Владелец не может выйти.", ephemeral=True)
        conn.execute("DELETE FROM clan_members WHERE clan_id = ? AND discord_id = ?", (row["id"], ctx.author.id))
        conn.commit()
        conn.close()
        if row["chat_id"]:
            channel = ctx.guild.get_channel(row["chat_id"])
            if channel:
                await channel.set_permissions(ctx.author, overwrite=None)
        await ctx.respond(f"<:yes:1503121926128664766> Вы вышли из **{row['name']}**.")

    @discord.slash_command(name="clan_info", description="Информация о клане", guild_ids=[GUILD_ID])
    async def clan_info(self, ctx):
        conn = models.get_connection()
        row = conn.execute("SELECT c.*, (SELECT COUNT(*) FROM clan_members WHERE clan_id = c.id) as member_count FROM clans c JOIN clan_members cm ON c.id = cm.clan_id WHERE cm.discord_id = ?", (ctx.author.id,)).fetchone()
        if not row:
            conn.close()
            return await ctx.respond("<:no:1503121885674868938> Вы не в клане!", ephemeral=True)
        members = conn.execute("SELECT discord_id, role FROM clan_members WHERE clan_id = ?", (row["id"],)).fetchall()
        rank_row = conn.execute("SELECT COUNT(*) + 1 FROM clans WHERE wins > ?", (row["wins"],)).fetchone()
        clan_rank = rank_row[0] if rank_row else 1
        conn.close()
        owner = self.bot.get_user(row["owner_id"])
        embed = discord.Embed(title=f"[{row['tag']}] {row['name']}", color=EMBED_COLOR)
        if row["description"]:
            embed.description = row["description"]
        if row["avatar"]:
            embed.set_thumbnail(url=row["avatar"])
        if row["banner"]:
            embed.set_image(url=row["banner"])
        embed.add_field(name="<:leader:1503017771871637685> Владелец", value=owner.mention if owner else "—", inline=True)
        embed.add_field(name="<:winrate:1502718521275187200> Статистика", value=f"Побед: {row['wins']}\nПоражений: {row['losses']}", inline=True)
        embed.add_field(name="<:members:1503017912619896924> Участников", value=str(row["member_count"]), inline=True)
        embed.add_field(name="<:kubok:1502711350689005740> Рейтинг кланов", value=f"**#{clan_rank}** место", inline=True)
        member_list = []
        for m in members:
            role_text = f" — *{m['role']}*" if m['role'] else ""
            member_list.append(f"<@{m['discord_id']}>{role_text}")
        embed.add_field(name="<:structure:1503018072137662586> Состав", value="\n".join(member_list), inline=False)
        view = ClanManageView(row["id"], row["owner_id"]) if ctx.author.id == row["owner_id"] else None
        await ctx.respond(embed=embed, view=view)

    @discord.slash_command(name="clans_top", description="Топ кланов", guild_ids=[GUILD_ID])
    async def clans_top(self, ctx):
        conn = models.get_connection()
        rows = conn.execute("SELECT name, tag, wins, losses, avatar FROM clans ORDER BY wins DESC LIMIT 10").fetchall()
        conn.close()
        if not rows:
            return await ctx.respond("Нет кланов.", ephemeral=True)
        embed = discord.Embed(title="<:kubok:1502711350689005740> Сезонный рейтинг кланов", color=EMBED_COLOR)
        text = ""
        for i, r in enumerate(rows, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{emoji} **[{r['tag']}] {r['name']}** — {r['wins']}W/{r['losses']}L\n"
        embed.description = text
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(Clans(bot))
