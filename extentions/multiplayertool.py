import asyncio
import json
import os

import discord

from extentions import log, supportrequest
from extentions.aclient import client
from extentions.config import config

logger = log.setup_logger()
dir = os.path.dirname(os.path.abspath(__file__))
multi_json_name = "jsons\\multi.json"

# --- Extensibility helpers (game/mode profile) ---
class GameModeProfile:
    """Lightweight profile to customize labels and destinations per game/mode.

    Add new entries to `_GAME_MODE_REGISTRY` to support other games/modes without
    changing the core logic.
    """
    def __init__(self,
                 key: str,
                 title: str,
                 request_channel_id: int,
                 thread_name_template: str,
                 labels: dict,
                 footer_text: str):
        self.key = key
        self.title = title
        self.request_channel_id = request_channel_id
        self.thread_name_template = thread_name_template
        self.labels = labels
        self.footer_text = footer_text


_GAME_MODE_REGISTRY: dict[str, GameModeProfile] = {
    # Default profile keeps current behavior/texts
    "default": GameModeProfile(
        key="default",
        title="マルチプレイ募集",
        request_channel_id=getattr(config, "multiplay_request_channel", 0),
        thread_name_template="マルチプレイチャット #{user_id}",
        labels={
            "room": "ルーム番号",
            "players": "プレイヤー数",
            "vc": "ボイスチャット連携",
            "playtime": "プレイ時間",
            "remarks": "遊び方",
            "owner_prefix": "募集主",
        },
        footer_text=(
            "作戦が終わった、もしくは募集を終えた場合は"
            "「削除」ボタンを押してください"
        ),
    ),
    # 協心競技
    "協心競技": GameModeProfile(
        key="協心競技",
        title="協心競技 募集",
        request_channel_id=getattr(config, "multiplay_request_channel", 0),
        thread_name_template="協心競技チャット #{user_id}",
        labels={
            "room": "ルーム番号",
            "players": "プレイヤー数",
            "vc": "ボイスチャット連携",
            "playtime": "プレイ時間",
            "remarks": "遊び方",
            "owner_prefix": "募集主",
        },
        footer_text=(
            "作戦が終わった、もしくは募集を終えた場合は"
            "「削除」ボタンを押してください"
        ),
    ),
    # デュエルチャンネル
    "デュエルチャンネル": GameModeProfile(
        key="デュエルチャンネル",
        title="デュエルチャンネル 募集",
        request_channel_id=getattr(config, "multiplay_request_channel", 0),
        thread_name_template="デュエルチャンネルチャット #{user_id}",
        labels={
            "room": "ルーム番号",
            "players": "プレイヤー数",
            "vc": "ボイスチャット連携",
            "playtime": "プレイ時間",
            "remarks": "遊び方",
            "owner_prefix": "募集主",
        },
        footer_text=(
            "作戦が終わった、もしくは募集を終えた場合は"
            "「削除」ボタンを押してください"
        ),
    ),
    # 堅守協定
    "堅守協定": GameModeProfile(
        key="堅守協定",
        title="堅守協定 募集",
        request_channel_id=getattr(config, "multiplay_request_channel", 0),
        thread_name_template="堅守協定チャット #{user_id}",
        labels={
            "room": "ルーム番号",
            "players": "プレイヤー数",
            "vc": "ボイスチャット連携",
            "playtime": "プレイ時間",
            "remarks": "遊び方",
            "owner_prefix": "募集主",
        },
        footer_text=(
            "作戦が終わった、もしくは募集を終えた場合は"
            "「削除」ボタンを押してください"
        ),
    ),
    # その他
    "その他": GameModeProfile(
        key="その他",
        title="その他 募集",
        request_channel_id=getattr(config, "multiplay_request_channel", 0),
        thread_name_template="マルチプレイチャット #{user_id}",
        labels={
            "room": "ルーム番号",
            "players": "プレイヤー数",
            "vc": "ボイスチャット連携",
            "playtime": "プレイ時間",
            "remarks": "遊び方",
            "owner_prefix": "募集主",
        },
        footer_text=(
            "作戦が終わった、もしくは募集を終えた場合は"
            "「削除」ボタンを押してください"
        ),
    )
}


