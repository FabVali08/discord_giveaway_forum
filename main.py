import json
import discord
import asyncio
import random
import os
from datetime import datetime, timedelta, timezone
from discord.ext import tasks, commands
from discord import ui
from config import settings

DB_DIR = "db"
GIVEAWAYS_DB = os.path.join(DB_DIR, "giveaways.json")
ROLE_DB = os.path.join(DB_DIR, "role.json")
FORUM_CHANNEL_DB = os.path.join(DB_DIR, "forum_channel.json")

os.makedirs(DB_DIR, exist_ok=True)

class GiveawayView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🎉 Teilnehmen", style=discord.ButtonStyle.green, custom_id="giveaway_join")
    async def join_giveaway(self, button: ui.Button, interaction: discord.Interaction):
        with open(GIVEAWAYS_DB, "r") as f:
            giveaways = json.load(f)

        giveaway = giveaways.get(str(interaction.message.id))
        if not giveaway:
            return await interaction.response.send_message("❌ Giveaway nicht gefunden!", ephemeral=True)

        if interaction.user.id in giveaway["participants"]:
            return await interaction.response.send_message("⚠️ Du nimmst bereits teil!", ephemeral=True)

        if giveaway["requirement_role"]:
            role = interaction.guild.get_role(giveaway["requirement_role"])
            if role not in interaction.user.roles:
                return await interaction.response.send_message(
                    f"❌ Du benötigst die Rolle {role.mention}!",
                    ephemeral=True
                )

        giveaway["participants"].append(interaction.user.id)
        with open(GIVEAWAYS_DB, "w") as f:
            json.dump(giveaways, f, indent=4)

        await interaction.response.send_message("🎉 Erfolgreich teilgenommen!", ephemeral=True)

    @ui.button(label="👥 Teilnehmer", style=discord.ButtonStyle.blurple, custom_id="giveaway_participants")
    async def show_participants(self, button: ui.Button, interaction: discord.Interaction):
        with open(GIVEAWAYS_DB, "r") as f:
            giveaways = json.load(f)

        giveaway = giveaways.get(str(interaction.message.id))
        if not giveaway:
            return await interaction.response.send_message("❌ Giveaway nicht gefunden!", ephemeral=True)

        participants = [f"<@{user_id}>" for user_id in giveaway["participants"]]
        embed = discord.Embed(
            title=f"🎁 Teilnehmer - {giveaway['prize']}",
            description="\n".join(participants) if participants else "Keine Teilnehmer",
            color=0xffca85
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="🛑 Beenden", style=discord.ButtonStyle.red, custom_id="giveaway_end")
    async def end_giveaway(self, button: ui.Button, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Keine Berechtigung!", ephemeral=True)

        with open(GIVEAWAYS_DB, "r") as f:
            giveaways = json.load(f)

        giveaway = giveaways.get(str(interaction.message.id))
        if not giveaway:
            return await interaction.response.send_message("❌ Giveaway nicht gefunden!", ephemeral=True)

        if len(giveaway["participants"]) < giveaway["winners"]:
            return await interaction.response.send_message("❌ Nicht genug Teilnehmer!", ephemeral=True)

        winners = random.sample(giveaway["participants"], giveaway["winners"])
        winners_mention = " ".join([f"<@{winner}>" for winner in winners])

        embed = discord.Embed(
            title=f"🎉 GEWINNER - {giveaway['prize']}",
            description=f"Herzlichen Glückwunsch an {winners_mention}!",
            color=0x00ff00
        )

        await interaction.channel.send(embed=embed)
        giveaway["ended"] = True

        with open(GIVEAWAYS_DB, "w") as f:
            json.dump(giveaways, f, indent=4)


class GiveawayBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(intents=intents, help_command=None, command_prefix='lu!')
        self.persistent_views_added = False

    async def setup_hook(self):
        self.add_view(GiveawayView())
        self.add_view(NicknameButton())
        await self.load_extension("jishaku")

    async def on_ready(self):
        if not self.persistent_views_added:
            self.persistent_views_added = True
            self.add_view(GiveawayView())
            self.add_view(NicknameButton())
        print(f"Eingeloggt als {self.user} (ID: {self.user.id})")


bot = GiveawayBot()

class NicknameModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Minecraft-Nickname ändern")
        self.add_item(
            ui.InputText(
                label="Minecraft-Name",
                placeholder="Gib deinen aktuellen Minecraft-Namen ein",
                min_length=3,
                max_length=16
            )
        )

    async def callback(self, interaction: discord.Interaction):
        nickname = self.children[0].value
        try:
            await interaction.user.edit(nick=nickname)
            embed = discord.Embed(
                title="✅ Erfolgreich geändert!",
                description=f"Dein Nickname wurde zu **{nickname}** aktualisiert!",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            error_embed = discord.Embed(
                title="❌ Fehler",
                description="Ich habe keine Berechtigung, deinen Nickname zu ändern!",
                color=0xff0000
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Unerwarteter Fehler",
                description=f"Ein Fehler ist aufgetreten: {str(e)}",
                color=0xff0000
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class NicknameButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Nickname ändern", style=discord.ButtonStyle.primary, custom_id="nickname_change", emoji="🛠️")
    async def button_callback(self, button, interaction):
        # Berechtigungscheck für den Bot
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "❌ Ich habe keine Berechtigung um Rollen zu vergeben!",
                ephemeral=True
            )
            return

        # Rollenzuweisung
        try:
            with open(ROLE_DB, "r") as f:
                role_data = json.load(f)
            role_id = role_data.get(str(interaction.message.id))
            
            if role_id:
                role = interaction.guild.get_role(role_id)
                if not role:
                    await interaction.response.send_message(
                        "❌ Konfigurierte Rolle nicht gefunden!",
                        ephemeral=True
                    )
                    return
                
                if role in interaction.user.roles:
                    await interaction.response.send_modal(NicknameModal())
                    return
                
                await interaction.user.add_roles(role)
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Fehler bei Rollenzuweisung: {str(e)}",
                ephemeral=True
            )
            return

        # Modal öffnen
        await interaction.response.send_modal(NicknameModal())

class NicknameCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(
        name="setup_nickname",
        description="🛠️ Erstelle das Nickname-Änderungssystem",
        default_member_permissions=discord.Permissions(administrator=True)
    )
    async def setup_nickname(self, ctx, role: discord.Role):
        # Embed erstellen
        embed = discord.Embed(
            title="🛠️ Minecraft-Nickname ändern",
            description="Klicke auf den Button unten um deinen Minecraft-Nickname festzulegen!\n\n"
                        "**Regeln:**\n"
                        "• Muss deinem aktuellen Minecraft-Namen entsprechen\n"
                        "• Keine beleidigenden Namen\n"
                        "• Mindestens 3 Zeichen lang",
            color=0x00FF00
        )
        
        # Nachricht senden und Rolle speichern
        message = await ctx.send(embed=embed, view=NicknameButton())
        
        try:
            with open(ROLE_DB, "r+") as f:
                data = json.load(f) if os.path.getsize(ROLE_DB) > 0 else {}
                data[str(message.id)] = role.id
                f.seek(0)
                json.dump(data, f, indent=4)
        except Exception as e:
            await ctx.respond(f"❌ Fehler beim Speichern der Rolle: {str(e)}", ephemeral=True)
            return
        
        await ctx.respond("✅ System wurde erfolgreich eingerichtet!", ephemeral=True)

class ForumChannel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(
        name="set_giveaway_forum",
        description="🎁 | Setze den Forum-Kanal für Giveaways",
        default_member_permissions=discord.Permissions(administrator=True)
    )
    async def set_forum_channel(self, ctx, channel: discord.ForumChannel):
        data = {"channel_id": channel.id}
        with open(FORUM_CHANNEL_DB, "w") as f:
            json.dump(data, f)
        await ctx.respond(f"🎉 Forum-Kanal wurde auf {channel.mention} gesetzt!", ephemeral=True)


class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    def get_forum_channel(self):
        try:
            with open(FORUM_CHANNEL_DB, "r") as f:
                return json.load(f)["channel_id"]
        except:
            return None

    giveaway = discord.SlashCommandGroup(
        name="giveaway",
        description="🎁 | Giveaway Commands",
        default_member_permissions=discord.Permissions(administrator=True)
    )

    @giveaway.command(name="create", description="🎁 | Erstelle ein neues Giveaway")
    async def create_giveaway(
        self,
        ctx: discord.ApplicationContext,
        duration: str,
        winners: int,
        prize: str,
        requirement_role: discord.Role = None
    ):
        try:
            time_units = {"d": 86400, "h": 3600, "m": 60}
            total_seconds = sum(int(t[:-1]) * time_units[t[-1]] for t in duration.split())
            end_time = datetime.now(timezone.utc) + timedelta(seconds=total_seconds)
        except:
            return await ctx.respond("⚠️ Ungültige Zeitangabe! Verwende z.B. '1d 2h 30m'", ephemeral=True)

        forum_channel_id = self.get_forum_channel()
        if not forum_channel_id:
            return await ctx.respond("❌ Es wurde kein Forum-Kanal festgelegt!", ephemeral=True)

        forum_channel = self.bot.get_channel(forum_channel_id)
        if not forum_channel:
            return await ctx.respond("❌ Forum-Kanal nicht gefunden!", ephemeral=True)

        embed = discord.Embed(
            description=f"""\
        ## 🎁 Giveaway – {prize}

        📦 **Preis:** {prize}  
        ⌛ **Endet:** <t:{int(end_time.timestamp())}:R>  
        🏆 **Gewinner:** {winners}  
        👤 **Veranstalter:** {ctx.author.mention}  
        **Voraussetzung:** {requirement_role.mention if requirement_role else 'Keine'}  

        ## 🔹 Teilnahmebedingungen  

        - **Nur 1 Teilnahme pro Person** (Mehrfachaccounts = Ausschluss).  
        - Der Gewinner wird nach Ende automatisch bekannt gegeben.  
        """,
            color=0xffca85
        )

        thread = await forum_channel.create_thread(
            name=f"🎁 Giveaway - {prize}",
            embed=embed,
            view=GiveawayView()
        )

        giveaway_data = {
            "message_id": thread.id,
            "channel_id": forum_channel.id,
            "end_time": end_time.isoformat(),
            "prize": prize,
            "winners": winners,
            "participants": [],
            "requirement_role": requirement_role.id if requirement_role else None,
            "ended": False
        }

        with open(GIVEAWAYS_DB, "r+") as f:
            data = json.load(f) if os.path.getsize(GIVEAWAYS_DB) > 0 else {}
            data[str(thread.id)] = giveaway_data
            f.seek(0)
            json.dump(data, f, indent=4)

        await ctx.respond(f"🎉 Giveaway wurde in {thread.mention} erstellt!", ephemeral=True)

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        with open(GIVEAWAYS_DB, "r") as f:
            giveaways = json.load(f)

        for thread_id_str, giveaway in list(giveaways.items()):
            thread_id = int(thread_id_str)
            print(f"Überprüfe Giveaway {thread_id}, Endzeit: {giveaway['end_time']}")

            if datetime.fromisoformat(giveaway["end_time"]) < datetime.now(timezone.utc) \
            and not giveaway["ended"]:
                print(f"Giveaway {thread_id} ist abgelaufen, beginne mit der Auslosung")
                thread = self.bot.get_channel(thread_id)
                if thread is None:
                    try:
                        thread = await self.bot.fetch_channel(thread_id)
                    except Exception as e:
                        print(f"Thread {thread_id} konnte nicht geladen werden: {e}")
                        continue
                try:
                    message = await thread.fetch_message(thread_id)
                except Exception as e:
                    print(f"Start‑Nachricht im Thread {thread_id} nicht gefunden: {e}")
                    continue
                if len(giveaway["participants"]) < giveaway["winners"]:
                    await message.reply("❌ Nicht genug Teilnehmer für die Auslosung!")
                    print(f"Nicht genug Teilnehmer für Giveaway {thread_id}")
                else:
                    winners = random.sample(giveaway["participants"], giveaway["winners"])
                    winners_mention = " ".join(f"<@{w}>" for w in winners)

                    embed = discord.Embed(
                        title=f"🎉 GEWINNER - {giveaway['prize']}",
                        description=f"Herzlichen Glückwunsch an {winners_mention}!",
                        color=0x00ff00
                    )
                    await thread.send(embed=embed)

                giveaway["ended"] = True
                giveaways[thread_id_str] = giveaway

        with open(GIVEAWAYS_DB, "w") as f:
            json.dump(giveaways, f, indent=4)


bot.add_cog(Giveaway(bot))
bot.add_cog(ForumChannel(bot))
bot.add_cog(NicknameCommands(bot))
bot.run(settings.TOKEN)