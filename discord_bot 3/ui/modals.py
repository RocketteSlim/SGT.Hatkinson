import discord
from discord.ui import Modal, TextInput, View, Select
import re
import aiosqlite
from datetime import datetime
import datetime as dt

def is_valid_url(url):
    url_pattern = re.compile(
        r'^(https?:\/\/)?'
        r'([\da-z\.-]+)\.([a-z\.]{2,6})'
        r'([\/\w \.-]*)*\/?'
        r'(\?.*)?$'
    )
    return bool(url_pattern.match(url))

class MessageDetailsModal(Modal, title="Détails du Message Important"):
    def __init__(self, cog, user, initial_message_id, user_message_id, guild, data=None, message_id=None):
        super().__init__()
        self.cog = cog
        self.user = user
        self.initial_message_id = initial_message_id
        self.user_message_id = user_message_id
        self.guild = guild
        self.message_id = message_id
        self.data = data or {}  # Stocker les données initiales
        print(f"MessageDetailsModal initialisé pour l'utilisateur {user.id}, message ID {message_id}, guild {guild.id}")
        print(f"Données initiales : {self.data}")

        # Champs avec valeurs par défaut correctes
        self.title_input = TextInput(
            label="Titre (optionnel)",
            style=discord.TextStyle.short,
            placeholder="Entrez le titre du message (facultatif)",
            default=str(self.data.get("title", "") or "") if self.data else "",
            required=False,
            max_length=100
        )
        self.content_input = TextInput(
            label="Contenu (optionnel)",
            style=discord.TextStyle.paragraph,
            placeholder="Entrez le contenu du message (facultatif)",
            default=str(self.data.get("content", "") or "") if self.data else "",
            required=False,
            max_length=2000
        )
        self.image_url_input = TextInput(
            label="URL de l'Image ou GIF (optionnel)",
            style=discord.TextStyle.short,
            placeholder="Entrez l'URL d'une image ou GIF",
            default=str(self.data.get("image_url", "") or "") if self.data else "",
            required=False,
            max_length=200
        )
        self.interval_input = TextInput(
            label="Intervalle (secondes)",
            style=discord.TextStyle.short,
            placeholder="Entrez l'intervalle en secondes (ex: 3600 pour 1 heure)",
            default=str(self.data.get("interval_seconds", "") or "") if self.data else "",
            required=True,
            max_length=10
        )

        self.add_item(self.title_input)
        self.add_item(self.content_input)
        self.add_item(self.image_url_input)
        self.add_item(self.interval_input)
        print(f"Champs du modal ajoutés pour l'utilisateur {user.id}")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            print(f"Soumission du modal par {interaction.user.id} pour message ID {self.message_id}")
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("Vous n'êtes pas autorisé à soumettre ce formulaire.", ephemeral=True)
                print(f"Accès refusé : {interaction.user.id} n'est pas l'auteur {self.user.id}")
                return

            # Validation : au moins un champ doit être rempli
            if not self.title_input.value and not self.content_input.value and not self.image_url_input.value:
                await interaction.response.send_message("Au moins un des champs (titre, contenu, ou URL de l'image) doit être rempli.", ephemeral=True)
                print("Erreur : tous les champs titre, contenu et image_url sont vides")
                return

            image_url = self.image_url_input.value.strip() if self.image_url_input.value else None
            if image_url and not is_valid_url(image_url):
                await interaction.response.send_message("L'URL de l'image ou du GIF n'est pas valide.", ephemeral=True)
                print(f"URL invalide : {image_url}")
                return

            try:
                interval_seconds = int(self.interval_input.value)
                if interval_seconds < 60:
                    await interaction.response.send_message("L'intervalle doit être d'au moins 60 secondes.", ephemeral=True)
                    print(f"Intervalle invalide : {interval_seconds} secondes")
                    return
            except ValueError:
                await interaction.response.send_message("L'intervalle doit être un nombre valide.", ephemeral=True)
                print(f"Erreur de conversion d'intervalle : {self.interval_input.value}")
                return

            # Créer les données mises à jour
            updated_data = {
                "title": self.title_input.value or None,
                "content": self.content_input.value or None,
                "image_url": image_url,
                "interval_seconds": interval_seconds,
                "initial_message_id": self.initial_message_id,
                "user_message_id": self.user_message_id,
                "user_id": self.user.id,
                "created_at": self.data.get("created_at") or datetime.now(dt.UTC).isoformat(),
                "message_id": self.message_id,
                "channel_id": self.data.get("channel_id")  # Conserver le channel_id existant pour ChannelSelectView
            }
            print(f"Données soumises : {updated_data}")

            # Afficher ChannelSelectView pour permettre la modification du canal
            view = ChannelSelectView(self.cog, self.user, updated_data, self.initial_message_id)
            embed = discord.Embed(
                title="Sélection du Canal",
                description="Choisissez le canal où le message récurrent sera envoyé.",
                color=discord.Color.blue(),
                timestamp=datetime.now(dt.UTC)
            )
            embed.set_footer(text=f"Demandé par {self.user.display_name}")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            message = await interaction.original_response()
            view.message = message
            print(f"Menu de sélection de canal envoyé pour l'utilisateur {self.user.id}")

        except Exception as e:
            print(f"Erreur dans on_submit de MessageDetailsModal : {e}")
            await interaction.response.send_message(f"Erreur lors de la création/mise à jour du message : {e}", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Erreur dans MessageDetailsModal : {error}")
        await interaction.response.send_message(f"Une erreur s'est produite : {error}", ephemeral=True)

class ChannelSelectView(View):
    def __init__(self, cog, user, data, initial_message_id):
        super().__init__(timeout=180)
        self.cog = cog
        self.user = user
        self.data = data
        self.initial_message_id = initial_message_id
        self.add_channel_select()

    def add_channel_select(self):
        try:
            select = Select(
                placeholder="Sélectionnez un canal",
                options=[
                    discord.SelectOption(
                        label=channel.name,
                        value=str(channel.id),
                        default=(self.data.get("channel_id") == channel.id)  # Pré-sélectionner le canal actuel
                    )
                    for channel in self.user.guild.text_channels
                    if channel.permissions_for(self.user.guild.me).send_messages
                ]
            )
            select.callback = self.channel_select_callback
            self.add_item(select)
            print(f"Menu déroulant des canaux ajouté pour l'utilisateur {self.user.id}, channel_id actuel : {self.data.get('channel_id')}")
        except Exception as e:
            print(f"Erreur lors de l'ajout du menu déroulant des canaux : {e}")

    async def channel_select_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("Seul l'auteur peut interagir avec cette vue.", ephemeral=True)
                print(f"Accès refusé : {interaction.user.id} n'est pas l'auteur {self.user.id}")
                return

            channel_id = int(interaction.data["values"][0])
            self.data["channel_id"] = channel_id
            self.data["paused"] = False
            print(f"Channel ID sélectionné : {channel_id}")

            async with aiosqlite.connect("embeds.db") as db:
                if self.data["message_id"]:
                    await db.execute("""
                        UPDATE important_messages
                        SET title = ?, content = ?, image_url = ?, interval_seconds = ?, channel_id = ?, created_at = ?
                        WHERE id = ?
                    """, (self.data["title"], self.data["content"], self.data["image_url"], self.data["interval_seconds"], self.data["channel_id"], self.data["created_at"], self.data["message_id"]))
                    await db.commit()
                    print(f"Message important mis à jour avec ID {self.data['message_id']}, channel_id {self.data['channel_id']}")
                else:
                    await db.execute("""
                        INSERT INTO important_messages (title, content, channel_id, interval_seconds, user_id, image_url, paused, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (self.data["title"], self.data["content"], self.data["channel_id"], self.data["interval_seconds"], self.data["user_id"], self.data["image_url"], False, self.data["created_at"]))
                    await db.commit()
                    cursor = await db.execute("SELECT last_insert_rowid()")
                    self.data["message_id"] = (await cursor.fetchone())[0]
                    print(f"Nouveau message important inséré avec ID {self.data['message_id']}, channel_id {self.data['channel_id']}")

            # Démarrer la tâche de message
            await self.cog.start_sending_messages(self.data["message_id"], self.data)
            print(f"Tâche de message démarrée pour message_{self.data['message_id']} dans le canal {self.data['channel_id']}")

            # Supprimer le message initial
            try:
                channel = self.user.guild.get_channel(self.data["channel_id"])
                if channel:
                    try:
                        initial_message = await channel.fetch_message(self.initial_message_id)
                        await initial_message.delete()
                        print(f"Message initial {self.initial_message_id} supprimé")
                    except discord.errors.NotFound:
                        print(f"Message initial {self.initial_message_id} déjà supprimé ou introuvable")
                else:
                    print(f"Canal {self.data['channel_id']} introuvable pour supprimer le message initial {self.initial_message_id}")
            except Exception as e:
                print(f"Erreur lors de la suppression du message initial : {e}")

            await interaction.response.edit_message(content=f"Message important {'mis à jour' if self.data['message_id'] else 'créé'} avec succès ! ID: {self.data['message_id']}", embed=None, view=None)
            print(f"Message important {'mis à jour' if self.data['message_id'] else 'créé'} pour ID {self.data['message_id']}")

        except Exception as e:
            print(f"Erreur dans channel_select_callback : {e}")
            await interaction.response.edit_message(content=f"Erreur lors de la sélection du canal : {e}", embed=None, view=None)

class EndServiceForm(Modal, title="Formulaire de Fin de Service"):
    def __init__(self, cog, user, data, message_id, channel):
        super().__init__()
        self.cog = cog
        self.user = user
        self.data = data
        self.message_id = message_id
        self.channel = channel
        print(f"EndServiceForm initialisé pour l'utilisateur {user.id}, message ID {message_id}")

        self.etat_major = TextInput(
            label="État Major",
            style=discord.TextStyle.short,
            placeholder="Entrez l'état major",
            default=data.get("etat_major", ""),
            required=True
        )
        self.prise_poste = TextInput(
            label="Prise de Poste",
            style=discord.TextStyle.short,
            placeholder="Entrez la prise de poste",
            default=data.get("prise_poste", ""),
            required=True
        )
        self.heure_debut = TextInput(
            label="Heure de Début",
            style=discord.TextStyle.short,
            placeholder="Entrez l'heure de début",
            default=data.get("heure_debut", ""),
            required=True
        )
        self.heure_fin = TextInput(
            label="Heure de Fin",
            style=discord.TextStyle.short,
            placeholder="Entrez l'heure de fin",
            default=data.get("heure_fin", ""),
            required=True
        )
        self.base_principale = TextInput(
            label="Base Principale",
            style=discord.TextStyle.short,
            placeholder="Entrez la base principale",
            default=data.get("base_principale", ""),
            required=True
        )
        self.objectifs = TextInput(
            label="Objectifs",
            style=discord.TextStyle.paragraph,
            placeholder="Entrez les objectifs",
            default=data.get("objectifs", ""),
            required=True
        )
        self.info_importante = TextInput(
            label="Info Importante",
            style=discord.TextStyle.paragraph,
            placeholder="Entrez les informations importantes",
            default=data.get("info_importante", ""),
            required=False
        )

        self.add_item(self.etat_major)
        self.add_item(self.prise_poste)
        self.add_item(self.heure_debut)
        self.add_item(self.heure_fin)
        self.add_item(self.base_principale)
        self.add_item(self.objectifs)
        self.add_item(self.info_importante)
        print(f"Champs du EndServiceForm ajoutés pour l'utilisateur {self.user.id}")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            print(f"Soumission du EndServiceForm par {interaction.user.id}")
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("Vous n'êtes pas autorisé à soumettre ce formulaire.", ephemeral=True)
                print(f"Accès refusé : {interaction.user.id} n'est pas l'auteur {self.user.id}")
                return

            self.data.update({
                "etat_major": self.etat_major.value,
                "prise_poste": self.prise_poste.value,
                "heure_debut": self.heure_debut.value,
                "heure_fin": self.heure_fin.value,
                "base_principale": self.base_principale.value,
                "objectifs": self.objectifs.value,
                "info_importante": self.info_importante.value or None
            })

            from ui.views import ValidateView
            view = ValidateView(self.cog, self.user, self.data, self.data.get("initial_message_id"), self.data.get("user_message_id"), self.channel, is_adc=True)
            embed = discord.Embed(
                title="Validation du Formulaire",
                description="Vérifiez les détails ci-dessous.",
                color=discord.Color.blue(),
                timestamp=datetime.now(dt.UTC)
            )
            for key, value in self.data.items():
                if value and key not in ["initial_message_id", "user_message_id", "user_id", "message_id"]:
                    embed.add_field(name=key.replace("_", " ").title(), value=value, inline=False)
            embed.set_footer(text=f"Créé par {self.user.display_name}")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            message = await interaction.original_response()
            view.message = message
            print(f"Formulaire EndServiceForm soumis avec succès pour l'utilisateur {self.user.id}")

        except Exception as e:
            print(f"Erreur dans on_submit de EndServiceForm : {e}")
            await interaction.response.send_message(f"Erreur lors de la soumission du formulaire : {e}", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Erreur dans EndServiceForm : {error}")
        await interaction.response.send_message(f"Une erreur s'est produite : {error}", ephemeral=True)