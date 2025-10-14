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
                        overwrite = {guild.default_role: discord.PermissionOverwrite(view_channel = False, connect = True),
                                moderator: discord.PermissionOverwrite(view_channel = True, connect = True),
                                administrator: discord.PermissionOverwrite(view_channel = True, connect = True),
                                bots: discord.PermissionOverwrite(view_channel = True, connect = True),
                                interaction.user: discord.PermissionOverwrite(view_channel = True),
                                request_user: discord.PermissionOverwrite(view_channel = True, manage_channels = True)}
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

async def send_AK_multiplayer(user: discord.User, room_id: str, players: int, max_players: int, remarks: str, playtime: str, vc_linked):
    channel = client.get_channel(config.multiplay_request_channel)
    multi_dict = load_multi_json()
    embed = discord.Embed(color = discord.Color.blue(), title = "マルチプレイ募集", description = f"募集者: {user.mention}")
    
    vc_linked_str = "有効" if vc_linked else "無効"
    vc_linked_id = vc_linked.id if vc_linked else None
    remarks_str = remarks if remarks else "無し"
        
    embed.add_field(name = "ルーム番号", value= room_id, inline = False)
    embed.add_field(name = "プレイヤー数", value=  f'{players}/{max_players}')
    embed.add_field(name = "ボイスチャット連携", value=  vc_linked_str)
    embed.add_field(name = "プレイ時間", value= playtime)
    embed.add_field(name = "遊び方", value= remarks_str, inline=False)
    embed.set_footer(text = "【募集者のみ可能】作戦が終了した、もしくは募集を終了した場合は「削除」ボタンを押してください！")
    embed.set_author(icon_url=user.display_avatar, name = user.display_name)
    
    message_sent = await channel.send(embed = embed, view = AKMultiJoinButton())
    request_dict = {"userID": user.id, "roomID": room_id, "players": players, "maxPlayers": max_players, "remarks": remarks, "playtime": playtime, "vcLinked": vc_linked_id, "messageID": message_sent.id}
    multi_dict.append(request_dict)
    created_thread = await message_sent.create_thread(name = f"マルチプレイチャット #{user.id}")
    
    await created_thread.send(f"{user.mention}\nこちらをマルチプレイ中のチャット、募集者との連絡等にお使いください！")
    
    write_multi_json(multi_dict)
    
    return message_sent
    
class VClinkAndSendButton(discord.ui.View):
    def __init__(self, room_id: str, remarks: str , playtime: str, max_players: int):
        self.room_id = room_id
        self.remarks = remarks
        self.playtime = playtime
        self.players = 1
        self.max_players = max_players
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
                
                overwrite = {guild.default_role: discord.PermissionOverwrite(view_channel = False, connect = True),
                             vc_allowed: discord.PermissionOverwrite(view_channel = True, connect = True),
                             moderator: discord.PermissionOverwrite(view_channel = True, connect = True),
                             administrator: discord.PermissionOverwrite(view_channel = True, connect = True),
                             bots: discord.PermissionOverwrite(view_channel = True, connect = True),
                             interaction.user: discord.PermissionOverwrite(view_channel = True, manage_channels = True)}
                
                await vc_channel.edit(name = f"マルチプレイヤー: {self.room_id}", overwrites = overwrite)
                
                #値変える
                send_message = await send_AK_multiplayer(interaction.user, self.room_id, self.players, self.max_players, self.remarks, self.playtime, vc_channel)
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
                
                overwrite = {guild.default_role: discord.PermissionOverwrite(view_channel = False, connect = True),
                            moderator: discord.PermissionOverwrite(view_channel = True, connect = True),
                            administrator: discord.PermissionOverwrite(view_channel = True, connect = True),
                            bots: discord.PermissionOverwrite(view_channel = True, connect = True),
                            interaction.user: discord.PermissionOverwrite(view_channel = True, manage_channels = True)}
                
                await vc_channel.edit(name = f"マルチプレイヤー: {self.room_id}", user_limit=self.max_players, overwrites = overwrite)
                
                send_message = await send_AK_multiplayer(interaction.user, self.room_id, self.players, self.max_players, self.remarks, self.playtime, vc_channel)
                embed = discord.Embed(color = discord.Color.green(), title = "マルチプレイ募集 - 完了", description = f"マルチプレイ募集を送信しました！\n送信した募集を見る: {send_message.jump_url}")
                
                await interaction.edit_original_response(embed = embed, view = None)
                
                return
            
            else:
                pass
        await interaction.followup.send(f"ボイスチャットに正しく接続されていません！正しい方法でボイスチャットに接続してください！\n※公開VC(雑談やアークナイツなど)は現在この機能を利用できません。備考入力をご活用ください。\n接続しているボイスチャット: {vc_channel_name}", ephemeral=True)
        
    @discord.ui.button(label = "連携しない", style=discord.ButtonStyle.primary)  
    async def sendonly_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        send_message = await send_AK_multiplayer(interaction.user, self.room_id, self.players, self.max_players, self.remarks, self.playtime, None)
        embed = discord.Embed(color = discord.Color.green(), title = "マルチプレイ募集 - 完了", description = f"マルチプレイ募集を送信しました！\n送信した募集を見る: {send_message.jump_url}")
        
        await interaction.edit_original_response(embed = embed, view = None)
        

class AKMultiCreateModal(discord.ui.Modal, title = "マルチプレイ募集"):
    
    #新仕様(ui.Label)
    remarks_input = discord.ui.Label(
        text="遊び方",
        description="どんな遊び方をするのかを入力してください",
        component = discord.ui.TextInput(style=discord.TextStyle.paragraph, placeholder="例: 上級やってない所/要塞ディフェンスメイン/サッカーやろうぜ/未定", max_length=200, required=True)
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
                await interaction.followup.send(embed = embed, view = VClinkAndSendButton(room_id=room_id, remarks=remarks, playtime=playtime, max_players = 2))
                return
            else:
                pass
            
        vccreate_voice = client.get_channel(config.voicecreate_vc)
        embed = discord.Embed(title = "マルチプレイ募集 - ボイスチャットを使用しますか？", description="ボイスチャットを使用して連携を深めたい場合にご利用ください！")
        embed.add_field(name = "使用方法", value = f"1. {vccreate_voice.jump_url}をクリックし、VCを作成します(自動的に作成したVCに接続します。名前や最大人数の設定は次の操作で自動で設定されます。)チャンネルにアクセスできない場合、「チャンネル&ロール」から「ボイスチャット」のロールを取得してください！\n2. 「ボイスチャット連携」ボタンを押します。(公開)はVCに誰でも入ることが出来ますが、(非公開)は募集から参加した人だけがVCに入れます。")
        await interaction.followup.send(embed = embed, view = VClinkAndSendButton(room_id=room_id, remarks=remarks, playtime=playtime, max_players = 2))     
        
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
        
        