def get_game_mode_profile(mode: str | None) -> GameModeProfile:
    """Return a registered game/mode profile; fallback to 'default'."""
    if not mode:
        return _GAME_MODE_REGISTRY["default"]
    return _GAME_MODE_REGISTRY.get(mode, _GAME_MODE_REGISTRY["default"])


def build_multiplayer_embed_from_item(owner: discord.User, item: dict) -> discord.Embed:
    """Build an embed from a stored request item using its mode profile."""
    profile = get_game_mode_profile(item.get("mode"))
    vc_linked_str = "有効" if item.get("vcLinked") else "無効"
    playtime = item.get("playtime") or "未定"
    remarks_str = item.get("remarks") or "無し"

    embed = discord.Embed(
        color=discord.Color.blue(),
        title=profile.title,
        description=f"{profile.labels.get('owner_prefix', '募集主')} {owner.mention}",
    )
    embed.add_field(name=profile.labels.get("room", "ルーム番号"), value=item.get("roomID", "-"), inline=False)
    players = int(item.get('players', 0) or 0)
    max_players = item.get('maxPlayers')
    # 0 or None means unlimited
    if not max_players:
        players_str = f"{players}/∞"
    else:
        players_str = f"{players}/{max_players}"
    embed.add_field(
        name=profile.labels.get("players", "プレイヤー数"),
        value=players_str,
    )
    embed.add_field(name=profile.labels.get("vc", "ボイスチャット連携"), value=vc_linked_str)
    embed.add_field(name=profile.labels.get("playtime", "プレイ時間"), value=playtime)
    embed.add_field(name=profile.labels.get("remarks", "遊び方"), value=remarks_str, inline=False)
    embed.set_footer(text=profile.footer_text)
    embed.set_author(icon_url=owner.display_avatar, name=owner.display_name)
    return embed


def build_multiplayer_item(user: discord.User,
                           room_id: str,
                           players: int,
                           max_players: int,
                           remarks: str,
                           playtime: str,
                           vc_linked_channel) -> dict:
    """Create a dict payload for storage/embedding; does not set messageID."""
    return {
        "userID": user.id,
        "roomID": room_id,
        "players": players,
        "maxPlayers": max_players,
        "remarks": remarks,
        "playtime": playtime,
        "vcLinked": (vc_linked_channel.id if vc_linked_channel else None),
        "mode": "default",
    }


async def send_multiplayer(user: discord.User,
                           room_id: str,
                           players: int,
                           max_players: int,
                           remarks: str,
                           playtime: str,
                           vc_linked,
                           mode: str | None = None) -> discord.Message:
    """Generic sender that uses game/mode profiles for flexibility."""
    profile = get_game_mode_profile(mode)
    # モジュールロード時の順序問題による 0 を防ぐため、動的に config を参照
    req_channel_id = getattr(config, "multiplay_request_channel", profile.request_channel_id) or profile.request_channel_id
    channel = client.get_channel(req_channel_id)
    if channel is None:
        channel = await client.fetch_channel(req_channel_id)
    multi_dict = load_multi_json()

    item = build_multiplayer_item(user, room_id, players, max_players, remarks, playtime, vc_linked)
    # Persist mode label if provided; otherwise default key
    item["mode"] = mode if mode else profile.key
    # Represent unlimited max as a human-friendly string for display and to bypass numeric equality checks
    if not max_players:
        item["maxPlayers"] = "∞"

    embed = build_multiplayer_embed_from_item(user, item)
    message_sent = await channel.send(embed=embed, view=AKMultiJoinButton())

    item["messageID"] = message_sent.id
    multi_dict.append(item)

    thread_name = profile.thread_name_template.format(user_id=user.id)
    created_thread = await message_sent.create_thread(name=thread_name)
    await created_thread.send(f"{user.mention}\nこちらをマルチプレイ中のチャット、募集連絡等にお使いください")

    write_multi_json(multi_dict)
    return message_sent

def load_multi_json():
    with open(os.path.join(dir, multi_json_name), encoding="utf-8") as f:
        multi_dict = json.load(f)
    return multi_dict

def write_multi_json(dict):
    with open(os.path.join(dir, multi_json_name), "w", encoding="utf-8") as f:
        json.dump(dict, f, ensure_ascii=False, indent = 4)
    return

