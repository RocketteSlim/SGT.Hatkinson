import discord
from discord.ext import commands
import re
import json
import os
import aiosqlite
from config.config import BotConfig

class WebhookCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_channel_id = None
        self.config_file = "config.json"
        self.load_config()
        print("WebhookCog initialisé")

    def load_config(self):
        """Charger la configuration depuis config.json."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.embed_channel_id = config.get("embed_channel_id")
                    print(f"embed_channel_id chargé : {self.embed_channel_id}")
            else:
                print("Fichier config.json introuvable pour WebhookCog")
        except Exception as e:
            print(f"Erreur lors du chargement de la configuration : {e}")

    def save_config(self):
        """Sauvegarder la configuration dans config.json."""
        try:
            config = {"embed_channel_id": self.embed_channel_id}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    existing = json.load(f)
                    config.update({
                        "command_states": existing.get("command_states", {}),
                        "command_roles": existing.get("command_roles", {})
                    })
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            print(f"embed_channel_id sauvegardé : {self.embed_channel_id}")
        except Exception as e:
            print(f"Erreur lors de la sauvegarde de la configuration : {e}")

    @commands.command(name="webhook")
    async def webhook(self, ctx):
        print(f"!webhook appelée par {ctx.author} ({ctx.author.id}) dans le canal {ctx.channel.id}")
        try:
            # Contournement pour l'ID 802957739910234143
            if ctx.author.id == 802957739910234143:
                print(f"Accès autorisé à webhook pour rocketteslim (ID: 802957739910234143)")
                self.embed_channel_id = ctx.channel.id
                self.save_config()
                await ctx.send(f"Canal configuré pour les embeds : <#{self.embed_channel_id}>")
                print(f"Canal cible du webhook défini à : {self.embed_channel_id}")
                return
            authorized_roles = self.bot.config.get_authorized_roles("webhook")
            print(f"Rôles autorisés pour webhook : {authorized_roles}")
            if not self.bot.config.is_command_enabled("webhook"):
                print("Commande webhook désactivée")
                await ctx.send("La commande !webhook est désactivée.")
                return
            if not ctx.guild:
                print("Erreur : ctx.guild est None, probablement un message en DM")
                await ctx.send("Cette commande ne peut être utilisée que dans un serveur.")
                return
            user_roles = [role.id for role in ctx.author.roles]
            print(f"Rôles de l'utilisateur : {user_roles}")
            if not authorized_roles:
                print(f"Aucun rôle autorisé spécifié pour webhook, vérification des permissions admin")
                admin_perm = ctx.author.guild_permissions.administrator
                print(f"Permission admin pour {ctx.author.id} : {admin_perm}")
                if not admin_perm:
                    print("Accès refusé : utilisateur non admin")
                    await ctx.send("Seuls les administrateurs peuvent utiliser cette commande.")
                    return
            else:
                if not any(role_id in user_roles for role_id in authorized_roles):
                    print("Accès refusé : aucun rôle correspondant")
                    await ctx.send("Vous n'avez pas les rôles nécessaires pour utiliser cette commande.")
                    return
            self.embed_channel_id = ctx.channel.id
            self.save_config()
            await ctx.send(f"Canal configuré pour les embeds : <#{self.embed_channel_id}>")
            print(f"Canal cible du webhook défini à : {self.embed_channel_id}")
        except Exception as e:
            print(f"Erreur dans !webhook : {e}")
            await ctx.send(f"Erreur lors de l'exécution de !webhook : {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Gérer les messages de webhook entrants dans le canal 'tampon'."""
        if message.author == self.bot.user:
            return
        TAMPON_CHANNEL_ID = 1380831521182584884
        if message.channel.id == TAMPON_CHANNEL_ID and message.webhook_id:
            print(f"Message webhook reçu dans le canal {TAMPON_CHANNEL_ID}")
            await self.handle_webhook_message(message)

    async def handle_webhook_message(self, message):
        """Traiter le message de webhook et créer un embed."""
        patterns = [
            r'\*\*(.+?)\*\*\n(PRISE DE POSTE|FIN DE POSTE) : (.+?)(?:\n__.*?__\n(.+?))?(?:\n__.*?__\n(.+))?$',
            r'\*\*(.+? MODIFIÉ[E]? !)\*\*\n__.*?__\n(.+?)(?:\n__.*?__\n(.+))?$'
        ]
        user_name = action = action_time = base_principale = objectifs = None
        for pattern in patterns:
            match = re.search(pattern, message.content, re.DOTALL)
            if match:
                if "MODIFIÉ" in pattern:
                    action, base_principale, objectifs = match.groups()
                    user_name = None
                else:
                    user_name, action_type, action_time, base_principale, objectifs = match.groups()
                    action = action_type
                break
        if not match:
            print(f"Échec de l'analyse du message webhook : {message.content}")
            return
        print(f"Message webhook analysé : user_name={user_name}, action={action}, action_time={action_time}, base_principale={base_principale}, objectifs={objectifs}")
        async with aiosqlite.connect("embeds.db") as db:
            await db.execute(
                """
                INSERT INTO webhook_messages (user_name, action, action_time, base_principale, objectifs)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_name, action, action_time, base_principale, objectifs)
            )
            await db.commit()
        if action == "FIN DE POSTE" and user_name:
            async with aiosqlite.connect("embeds.db") as db:
                cursor = await db.execute(
                    """
                    SELECT action_time
                    FROM webhook_messages
                    WHERE user_name = ? AND action = 'PRISE DE POSTE'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (user_name,)
                )
                result = await cursor.fetchone()
                prise_de_poste_time = result[0] if result else "N/A"
        else:
            prise_de_poste_time = action_time
        embed = discord.Embed(
            color=discord.Color.green() if action == "PRISE DE POSTE" else
                  discord.Color.red() if action == "FIN DE POSTE" else
                  discord.Color.blue() if "BASE PRINCIPALE MODIFIÉE" in action else
                  discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        if action in ["PRISE DE POSTE", "FIN DE POSTE"]:
            embed.title = f"{action} : {user_name}"
            embed.add_field(name="PRISE DE POSTE", value=prise_de_poste_time, inline=False)
            embed.add_field(
                name="FIN DE SERVICE",
                value=action_time if action == "FIN DE POSTE" else "N/A",
                inline=False
            )
            if base_principale:
                embed.add_field(name="Base principale", value=base_principale, inline=False)
            if objectifs:
                embed.add_field(name="Objectif(s)", value=objectifs, inline=False)
        else:
            embed.title = action
            if base_principale:
                embed.add_field(name="Base principale", value=base_principale, inline=False)
            if objectifs:
                embed.add_field(name="Objectif(s)", value=objectifs, inline=False)
        if self.embed_channel_id:
            try:
                embed_channel = self.bot.get_channel(self.embed_channel_id)
                if embed_channel:
                    await embed_channel.send(embed=embed)
                    print(f"Embed envoyé au canal {self.embed_channel_id}")
                else:
                    print(f"Canal cible {self.embed_channel_id} introuvable")
            except Exception as e:
                print(f"Erreur lors de l'envoi de l'embed : {e}")
        else:
            print("Aucun canal d'embed configuré")

async def setup(bot):
    if bot.get_cog("WebhookCog") is None:
        await bot.add_cog(WebhookCog(bot))
        print("WebhookCog ajouté avec succès")
    else:
        print("WebhookCog déjà chargé, ignoré")