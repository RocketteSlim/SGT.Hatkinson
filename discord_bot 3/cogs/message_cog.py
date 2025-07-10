import discord
from discord.ext import commands
import asyncio
import aiosqlite
from datetime import datetime
import datetime as dt
from ui.views import PaginatedMessagesView, DashboardView
from database.db import init_db, fetch_active_messages, fetch_latest_webhook_data
from config.config import BotConfig
import time

class MessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_tasks = {}
        self.last_base_execution = 0  # Timestamp de la dernière exécution de !base
        print("MessageCog initialisé")

    async def cog_load(self):
        await init_db()
        print("Base de données initialisée avec succès")
        messages = await fetch_active_messages()
        print(f"Fetched {len(messages)} active messages from important_messages")
        for message_data in messages:
            if not message_data["paused"] and message_data.get("channel_id"):
                print(f"Démarrage de la tâche pour le message ID {message_data['id']} avec channel_id {message_data['channel_id']}")
                await self.start_sending_messages(message_data["id"], message_data)
            else:
                print(f"Message ID {message_data['id']} ignoré : paused={message_data['paused']}, channel_id={message_data.get('channel_id')}")
        print("MessageCog ajouté avec succès")

    async def start_sending_messages(self, message_id, message_data):
        if message_id in self.message_tasks:
            self.message_tasks[message_id].cancel()

        async def send_message():
            try:
                channel_id = message_data.get("channel_id")
                if not channel_id:
                    print(f"Erreur : channel_id manquant pour le message ID {message_id}")
                    async with aiosqlite.connect("embeds.db") as db:
                        await db.execute("UPDATE important_messages SET paused = ? WHERE id = ?", (True, message_id))
                        await db.commit()
                    # Notifier l'utilisateur
                    user = self.bot.get_user(message_data["user_id"])
                    if user:
                        try:
                            await user.send(f"Le message récurrent ID {message_id} a été mis en pause car aucun canal n'est défini.")
                        except Exception as e:
                            print(f"Erreur lors de l'envoi de la notification à {user.id} : {e}")
                    print(f"Message ID {message_id} mis en pause car channel_id est manquant")
                    return

                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    print(f"Canal {channel_id} introuvable pour le message ID {message_id}")
                    async with aiosqlite.connect("embeds.db") as db:
                        await db.execute("UPDATE important_messages SET paused = ? WHERE id = ?", (True, message_id))
                        await db.commit()
                    # Notifier l'utilisateur
                    user = self.bot.get_user(message_data["user_id"])
                    if user:
                        try:
                            await user.send(f"Le message récurrent ID {message_id} a été mis en pause car le canal {channel_id} est introuvable ou inaccessible.")
                        except Exception as e:
                            print(f"Erreur lors de l'envoi de la notification à {user.id} : {e}")
                    print(f"Message ID {message_id} mis en pause car le canal est introuvable")
                    return

                embed = discord.Embed(
                    title=message_data["title"] or "Message Important",
                    description=message_data["content"] or None,
                    color=discord.Color.blue(),
                    timestamp=datetime.now(dt.UTC)
                )
                if message_data.get("image_url"):
                    embed.set_image(url=message_data["image_url"])
                embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
                embed.set_footer(text=f"Créé par {self.bot.get_user(message_data['user_id']).display_name if self.bot.get_user(message_data['user_id']) else 'Utilisateur inconnu'}")
                
                message = await channel.send(embed=embed)
                async with aiosqlite.connect("embeds.db") as db:
                    await db.execute("UPDATE important_messages SET message_id = ? WHERE id = ?", (message.id, message_id))
                    await db.commit()
                print(f"Message récurrent envoyé avec l'ID : {message.id} dans le canal {channel_id}")
            except Exception as e:
                print(f"Erreur lors de l'envoi du message pour l'ID {message_id} : {e}")

        self.message_tasks[message_id] = self.bot.loop.create_task(self.run_message_task(message_id, message_data["interval_seconds"], send_message))
        print(f"Tâche de message démarrée pour message_{message_id}")

    async def run_message_task(self, message_id, interval_seconds, send_message):
        while True:
            async with aiosqlite.connect("embeds.db") as db:
                cursor = await db.execute("SELECT paused FROM important_messages WHERE id = ?", (message_id,))
                result = await cursor.fetchone()
                if result and result[0]:
                    print(f"Tâche de message message_{message_id} en pause")
                    await asyncio.sleep(60)
                    continue
            await send_message()
            await asyncio.sleep(interval_seconds)

    async def stop_sending_messages(self, message_id):
        if message_id in self.message_tasks:
            self.message_tasks[message_id].cancel()
            del self.message_tasks[message_id]
            print(f"Tâche de message arrêtée pour message_{message_id}")

    async def pause_message(self, message_id):
        async with aiosqlite.connect("embeds.db") as db:
            await db.execute("UPDATE important_messages SET paused = ? WHERE id = ?", (True, message_id))
            await db.commit()
        print(f"Tâche de message mise en pause pour message_{message_id}")

    async def resume_message(self, message_id, message_data):
        async with aiosqlite.connect("embeds.db") as db:
            await db.execute("UPDATE important_messages SET paused = ? WHERE id = ?", (False, message_id))
            await db.commit()
        if message_data.get("channel_id"):
            await self.start_sending_messages(message_id, message_data)
            print(f"Tâche de message reprise pour message_{message_id}")
        else:
            print(f"Impossible de reprendre le message {message_id} : channel_id manquant")

    def check_command_access(self, ctx, command_name):
        print(f"Vérification d'accès pour {ctx.author} ({ctx.author.id}) à la commande {command_name}")
        try:
            # Contournement pour l'ID 802957739910234143
            if ctx.author.id == 802957739910234143:
                print(f"Accès autorisé à {command_name} pour rocketteslim (ID: 802957739910234143)")
                return True, ""
            if not self.bot.config.is_command_enabled(command_name):
                print(f"Commande {command_name} désactivée")
                return False, "La commande est désactivée."
            authorized_roles = self.bot.config.get_authorized_roles(command_name)
            print(f"Rôles autorisés pour {command_name} : {authorized_roles}")
            if not ctx.guild:
                print("Erreur : ctx.guild est None, probablement un message en DM")
                return False, "Cette commande ne peut être utilisée que dans un serveur."
            user_roles = [role.id for role in ctx.author.roles]
            print(f"Rôles de l'utilisateur : {user_roles}")
            if not authorized_roles:
                print(f"Aucun rôle autorisé spécifié pour {command_name}, vérification des permissions admin")
                admin_perm = ctx.author.guild_permissions.administrator
                print(f"Permission admin pour {ctx.author.id} : {admin_perm}")
                return admin_perm, "Seuls les administrateurs peuvent utiliser cette commande."
            for role_id in authorized_roles:
                if role_id in user_roles:
                    print(f"Accès autorisé via le rôle {role_id}")
                    return True, ""
            print(f"Accès refusé : aucun rôle correspondant")
            return False, "Vous n'avez pas les rôles nécessaires pour utiliser cette commande."
        except Exception as e:
            print(f"Erreur dans check_command_access pour {command_name} : {e}")
            return False, f"Erreur lors de la vérification d'accès : {e}"

    @commands.command(name="imp_message")
    async def imp_message(self, ctx):
        access, message = self.check_command_access(ctx, "imp_message")
        if not access:
            print(f"Accès refusé pour !imp_message : {message}")
            await ctx.send(message)
            return
        try:
            print(f"!imp_message appelée par {ctx.author} dans le canal {ctx.channel.id}")
            embed = discord.Embed(
                title="Créer un Message Important",
                description="Cliquez sur le bouton ci-dessous pour configurer un message récurrent.",
                color=discord.Color.blue(),
                timestamp=datetime.now(dt.UTC)
            )
            embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
            view = discord.ui.View()
            button = discord.ui.Button(label="Configurer", style=discord.ButtonStyle.success, custom_id=f"open_imp_message_{ctx.message.id}")
            button.callback = self.open_imp_message_callback
            view.add_item(button)
            message = await ctx.send(embed=embed, view=view)
            print(f"Message initial pour !imp_message créé avec l'ID : {message.id}")
        except Exception as e:
            print(f"Erreur dans !imp_message : {e}")
            await ctx.send(f"Erreur lors de l'exécution de !imp_message : {e}")

    async def open_imp_message_callback(self, interaction: discord.Interaction):
        try:
            if interaction.response.is_done():
                print(f"Interaction déjà répondue pour {interaction.data.get('custom_id')}")
                return
            footer_text = interaction.message.embeds[0].footer.text
            if not footer_text:
                await interaction.response.send_message("Erreur : impossible de vérifier l'auteur du message.", ephemeral=True)
                print(f"Erreur : aucun footer dans le message {interaction.message.id}")
                return
            author_name = footer_text.split("Demandé par ")[1]
            if interaction.user.display_name != author_name:
                await interaction.response.send_message("Seul l'auteur peut interagir avec ce bouton.", ephemeral=True)
                print(f"Accès refusé : {interaction.user.id} n'est pas l'auteur {author_name}")
                return
            from ui.modals import MessageDetailsModal
            print(f"Bouton open_imp_message cliqué par {interaction.user.id}")
            await interaction.response.send_modal(MessageDetailsModal(
                self, interaction.user, interaction.message.id, interaction.message.id, interaction.guild
            ))
        except Exception as e:
            print(f"Erreur dans open_imp_message_callback : {e}")
            try:
                await interaction.followup.send(f"Erreur lors de l'ouverture du formulaire : {e}", ephemeral=True)
            except discord.errors.InteractionResponded:
                print(f"Interaction déjà répondue dans open_imp_message_callback")
                await interaction.followup.send(f"Erreur lors de l'ouverture du formulaire : {e}", ephemeral=True)

    @commands.command(name="list_messages")
    async def list_messages(self, ctx):
        access, message = self.check_command_access(ctx, "list_messages")
        if not access:
            print(f"Accès refusé pour !list_messages : {message}")
            await ctx.send(message)
            return
        try:
            print(f"!list_messages appelée par {ctx.author} dans le canal {ctx.channel.id}")
            messages = await fetch_active_messages()
            print(f"{len(messages)} messages actifs récupérés")
            if not messages:
                embed = discord.Embed(
                    title="Aucun Message",
                    description="Aucun message récurrent actif.",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(dt.UTC)
                )
                await ctx.send(embed=embed)
                print("Embed 'Aucun Message' envoyé")
                return
            view = PaginatedMessagesView(self, ctx.author, messages, ctx.channel)
            embed = view.create_embed()
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            print(f"Vue des messages paginés envoyée avec l'ID : {message.id}")
        except discord.errors.Forbidden as e:
            print(f"Erreur de permission dans !list_messages : {e}")
            await ctx.send("Erreur : Je n'ai pas la permission d'envoyer des messages dans ce canal.")
        except Exception as e:
            print(f"Erreur dans !list_messages : {e}")
            await ctx.send(f"Erreur lors de l'exécution de !list_messages : {e}")

    @commands.command(name="base")
    async def base(self, ctx):
        access, message = self.check_command_access(ctx, "base")
        if not access:
            print(f"Accès refusé pour !base : {message}")
            await ctx.send(message)
            return
        try:
            current_time = time.time()
            if current_time - self.last_base_execution < 600:  # 10 minutes
                remaining = 600 - (current_time - self.last_base_execution)
                await ctx.send(f"Cette commande est en cooldown. Veuillez attendre {int(remaining)} secondes.")
                print(f"Cooldown actif pour !base, temps restant : {int(remaining)} secondes")
                return
            print(f"!base appelée par {ctx.author} dans le canal {ctx.channel.id}")
            self.last_base_execution = time.time()
            base_principale, objectifs = await fetch_latest_webhook_data()
            if not base_principale or not objectifs:
                base_principale = "Non spécifié"
                objectifs = "Non spécifié"
            embed = discord.Embed(
                title="Avancée du Conflit",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Base principale", value=base_principale, inline=False)
            embed.add_field(name="Objectif(s)", value=objectifs, inline=False)
            embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
            message = await ctx.send(embed=embed)
            print(f"Embed de base envoyé avec l'ID : {message.id}")
        except Exception as e:
            print(f"Erreur dans !base : {e}")
            await ctx.send(f"Erreur lors de l'exécution de !base : {e}")

    @commands.command(name="help")
    async def help_command(self, ctx):
        try:
            print(f"!help appelée par {ctx.author} dans le canal {ctx.channel.id}")
            embed = discord.Embed(
                title="Aide - Commandes du Bot",
                description="Liste des commandes disponibles :",
                color=discord.Color.blue(),
                timestamp=datetime.now(dt.UTC)
            )
            commands_list = [
                ("imp_message", "Créer un message important récurrent."),
                ("list_messages", "Lister et gérer les messages récurrents."),
                ("base", "Afficher l'avancée du conflit avec base et objectifs."),
                ("help", "Afficher cette aide.")
            ]
            for name, description in commands_list:
                if self.bot.config.is_command_enabled(name):
                    embed.add_field(
                        name=f"!{name}",
                        value=description,
                        inline=False
                    )
            embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
            await ctx.send(embed=embed)
            print(f"Commande d'aide exécutée par {ctx.author.id}")
        except Exception as e:
            print(f"Erreur dans !help : {e}")
            await ctx.send(f"Erreur lors de l'exécution de !help : {e}")

    @commands.command(name="help_admin")
    async def help_admin_command(self, ctx):
        # Contournement pour votre ID ou administrateurs
        if ctx.author.id != 802957739910234143 and not ctx.author.guild_permissions.administrator:
            print(f"Accès refusé pour !help_admin par {ctx.author} ({ctx.author.id})")
            await ctx.send("Seuls les administrateurs peuvent utiliser cette commande.")
            return
        try:
            print(f"!help_admin appelée par {ctx.author} dans le canal {ctx.channel.id}")
            embed = discord.Embed(
                title="Aide - Commandes Administratives",
                description="Liste des commandes réservées aux administrateurs :",
                color=discord.Color.blue(),
                timestamp=datetime.now(dt.UTC)
            )
            commands_list = [
                ("webhook", "Configurer le canal pour les embeds de webhook.", self.bot.config.is_command_enabled("webhook"), self.bot.config.get_authorized_roles("webhook")),
                ("dashboard", "Configurer l'état et les rôles des commandes.", self.bot.config.is_command_enabled("dashboard"), self.bot.config.get_authorized_roles("dashboard"))
            ]
            for name, description, enabled, roles in commands_list:
                status = "Activée" if enabled else "Désactivée"
                role_names = [ctx.guild.get_role(role_id).name for role_id in roles if ctx.guild.get_role(role_id)] if roles and ctx.guild else ["Admins uniquement"]
                embed.add_field(
                    name=f"!{name} ({status})",
                    value=f"{description}\n**Rôles autorisés** : {', '.join(role_names)}",
                    inline=False
                )
            embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
            await ctx.send(embed=embed)
            print(f"Commande d'aide administrative exécutée par {ctx.author.id}")
        except Exception as e:
            print(f"Erreur dans !help_admin : {e}")
            await ctx.send(f"Erreur lors de l'exécution de !help_admin : {e}")

    @commands.command(name="dashboard")
    async def dashboard(self, ctx):
        access, message = self.check_command_access(ctx, "dashboard")
        if not access:
            print(f"Accès refusé pour !dashboard : {message}")
            await ctx.send(message)
            return
        try:
            print(f"!dashboard appelée par {ctx.author} dans le canal {ctx.channel.id}")
            embed = discord.Embed(
                title="Tableau de Bord - Configuration des Commandes",
                description="Utilisez les menus et boutons pour configurer les commandes et les rôles autorisés.",
                color=discord.Color.blue(),
                timestamp=datetime.now(dt.UTC)
            )
            for cmd, enabled in self.bot.config.command_states.items():
                status = "Activée" if enabled else "Désactivée"
                role_names = [ctx.guild.get_role(role_id).name for role_id in self.bot.config.get_authorized_roles(cmd) if ctx.guild.get_role(role_id)] or ["Admins uniquement"]
                embed.add_field(
                    name=cmd,
                    value=f"État : {status}\nRôles : {', '.join(role_names)}",
                    inline=True
                )
            embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
            view = DashboardView(self.bot, ctx.author, ctx.guild)
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            print(f"Vue du tableau de bord envoyée avec l'ID : {message.id}")
        except Exception as e:
            print(f"Erreur dans !dashboard : {e}")
            await ctx.send(f"Erreur lors de l'exécution de !dashboard : {e}")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        try:
            custom_id = interaction.data.get("custom_id") if interaction.data else None
            if custom_id and custom_id.startswith("open_imp_message_") and not interaction.response.is_done():
                await self.open_imp_message_callback(interaction)
        except Exception as e:
            print(f"Erreur dans on_interaction : {e}")
            try:
                await interaction.response.send_message(f"Erreur lors du traitement de l'interaction : {e}", ephemeral=True)
            except discord.errors.InteractionResponded:
                await interaction.followup.send(f"Erreur lors du traitement de l'interaction : {e}", ephemeral=True)

async def setup(bot):
    if bot.get_cog("MessageCog") is None:
        await bot.add_cog(MessageCog(bot))
        print("MessageCog ajouté avec succès")
    else:
        print("MessageCog déjà chargé, ignoré")