class AKMultiJoinButton(discord.ui.View):
    def __init__(self, *, timeout = None):
        super().__init__(timeout=timeout)
    @discord.ui.button(label = "参加する", custom_id="multi_join_button", style = discord.ButtonStyle.success)
    async def multi_join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        multi_dict = load_multi_json()
        original_message = interaction.message
        
        for index, item in enumerate(multi_dict):
            if item["messageID"] == original_message.id:
                
                request_user = client.get_user(item["userID"])
                
                if item["players"] == item["maxPlayers"]:
                    await interaction.response.send_message("既に最大人数に達しています！", ephemeral = True)
                    return
                
                if item["userID"] == interaction.user.id and interaction.user.guild_permissions.manage_messages is not True:
                    await interaction.response.send_message("自分の募集に参加することは出来ません！", ephemeral = True)
                    return
                
                doctorname, return_interaction = await supportrequest.doctor_check_or_input(interaction, interaction.user)
                
                #ドクター名入力後
                if item["players"] +1 == item["maxPlayers"]:
                    self.children[0].disabled = True
                    
                item["players"] += 1
                
                write_multi_json(multi_dict)
                vc_linked_str = "有効" if item["vcLinked"] else "無効"
                playtime = item["playtime"] if item["playtime"] else "未定"
                remarks_str = item["remarks"] if item["remarks"] else "無し"
                
                embed = discord.Embed(color = discord.Color.blue(), title = "マルチプレイ募集", description = f"募集者: {request_user.mention}")
                embed.add_field(name = "ルーム番号", value= item["roomID"], inline = False)
                embed.add_field(name = "プレイヤー数", value= f'{item["players"]}/{item["maxPlayers"]}')
                embed.add_field(name = "ボイスチャット連携", value= vc_linked_str)
                embed.add_field(name = "プレイ時間", value= playtime)
                embed.add_field(name = "遊び方", value= remarks_str, inline=False)
                embed.set_footer(text = "【募集者のみ可能】作戦が終了した、もしくは募集を終了した場合は「削除」ボタンを押してください！")
                embed.set_author(icon_url=request_user.display_avatar, name = request_user.display_name)
                
                await original_message.edit(embed = embed, view = AKMultiJoinButton())
                
                if item["vcLinked"]:
                    guild = interaction.guild
                    moderator = guild.get_role(config.Moderator_role)
                    administrator = guild.get_role(config.administrator_role)
                    bots = guild.get_role(config.server_app_role)
                    try:
                        vc_channel = client.get_channel(item["vcLinked"])
                        overwrite = {
                            guild.default_role: discord.PermissionOverwrite(view_channel = False, connect = True),
                            interaction.user: discord.PermissionOverwrite(view_channel = True),
                            request_user: discord.PermissionOverwrite(view_channel = True, manage_channels = True)
                        }
                        if moderator: overwrite[moderator] = discord.PermissionOverwrite(view_channel = True, connect = True)
                        if administrator: overwrite[administrator] = discord.PermissionOverwrite(view_channel = True, connect = True)
                        if bots: overwrite[bots] = discord.PermissionOverwrite(view_channel = True, connect = True)
                        
                        await vc_channel.edit(overwrites=overwrite)
                        await return_interaction.response.send_message(f"参加しました！\n連携したボイスチャットに接続できます！→{vc_channel.jump_url}", ephemeral = True)
                    except Exception:
                        item["vcLinked"] = None
                        await return_interaction.response.send_message("参加しました！", ephemeral = True)
                        
                else:
                        
                    await return_interaction.response.send_message("参加しました！", ephemeral = True)
                
                await original_message.thread.send(f"{request_user.mention}\n {interaction.user.mention} さんが参加しました！ ドクターネーム: {doctorname}")
                return
        
        raise TypeError(f"リクエストが存在しません メッセージID:{original_message.id}")
    
    @discord.ui.button(label = "削除", custom_id="multi_delete_button", style = discord.ButtonStyle.danger)
    async def multi_delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        multi_list = load_multi_json()
        original_message = interaction.message
        
        messageID = None
        request_user = None

        for index in multi_list:
            if index["messageID"] == original_message.id:
                messageID = index["messageID"]
                request_user = client.get_user(index["userID"])
                
        if messageID is None or request_user is None:
            await interaction.followup.send("募集が見つかりませんでした。すでに削除されている場合があります", ephemeral=True)
            return
                
        if interaction.user.id == request_user.id or interaction.user.guild_permissions.manage_messages is True:
            embed = discord.Embed(title="マルチプレイ募集を終了しました！",
                                  description="この投稿は5秒後に削除されます！")
            embed.set_author(name=interaction.user.display_name,
                             icon_url=interaction.user.display_avatar)
            await original_message.edit(embed=embed, view=None)

            multi_list.remove(index)
            write_multi_json(multi_list)
            
            thread = interaction.guild.get_thread(messageID)
            await asyncio.sleep(5)
            if thread:
                await thread.delete()
            await interaction.delete_original_response()
        else:
            await interaction.followup.send("リクエストは募集を開始した本人だけが終了できます！", ephemeral=True)
    
