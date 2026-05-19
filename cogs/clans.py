from __future__ import annotations

import discord
from discord.ext import commands
from database import models
from database.models import ClanError
from config import (
    GUILD_ID,
    CLAN_XP_PER_100_DEPOSIT,
    CLAN_LEVEL_XP_BASE,
    EMOJI_POINTS,
)

EMBED_COLOR = 0x2c2f33
CLAN_CREATE_COST = 500
ROLE_HINT = "Роли: **Участник**, **Офицер**, **Казначей** (снимают из казны), **Владелец**"

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
        conn.execute("DELETE FROM clan_treasury_log WHERE clan_id = ?", (self.clan_id,))
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
        conn.execute(
            "INSERT INTO clan_members (clan_id, discord_id, role) VALUES (?, ?, ?)",
            (clan_id, ctx.author.id, "Владелец"),
        )
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
        treasury = row["treasury"] if row["treasury"] is not None else 0
        level = row["level"] if row["level"] is not None else 1
        xp = row["xp"] if row["xp"] is not None else 0
        embed.add_field(name="<:winrate:1502718521275187200> Статистика", value=f"Побед: {row['wins']}\nПоражений: {row['losses']}", inline=True)
        embed.add_field(
            name=f"{EMOJI_POINTS} Казна",
            value=f"**{treasury}** очков\nУровень **{level}** ({xp} XP)",
            inline=True,
        )
        embed.add_field(name="<:members:1503017912619896924> Участников", value=str(row["member_count"]), inline=True)
        embed.add_field(name="<:kubok:1502711350689005740> Рейтинг кланов", value=f"**#{clan_rank}** место", inline=True)
        embed.set_footer(text="Казна: /clan_deposit · /clan_bank · " + ROLE_HINT[:80])
        member_list = []
        for m in members:
            role_text = f" — *{m['role']}*" if m['role'] else ""
            member_list.append(f"<@{m['discord_id']}>{role_text}")
        embed.add_field(name="<:structure:1503018072137662586> Состав", value="\n".join(member_list), inline=False)
        view = ClanManageView(row["id"], row["owner_id"]) if ctx.author.id == row["owner_id"] else None
        await ctx.respond(embed=embed, view=view)

    @discord.slash_command(name="clans_top", description="Топ кланов", guild_ids=[GUILD_ID])
    async def clans_top(
        self,
        ctx: discord.ApplicationContext,
        sort_by: str = discord.Option(
            choices=["wins", "treasury", "level"],
            description="Сортировка",
            default="wins",
        ),
    ):
        order = {
            "wins": "wins DESC, treasury DESC",
            "treasury": "treasury DESC, wins DESC",
            "level": "level DESC, xp DESC",
        }.get(sort_by, "wins DESC")
        conn = models.get_connection()
        rows = conn.execute(
            f"SELECT name, tag, wins, losses, treasury, level, avatar FROM clans ORDER BY {order} LIMIT 10"
        ).fetchall()
        conn.close()
        if not rows:
            return await ctx.respond("Нет кланов.", ephemeral=True)
        titles = {"wins": "по победам", "treasury": "по казне", "level": "по уровню"}
        embed = discord.Embed(
            title=f"<:kubok:1502711350689005740> Топ кланов ({titles.get(sort_by, '')})",
            color=EMBED_COLOR,
        )
        text = ""
        for i, r in enumerate(rows, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            extra = f" · {r['treasury'] or 0}💰 · ур.{r['level'] or 1}"
            text += f"{emoji} **[{r['tag']}] {r['name']}** — {r['wins']}W/{r['losses']}L{extra}\n"
        embed.description = text
        await ctx.respond(embed=embed)

    @discord.slash_command(name="clan_deposit", description="Вложить очки в казну клана", guild_ids=[GUILD_ID])
    async def clan_deposit(self, ctx: discord.ApplicationContext, amount: int):
        await ctx.defer(ephemeral=True)
        try:
            models.get_or_create_player(ctx.author.id, ctx.author.name)
            res = models.clan_deposit(
                ctx.author.id,
                amount,
                xp_base=CLAN_LEVEL_XP_BASE,
                xp_per_100=CLAN_XP_PER_100_DEPOSIT,
            )
            await ctx.followup.send(
                f"<:yes:1503121926128664766> В казну: **+{amount}**.\n"
                f"Казна: **{res['treasury']}** · Уровень **{res['level']}**",
                ephemeral=True,
            )
        except ClanError as e:
            await ctx.followup.send(f"<:no:1503121885674868938> {e}", ephemeral=True)

    @discord.slash_command(name="clan_withdraw", description="Снять из казны (владелец/офицер)", guild_ids=[GUILD_ID])
    async def clan_withdraw(self, ctx: discord.ApplicationContext, amount: int):
        await ctx.defer(ephemeral=True)
        try:
            res = models.clan_withdraw(ctx.author.id, amount)
            await ctx.followup.send(
                f"<:yes:1503121926128664766> Снято **{amount}** на ваш счёт.\nКазна: **{res['treasury']}**",
                ephemeral=True,
            )
        except ClanError as e:
            await ctx.followup.send(f"<:no:1503121885674868938> {e}", ephemeral=True)

    @discord.slash_command(name="clan_pay", description="Выплата из казны участнику (владелец)", guild_ids=[GUILD_ID])
    async def clan_pay(self, ctx: discord.ApplicationContext, member: discord.Member, amount: int):
        await ctx.defer(ephemeral=True)
        try:
            models.get_or_create_player(member.id, member.name)
            res = models.clan_pay_member(ctx.author.id, member.id, amount)
            await ctx.followup.send(
                f"<:yes:1503121926128664766> {member.mention} получил **{amount}** из казны.\n"
                f"Остаток: **{res['treasury']}**",
                ephemeral=True,
            )
        except ClanError as e:
            await ctx.followup.send(f"<:no:1503121885674868938> {e}", ephemeral=True)

    @discord.slash_command(name="clan_bank", description="Казна и последние операции", guild_ids=[GUILD_ID])
    async def clan_bank(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        clan = models.get_clan_membership(ctx.author.id)
        if not clan:
            return await ctx.followup.send("<:no:1503121885674868938> Вы не в клане!", ephemeral=True)
        logs = models.get_clan_treasury_log(clan["id"], 8)
        treasury = clan.get("treasury") or 0
        level = clan.get("level") or 1
        lines = []
        for entry in logs:
            sign = "+" if entry["amount"] > 0 else ""
            who = f"<@{entry['actor_id']}>" if entry["actor_id"] else "система"
            lines.append(f"`{sign}{entry['amount']}` {entry['reason']} — {who}")
        embed = discord.Embed(
            title=f"🏦 Казна [{clan['tag']}] {clan['name']}",
            description=f"**{treasury}** очков · Уровень **{level}**",
            color=EMBED_COLOR,
        )
        embed.add_field(
            name="Операции",
            value="\n".join(lines) if lines else "Пока пусто — внесите через /clan_deposit",
            inline=False,
        )
        embed.set_footer(text=ROLE_HINT)
        await ctx.followup.send(embed=embed, ephemeral=True)

    @discord.slash_command(name="clan_announce", description="Объявление в клановый чат (владелец)", guild_ids=[GUILD_ID])
    async def clan_announce(self, ctx: discord.ApplicationContext, message: str):
        clan = models.get_clan_membership(ctx.author.id)
        if not clan:
            return await ctx.respond("<:no:1503121885674868938> Вы не в клане!", ephemeral=True)
        if clan["owner_id"] != ctx.author.id:
            return await ctx.respond("<:no:1503121885674868938> Только владелец!", ephemeral=True)
        if not clan.get("chat_id"):
            return await ctx.respond("<:no:1503121885674868938> Клановый канал не найден.", ephemeral=True)
        channel = ctx.guild.get_channel(clan["chat_id"])
        if not channel:
            return await ctx.respond("<:no:1503121885674868938> Канал недоступен.", ephemeral=True)
        embed = discord.Embed(
            title=f"📢 [{clan['tag']}] Объявление",
            description=message[:2000],
            color=EMBED_COLOR,
        )
        embed.set_footer(text=f"От {ctx.author.display_name}")
        await channel.send(embed=embed)
        await ctx.respond("<:yes:1503121926128664766> Отправлено в клановый чат.", ephemeral=True)

    @discord.slash_command(name="clan_promote", description="Назначить роль (Офицер/Казначей)", guild_ids=[GUILD_ID])
    async def clan_promote(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        role: str = discord.Option(
            choices=["Офицер", "Казначей", "Участник"],
            description="Роль в клане",
        ),
    ):
        try:
            models.clan_set_member_role(ctx.author.id, member.id, role)
            await ctx.respond(f"<:yes:1503121926128664766> {member.mention} → **{role}**", ephemeral=True)
        except ClanError as e:
            await ctx.respond(f"<:no:1503121885674868938> {e}", ephemeral=True)

    @discord.slash_command(name="clan_transfer", description="Передать клан другому участнику", guild_ids=[GUILD_ID])
    async def clan_transfer(self, ctx: discord.ApplicationContext, member: discord.Member):
        try:
            models.clan_transfer_ownership(ctx.author.id, member.id)
            await ctx.respond(
                f"<:yes:1503121926128664766> Клан передан {member.mention}. Вы стали участником.",
                ephemeral=True,
            )
        except ClanError as e:
            await ctx.respond(f"<:no:1503121885674868938> {e}", ephemeral=True)

    @discord.slash_command(name="clan_lookup", description="Инфо о клане по тегу", guild_ids=[GUILD_ID])
    async def clan_lookup(self, ctx: discord.ApplicationContext, tag: str):
        conn = models.get_connection()
        row = conn.execute(
            """
            SELECT c.*, (SELECT COUNT(*) FROM clan_members WHERE clan_id = c.id) AS member_count
            FROM clans c WHERE LOWER(tag) = LOWER(?)
            """,
            (tag.strip(),),
        ).fetchone()
        conn.close()
        if not row:
            return await ctx.respond("<:no:1503121885674868938> Клан не найден.", ephemeral=True)
        embed = discord.Embed(title=f"[{row['tag']}] {row['name']}", color=EMBED_COLOR)
        if row["description"]:
            embed.description = row["description"]
        if row["avatar"]:
            embed.set_thumbnail(url=row["avatar"])
        embed.add_field(name="Побед / поражений", value=f"{row['wins']} / {row['losses']}", inline=True)
        embed.add_field(name="Казна", value=str(row["treasury"] or 0), inline=True)
        embed.add_field(name="Уровень", value=str(row["level"] or 1), inline=True)
        embed.add_field(name="Участников", value=str(row["member_count"]), inline=True)
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(Clans(bot))
