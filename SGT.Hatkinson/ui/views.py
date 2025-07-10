import discord
from discord.ui import View, Button, Select
import aiosqlite

class PaginatedMessagesView(View):
    def __init__(self, cog, author, messages, channel):
        super().__init__(timeout=180)
        self.cog = cog
        self.author = author
        self.messages = messages
        self.channel = channel
        self.current_page = 0
        print(f"PaginatedMessagesView initialisé pour l'utilisateur {author.id} avec {len(messages)} messages")
        self.update_buttons()

    def create_embed(self):
        embed = discord.Embed(
            title=f"Messages Récurrents - Page {self.current_page + 1}/{len(self.messages)}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        if self.messages:
            message = self.messages[self.current_page]
            embed.add_field(name="ID", value=message["id"], inline=True)
            embed.add_field(name="Titre", value=message["title"] or "Aucun", inline=True)
            embed.add_field(name="Canal", value=f"<#{message['channel_id']}>" if message["channel_id"] else "Non défini", inline=True)
            embed.add_field(name="Intervalle", value=f"{message['interval_seconds']} secondes" if message["interval_seconds"] else "Non défini", inline=True)
            embed.add_field(name="État", value="Actif" if not message["paused"] else "En pause", inline=True)
        else:
            embed.description = "Aucun message récurrent."
        embed.set_footer(text=f"Demandé par {self.author.display_name}")
        return embed

    def update_buttons(self):
        self.clear_items()
        if len(self.messages) > 1:
            prev_button = Button(label="Précédent", style=discord.ButtonStyle.secondary, disabled=self.current_page == 0)
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
            next_button = Button(label="Suivant", style=discord.ButtonStyle.secondary, disabled=self.current_page == len(self.messages) - 1)
            next_button.callback = self.next_page
            self.add_item(next_button)
        if self.messages:
            pause_resume_button = Button(
                label="Mettre en pause" if not self.messages[self.current_page]["paused"] else "Reprendre",
                style=discord.ButtonStyle.success if not self.messages[self.current_page]["paused"] else discord.ButtonStyle.primary
            )
            pause_resume_button.callback = self.pause_resume
            self.add_item(pause_resume_button)
            stop_button = Button(label="Arrêter", style=discord.ButtonStyle.danger)
            stop_button.callback = self.stop_message
            self.add_item(stop_button)
            edit_button = Button(label="Modifier", style=discord.ButtonStyle.secondary)
            edit_button.callback = self.edit_message
            self.add_item(edit_button)
        print(f"Boutons mis à jour pour PaginatedMessagesView, page {self.current_page + 1}")

    async def prev_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Seul l'auteur peut interagir avec cette vue.", ephemeral=True)
            return
        self.current_page -= 1
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        print(f"Page précédente affichée : {self.current_page + 1}")

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Seul l'auteur peut interagir avec cette vue.", ephemeral=True)
            return
        self.current_page += 1
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        print(f"Page suivante affichée : {self.current_page + 1}")

    async def pause_resume(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Seul l'auteur peut interagir avec cette vue.", ephemeral=True)
            return
        message_data = self.messages[self.current_page]
        if message_data["paused"]:
            await self.cog.resume_message(message_data["id"], message_data)
            message_data["paused"] = False
        else:
            await self.cog.pause_message(message_data["id"])
            message_data["paused"] = True
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        print(f"Message {message_data['id']} {'repris' if not message_data['paused'] else 'mis en pause'}")

    async def stop_message(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Seul l'auteur peut interagir avec cette vue.", ephemeral=True)
            return
        message_data = self.messages[self.current_page]
        await self.cog.stop_sending_messages(message_data["id"])
        async with aiosqlite.connect("embeds.db") as db:
            await db.execute("DELETE FROM important_messages WHERE id = ?", (message_data["id"],))
            await db.commit()
        self.messages.pop(self.current_page)
        if self.current_page >= len(self.messages):
            self.current_page = max(0, len(self.messages) - 1)
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        print(f"Message {message_data['id']} arrêté")

    async def edit_message(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Seul l'auteur peut interagir avec cette vue.", ephemeral=True)
            return
        from ui.modals import MessageDetailsModal
        message_data = self.messages[self.current_page]
        print(f"Données envoyées au modal pour le message ID {message_data['id']} : {message_data}")
        await interaction.response.send_modal(MessageDetailsModal(
            self.cog, interaction.user, interaction.message.id, interaction.message.id, interaction.guild, data=message_data, message_id=message_data["id"]
        ))
        print(f"Modal de modification ouvert pour le message ID {message_data['id']}")

class DashboardView(View):
    def __init__(self, bot, author, guild):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.guild = guild
        print(f"DashboardView initialisé pour l'utilisateur {author.id}")
        self.add_command_select()

    def add_command_select(self):
        try:
            select = Select(
                placeholder="Sélectionnez une commande à configurer",
                options=[
                    discord.SelectOption(label=cmd, value=cmd)
                    for cmd in self.bot.config.command_states.keys()
                ]
            )
            select.callback = self.command_select_callback
            self.add_item(select)
            print("Menu déroulant des commandes ajouté à DashboardView")
        except Exception as e:
            print(f"Erreur lors de l'ajout du menu déroulant des commandes : {e}")

    async def command_select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Seul l'auteur peut interagir avec cette vue.", ephemeral=True)
            return
        command_name = interaction.data["values"][0]
        print(f"Commande sélectionnée : {command_name}")
        self.clear_items()
        self.add_command_toggle(command_name)
        self.add_role_select(command_name)
        embed = discord.Embed(
            title=f"Configuration de la commande : {command_name}",
            description=f"État actuel : {'Activée' if self.bot.config.is_command_enabled(command_name) else 'Désactivée'}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        role_names = [self.guild.get_role(role_id).name for role_id in self.bot.config.get_authorized_roles(command_name) if self.guild.get_role(role_id)] or ["Aucun"]
        embed.add_field(name="Rôles autorisés", value=", ".join(role_names), inline=False)
        embed.set_footer(text=f"Demandé par {self.author.display_name}")
        await interaction.response.edit_message(embed=embed, view=self)
        print(f"Vue mise à jour pour la configuration de {command_name}")

    def add_command_toggle(self, command_name):
        try:
            button = Button(
                label="Activer/Désactiver",
                style=discord.ButtonStyle.green if self.bot.config.is_command_enabled(command_name) else discord.ButtonStyle.red
            )
            button.callback = lambda i: self.toggle_command(i, command_name)
            self.add_item(button)
            print(f"Bouton Activer/Désactiver ajouté pour {command_name}")
        except Exception as e:
            print(f"Erreur lors de l'ajout du bouton Activer/Désactiver : {e}")

    def add_role_select(self, command_name):
        try:
            select = Select(
                placeholder="Sélectionnez les rôles autorisés",
                options=[
                    discord.SelectOption(label=role.name, value=str(role.id))
                    for role in self.guild.roles if not role.is_bot_managed() and not role.is_integration()
                ],
                max_values=min(len([r for r in self.guild.roles if not r.is_bot_managed() and not r.is_integration()]), 25),
                min_values=0
            )
            select.callback = lambda i: self.role_select_callback(i, command_name)
            self.add_item(select)
            print(f"Menu déroulant des rôles ajouté pour {command_name}")
        except Exception as e:
            print(f"Erreur lors de l'ajout du menu déroulant des rôles : {e}")

    async def toggle_command(self, interaction: discord.Interaction, command_name):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Seul l'auteur peut interagir avec cette vue.", ephemeral=True)
            return
        current_state = self.bot.config.is_command_enabled(command_name)
        self.bot.config.set_command_state(command_name, not current_state)
        print(f"État de la commande {command_name} changé à : {'Activée' if not current_state else 'Désactivée'}")
        self.clear_items()
        self.add_command_select()
        embed = discord.Embed(
            title="Tableau de Bord - Configuration des Commandes",
            description="Utilisez le menu pour configurer les commandes et les rôles autorisés.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        for cmd, enabled in self.bot.config.command_states.items():
            status = "Activée" if enabled else "Désactivée"
            role_names = [self.guild.get_role(role_id).name for role_id in self.bot.config.get_authorized_roles(cmd) if self.guild.get_role(role_id)] or ["Admins uniquement"]
            embed.add_field(
                name=cmd,
                value=f"État : {status}\nRôles : {', '.join(role_names)}",
                inline=True
            )
        embed.set_footer(text=f"Demandé par {self.author.display_name}")
        await interaction.response.edit_message(embed=embed, view=self)
        print(f"Vue du tableau de bord restaurée après changement d'état de {command_name}")

    async def role_select_callback(self, interaction: discord.Interaction, command_name):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Seul l'auteur peut interagir avec cette vue.", ephemeral=True)
            return
        role_ids = [int(value) for value in interaction.data["values"]]
        self.bot.config.set_authorized_roles(command_name, role_ids)
        print(f"Rôles autorisés mis à jour pour {command_name} : {role_ids}")
        self.clear_items()
        self.add_command_select()
        embed = discord.Embed(
            title="Tableau de Bord - Configuration des Commandes",
            description="Utilisez le menu pour configurer les commandes et les rôles autorisés.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        for cmd, enabled in self.bot.config.command_states.items():
            status = "Activée" if enabled else "Désactivée"
            role_names = [self.guild.get_role(role_id).name for role_id in self.bot.config.get_authorized_roles(cmd) if self.guild.get_role(role_id)] or ["Admins uniquement"]
            embed.add_field(
                name=cmd,
                value=f"État : {status}\nRôles : {', '.join(role_names)}",
                inline=True
            )
        embed.set_footer(text=f"Demandé par {self.author.display_name}")
        await interaction.response.edit_message(embed=embed, view=self)
        print(f"Vue du tableau de bord restaurée après mise à jour des rôles de {command_name}")