class VClinkAndSendButton(discord.ui.View):
    def __init__(self, room_id: str, remarks: str , playtime: str, max_players: int, mode: str | None = None):
        self.room_id = room_id
        self.remarks = remarks
        self.playtime = playtime
        self.players = 1
        self.max_players = max_players
        self.mode = mode
        super().__init__(timeout = 240) 
        
    @discord.ui.button(label = "ボイスチャット連携(公開)", style=discord.ButtonStyle.success, emoji = "✅")  
    async def vclink_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc_channel_name = "無し"
        if interaction.user.voice:
            vc_channel = interaction.user.voice.channel
            vc_channel_name = vc_channel.jump_url
            vccreate_voice = client.get_channel(config.voicecreate_vc)
            
            if vc_channel.category_id == config.vccreate_category and not vc_channel == vccreate_voice:
                
                guild = interaction.guild
                moderator = guild.get_role(config.Moderator_role)
                administrator = guild.get_role(config.administrator_role)
                vc_allowed = guild.get_role(config.vc_allowed_role)
                bots = guild.get_role(config.server_app_role)
                
                overwrite = {
                    guild.default_role: discord.PermissionOverwrite(view_channel = False, connect = True),
                    interaction.user: discord.PermissionOverwrite(view_channel = True, manage_channels = True)
                }
                if vc_allowed: overwrite[vc_allowed] = discord.PermissionOverwrite(view_channel = True, connect = True)
                if moderator: overwrite[moderator] = discord.PermissionOverwrite(view_channel = True, connect = True)
                if administrator: overwrite[administrator] = discord.PermissionOverwrite(view_channel = True, connect = True)
                if bots: overwrite[bots] = discord.PermissionOverwrite(view_channel = True, connect = True)
                
                await vc_channel.edit(name = f"マルチプレイヤー: {self.room_id}", overwrites = overwrite)
                
                #値変える
                send_message = await send_multiplayer(interaction.user, self.room_id, self.players, self.max_players, self.remarks, self.playtime, vc_channel, mode=self.mode)
                embed = discord.Embed(color = discord.Color.green(), title = "マルチプレイ募集 - 完了", description = f"マルチプレイ募集を送信しました！\n送信した募集を見る: {send_message.jump_url}")
                
                await interaction.edit_original_response(embed = embed, view = None)
                
                return
            
            else:
                pass
    
        await interaction.followup.send(f"ボイスチャットに正しく接続されていません！正しい方法でボイスチャットに接続してください！\n※公開VC(雑談やアークナイツなど)は現在この機能を利用できません。備考入力をご活用ください。\n接続しているボイスチャット: {vc_channel_name}", ephemeral=True)
    @discord.ui.button(label = "ボイスチャット連携(非公開)", style=discord.ButtonStyle.secondary, emoji = "✅")  
    async def vclink_button_private(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc_channel_name = "無し"
        if interaction.user.voice:
            vc_channel = interaction.user.voice.channel
            vc_channel_name = vc_channel.jump_url
            vccreate_voice = client.get_channel(config.voicecreate_vc)
            
            if vc_channel.category_id == config.vccreate_category and not vc_channel == vccreate_voice:
                
                guild = interaction.guild
                moderator = guild.get_role(config.Moderator_role)
                administrator = guild.get_role(config.administrator_role)
                bots = guild.get_role(config.server_app_role)
                
                overwrite = {
                    guild.default_role: discord.PermissionOverwrite(view_channel = False, connect = True),
                    interaction.user: discord.PermissionOverwrite(view_channel = True, manage_channels = True)
                }
                if moderator: overwrite[moderator] = discord.PermissionOverwrite(view_channel = True, connect = True)
                if administrator: overwrite[administrator] = discord.PermissionOverwrite(view_channel = True, connect = True)
                if bots: overwrite[bots] = discord.PermissionOverwrite(view_channel = True, connect = True)
                
                await vc_channel.edit(name = f"マルチプレイヤー: {self.room_id}", user_limit=self.max_players, overwrites = overwrite)
                
                send_message = await send_multiplayer(interaction.user, self.room_id, self.players, self.max_players, self.remarks, self.playtime, vc_channel, mode=self.mode)
                embed = discord.Embed(color = discord.Color.green(), title = "マルチプレイ募集 - 完了", description = f"マルチプレイ募集を送信しました！\n送信した募集を見る: {send_message.jump_url}")
                
                await interaction.edit_original_response(embed = embed, view = None)
                
                return
            
            else:
                pass
        await interaction.followup.send(f"ボイスチャットに正しく接続されていません！正しい方法でボイスチャットに接続してください！\n※公開VC(雑談やアークナイツなど)は現在この機能を利用できません。備考入力をご活用ください。\n接続しているボイスチャット: {vc_channel_name}", ephemeral=True)
        
    @discord.ui.button(label = "連携しない", style=discord.ButtonStyle.primary)  
    async def sendonly_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        send_message = await send_multiplayer(interaction.user, self.room_id, self.players, self.max_players, self.remarks, self.playtime, None, mode=self.mode)
        embed = discord.Embed(color = discord.Color.green(), title = "マルチプレイ募集 - 完了", description = f"マルチプレイ募集を送信しました！\n送信した募集を見る: {send_message.jump_url}")
        
        await interaction.edit_original_response(embed = embed, view = None)
        

class AKMultiCreateModal(discord.ui.Modal, title = "マルチプレイ募集"):
    
    remarks_input = discord.ui.Label(
        text="遊び方",
        description="どんな遊び方をするのかを入力してください",
        component = discord.ui.TextInput(style=discord.TextStyle.paragraph, placeholder="攻略手伝ってください/未定", max_length=200, required=True)
    )
    playmode_input = discord.ui.Label(
        text="マルチプレイのモード",
        component = discord.ui.Select(
            options = [
                discord.SelectOption(label = "協心競技", value = "協心競技"),
                discord.SelectOption(label = "デュエルチャンネル", value = "デュエルチャンネル"),
                discord.SelectOption(label = "堅守協定", value = "堅守協定"),
                discord.SelectOption(label = "その他", value = "その他")
            ]
        )
    )
    playtime_input = discord.ui.Label(
        text="プレイ時間",
        component = discord.ui.Select(
            options = [
                discord.SelectOption(label="未定", value="未定"),
                discord.SelectOption(label="30分以内", value="30分以内"),
                discord.SelectOption(label="1時間以内", value="1時間以内"),
                discord.SelectOption(label="1時間以上", value="1時間以上")
            ],
            required=False,
            placeholder="未定"
        )
    )
    room_id_input = discord.ui.Label(
        text="ルーム番号",
        description="ルームを建てている場合入力してください(そのままコピペでOK!)",
        component = discord.ui.TextInput(style=discord.TextStyle.short, max_length=120, required=False)
    )
        
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        assert isinstance(self.remarks_input.component, discord.ui.TextInput)
        assert isinstance(self.playtime_input.component, discord.ui.Select)
        assert isinstance(self.playmode_input.component, discord.ui.Select)
        assert isinstance(self.room_id_input.component, discord.ui.TextInput)
        
        room_id = self.room_id_input.component.value.upper() if self.room_id_input.component.value else "ルーム番号未設定"
        remarks = self.remarks_input.component.value
        playtime = self.playtime_input.component.values[0] if self.playtime_input.component.values else "未定"
        
        id_find = room_id.find("[")
        if id_find != -1:
            id_find_end = room_id.find("]")
            room_id = room_id[id_find+1:id_find_end]
                
        if interaction.user.voice:
            vc_channel = interaction.user.voice.channel
            if vc_channel.category_id == config.vccreate_category:
                embed = discord.Embed(title = "マルチプレイ募集 - ボイスチャットを使用しますか？", description=f"現在あなたが接続している{vc_channel.jump_url}はVC連携を利用できます！\n(公開)はVCに誰でも入ることが出来ますが、(非公開)は募集から参加した人だけがVCに入れます。")
                await interaction.followup.send(embed = embed, view = VClinkAndSendButton(room_id=room_id, remarks=remarks, playtime=playtime, max_players = (2 if (not self.playmode_input.component.values or (self.playmode_input.component.values[0] in ("default", "協心競技"))) else 0), mode=(self.playmode_input.component.values[0] if self.playmode_input.component.values else "default")))
                return
            else:
                pass
            
        vccreate_voice = client.get_channel(config.voicecreate_vc)
        embed = discord.Embed(title = "マルチプレイ募集 - ボイスチャットを使用しますか？", description="ボイスチャットを使用して連携を深めたい場合にご利用ください！")
        embed.add_field(name = "使用方法", value = f"1. {vccreate_voice.jump_url}をクリックし、VCを作成します(自動的に作成したVCに接続します。名前や最大人数の設定は次の操作で自動で設定されます。)チャンネルにアクセスできない場合、「チャンネル&ロール」から「ボイスチャット」のロールを取得してください！\n2. 「ボイスチャット連携」ボタンを押します。(公開)はVCに誰でも入ることが出来ますが、(非公開)は募集から参加した人だけがVCに入れます。")
        await interaction.followup.send(embed = embed, view = VClinkAndSendButton(room_id=room_id, remarks=remarks, playtime=playtime, max_players = (2 if (not self.playmode_input.component.values or (self.playmode_input.component.values[0] in ("default", "協心競技"))) else 0), mode=(self.playmode_input.component.values[0] if self.playmode_input.component.values else "default")))
        
async def multi_create(interaction: discord.Interaction) -> bool:
    multi_dict = load_multi_json()
    for request in multi_dict:
        if request["userID"] == interaction.user.id:
            await interaction.response.send_message("あなたは既にマルチ募集をかけています！\n", ephemeral=True)
            return False
    modal = AKMultiCreateModal()
    await interaction.response.send_modal(modal)
    return True

@client.tree.command(name = "vccreate", guild = discord.Object(config.testserverid))
async def vccreate(interaction: discord.Interaction, channel: str = str(config.voicecreate_channel), edit_message: str = None):
    await interaction.response.defer()
    if channel and not channel.isdecimal():
        await interaction.followup.send(f"channel({channel})の型が不正です！")
    else:
        channel = int(channel)
    if edit_message and not edit_message.isdecimal():
        await interaction.followup.send(f"edit_message({edit_message})の型が不正です！")
    elif edit_message:
        edit_message = int(edit_message)
    
    vccreate_voice = client.get_channel(config.voicecreate_vc)
    channel_get = client.get_channel(channel)

    embed = discord.Embed(color = discord.Color.green(), title = "ボイスチャット作成", description=f"用途に沿った臨時ボイスチャットを作成します！\n{vccreate_voice.jump_url} を押すと**自動的に**ボイスチャットが作成されます！")
    embed.add_field(name = "名前の変え方", value = "作成されたボイスチャットから、「⚙️チャンネルの編集」→「チャンネル名」の欄に好きな名前を入力してください！\nオススメ: 今の状況や来て欲しい人など 例:「危機契約620点挑戦中」、「作業通話 誰でも来て下さい！」", inline = False)
    embed.add_field(name = "最大人数の設定", value = "「⚙️チャンネルの編集」→「ユーザー人数制限」のスライダーを動かすことで、ボイスチャットに接続できる最大人数を設定できます。数人用のゲームで遊ぶときにおススメです！", inline = False)
    embed.add_field(name = "聞き専チャット、読み上げについて", value = "聞き専チャットは作成されたボイスチャットの「💬チャットを開く」ボタンから開けます。\n読み上げbotは、<@&1322070138408931341>からご利用ください。ロードbotの`/join`から利用可能です！\nなお、読み上げモジュールは毎朝5時に再起動しますので、ご注意ください！", inline = False)
    
    if edit_message:
        message = await channel_get.fetch_message(edit_message)
        await message.edit(embed = embed)
        await interaction.followup.send("送信しました！")
    else:
        await channel_get.send(embed = embed)
        await interaction.followup.send("送信しました！")
        
        
