import discord
from discord.ext import tasks
from datetime import timedelta
import json
import time
import os
from extentions import log, config, JSTTime, modmails
from extentions.aclient import client
from typing import List

logger = log.setup_logger()
dir = os.path.abspath(__file__ + "/../")
puni_json_path = "jsons/punishments.json"
jst_tz = JSTTime.timeJST("JST")

async def punishment_delete(member, id):
    punishments = await punishment_load()
    try:
        if str(member.id) in punishments:
            member_punishments = punishments[str(member.id)]["punishments"]
            for index in range(len(member_punishments)):
                if member_punishments[index]["id"] == id:
                    value = "True"
                    if "timeout" in member_punishments[index].keys():
                        if member_punishments[index]["timeout"]:
                            value = "Timeout"
                    del member_punishments[index]
                    punishments[str(member.id)
                                ]["punishments"] = member_punishments
                    await punishment_write(punishments)
                    return value
            return "False"

    except Exception as e:
        logger.error(f"[punishment_delete]にてエラー：{e}")


async def punishment_write(dic):
    with open(os.path.join(dir, puni_json_path), "w", encoding="UTF-8") as f:
        json.dump(dic, f, indent=2, ensure_ascii=False)
        logger.info(f"punishments.jsonに新しく書き込みを行いました")


async def punishment_load():
    with open(os.path.join(dir, puni_json_path), encoding="UTF-8") as f:
        punishments = json.load(f)
    return (punishments)


async def reason_autocomplete(interaction: discord.Interaction, current: str) -> List[discord.app_commands.Choice[str]]:
    reasons = ["botロールの取得",  "疑わしいプロフィール", "迷惑なスパム行為", "サーバールールの違反", "差別/侮辱的な発言", "ハラスメント行為",
               "暴力的な発言/脅迫行為", "児童への性的加害を含んだコンテンツの共有",
               "不適切な場所での性的なコンテンツの共有", "他者の権利を侵害するコンテンツの共有",
               "虚偽の情報/誤解を招く情報の共有", "違法行為の助長または実行"]
    return [
        discord.app_commands.Choice(name=reason, value=reason)
        for reason in reasons if current.lower() in reason.lower()
    ]
    
def timeout_choices():
    timeout_labels = ["無し", "30分", "1時間", "6時間", "12時間", "1日", "3日", "1週間"]
    timeout_values = [None, 30, 60, 360, 720, 1440, 4320, 10080]
    
    return [discord.SelectOption(label = timeout_labels[i], value = timeout_values[i]) for i in range(len(timeout_values))]

async def warning_and_timeout(interaction: discord.Interaction, member: discord.Member = None, member_id: str = None, reason: str = None, timeout: int = None):
    #AppCommand, Component, Modal_Submitのみ対応
    await interaction.response.defer()
    try:
        if member is None and member_id is None:
            embed = discord.Embed(title="メンバーを指定してください！",
                                  description="memberかmember_idのどちらかでメンバーの指定する必要があります！")
            await interaction.followup.send(embed=embed)
            return

        if not reason:
            reason = "無し"

        member_got = client.get_user(
            int(member_id)) if member is None else member

        now = str(JSTTime.timeJST("raw"))
        member_punishments = []
        search_id = str(member_got.id)
        
        timeout_minutes = f"{timeout}分" if timeout else "無し"

        punishments = await punishment_load()
        if search_id in punishments:
            criminal_record = punishments[search_id]
            member_punishments = criminal_record["punishments"]
            # logger.info(member_punishments)

        embed = discord.Embed(title="⚠️メンバーに「警告」を科しました。",
                              description=f"メンバー「{member_got.display_name}」に「**警告**」を科しました。\n- タイムアウト: {timeout_minutes}\n- 理由：{reason}\n- これは{len(member_punishments)+1}回目の処罰です。\n「警告」が数回重なった場合、より重い処罰が科される場合があります。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。",
                              color=member_got.accent_color)
        embed.set_author(name=member_got.display_name, icon_url=member_got.display_avatar)
        embed.set_footer(text=f"{now} | このメッセージは削除しないでください。")
        message = await interaction.followup.send(content=member_got.mention, embed=embed)

        punishment = {"id": message.id, "type": "warn", "timeout": timeout,
                      "date": now, "reason": reason, "by": interaction.user.id}

        if search_id in punishments:
            member_punishments.append(punishment)
            new = {"userName": str(member_got), "userID": member_got.id,
                   "banned": False, "punishments": member_punishments}
            punishments[search_id] = new
            # logger.info(new)
            await punishment_write(punishments)

        else:
            lists = []
            lists.append(punishment)
            new = {"userName": str(member_got), "userID": member_got.id, "banned": False, "punishments": lists}
            punishments[search_id] = new
            await punishment_write(punishments)

        if interaction.channel_id != config.moderatorchannel:
            channel = client.get_channel(config.moderatorchannel)
            await channel.send(embed=embed)

        if reason:
            if timeout:
                description = f"{member_got.display_name}さん、あなたはスタッフの判断によって「**警告とタイムアウト**」が科されました。\n- あなたはこれより**{timeout_minutes}**、メッセージの送信やVCへの参加が出来ません。\n- 警告の理由: {reason}\n\nこれは{len(member_punishments)+1}回目の処罰です。「警告」が数回重なるとより重いタイムアウトやサーバーからの追放、Banなどの重い処罰が科されます。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。\nこの処罰に身に覚えが無い場合、/modmailコマンドでアピールすることが出来ます。"
            else:
                description = f"{member_got.display_name}さん、あなたはスタッフの判断によって「**警告**」が科されました。\n- メッセージの送信やVCへの参加は引き続き可能です。\n- 警告の理由: {reason}\n\nこれは{len(member_punishments)+1}回目の処罰です。「警告」が数回重なるとタイムアウトやサーバーからの追放、Banなどの重い処罰が科されます。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。\nこの処罰に身に覚えが無い場合、/modmailコマンドでアピールすることが出来ます。"
            embed = discord.Embed(title="⚠️あなたはスタッフから警告されました",
                                  description=description)
            embed.set_author(
                name="あしたはこぶね", url=config.server_invite_link, icon_url=config.server_icon)
            logger.info(f"DMを送信しました。: {embed.description}")
            await member_got.send(embed=embed)
            
            #タイムアウト
            if timeout:
                timeout_until = timedelta(minutes = timeout)
                await member_got.timeout(timeout_until, reason = reason)

    except Exception as e:
        embed = discord.Embed(title="⚠️メンバーへの警告に失敗しました！",
                              description=f"メンバーの取得に失敗したか、既に退出している可能性があります！\n出現した例外：{e}")
        await interaction.followup.send(embed=embed)
        logger.error(f"[warning_and_timeout]にてエラー：{e}")

class WarningDetailModal(discord.ui.Modal):
    
    def __init__(self, member, message_url) -> None:
        self.message_url = message_url
        self.member = member
        super().__init__(title=f"{member.display_name}さんに警告を科す")
    
    reason = discord.ui.TextInput(label = "理由(任意)", required = False)
    timeout_minutes = discord.ui.TextInput(label = "タイムアウト期間(分, 任意)" , required = False)
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.timeout_minutes.value == False:
            interaction.response.send_message("タイムアウトには有効な数字のみを入力してください！")
        reason = f"{self.message_url}: {self.reason.value}" if self.reason.value else self.message_url
        await warning_and_timeout(interaction, self.member, None, reason, int(self.timeout_minutes.value))

@client.tree.context_menu(name = "メッセージから警告")
@discord.app_commands.default_permissions(kick_members=True)
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(kick_members=True)
async def warn_from_message(interaction: discord.Interaction, message: discord.Message):
    member = message.author
    message_url = message.jump_url
    await interaction.response.send_modal(WarningDetailModal(member, message_url))
    

@client.tree.command(name="warn", description="指定したメンバーに警告を科します。")
@discord.app_commands.describe(member="警告するメンバー(どちらか)", member_id="警告するメンバーの ID(どちらか)", reason="警告する理由", timeout="タイムアウト(ミュート)する時間(分単位の数字)")
@discord.app_commands.default_permissions(kick_members=True)
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(kick_members=True)
@discord.app_commands.autocomplete(reason=reason_autocomplete)
async def warn(interaction:  discord.Interaction, member:  discord.Member = None, member_id: str = None, reason: str = None, timeout: int = None):
    await warning_and_timeout(interaction, member, member_id, reason, timeout)

@client.tree.command(name="kick", description="指定したメンバーをキックします。")
@discord.app_commands.describe(member="キックするメンバー(どちらか)", member_id="キックするメンバーの ID(どちらか)", reason="キックする理由")
@discord.app_commands.default_permissions(kick_members=True)
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(kick_members=True)
@discord.app_commands.autocomplete(reason=reason_autocomplete)
async def kick(interaction:  discord.Interaction, member:  discord.Member = None, member_id: str = None, reason: str = None):
    await interaction.response.defer()
    try:
        if member is None and member_id is None:
            embed = discord.Embed(title="メンバーを指定してください！",
                                  description="memberかmember_idのどちらかでメンバーの指定する必要があります！")
            await interaction.followup.send(embed=embed)
            return

        if not reason:
            reason = "無し"

        member_got = client.get_user(
            int(member_id)) if member is None else member

        now = str(JSTTime.timeJST("raw"))
        member_punishments = []
        search_id = str(member_got.id)

        punishments = await punishment_load()
        if search_id in punishments:
            criminal_record = punishments[search_id]
            member_punishments = criminal_record["punishments"]

        embed = discord.Embed(title="⚠️メンバーを追放しました",
                              description=f"メンバー「{member_got.display_name}」をサーバーから「**追放**」しました。\n- 理由：{reason}\n- これは{len(member_punishments)+1}回目の処罰で、このメンバーはサーバーに入りなおすことが出来ます。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。",
                              color=member_got.accent_color)
        embed.set_author(name=member_got.display_name, icon_url=member_got.display_avatar)
        embed.set_footer(text=f"{now} | このメッセージは削除しないでください。")
        message = await interaction.followup.send(embed=embed)

        punishment = {"id": message.id, "type": "kick",
                      "date": now, "reason": reason, "by": interaction.user.id}

        if search_id in punishments:
            member_punishments.append(punishment)
            new = {"userName": str(member_got), "userID": member_got.id,
                   "banned": False, "punishments": member_punishments}
            punishments[search_id] = new
            await punishment_write(punishments)

        else:
            lists = []
            lists.append(punishment)
            new = {"userName": str(
                member_got), "userID": member_got.id, "banned": False, "punishments": lists}
            punishments[search_id] = new
            await punishment_write(punishments)

        if interaction.channel_id != config.moderatorchannel:
            channel = client.get_channel(config.moderatorchannel)
            await channel.send(embed=embed)

        if reason != "無し":
            embed = discord.Embed(title="⚠️あなたはサーバーから追放されました",
                                  description=f"{member_got.display_name}さん、あなたはスタッフの判断によってサーバーから「**追放**」されました。\n- 処罰の理由: {reason}\n\nあなたはまたサーバーに入りなおすことが出来ますが、これは{len(member_punishments)}回目の処罰です。回数が重なると、あなたはサーバーに入りなおすことが出来なくなります。\nこの処罰に身に覚えが無い場合、あなたは/modmailコマンドでアピールすることが出来ます。")
            embed.set_author(
                name="あしたはこぶね", url=config.server_invite_link, icon_url=config.server_icon)
            logger.info(f"DMを送信しました。: {embed.description}")
            await member_got.send(embed=embed)

        #キック
        await interaction.guild.kick(user=member_got, reason=reason)

    except Exception as e:
        embed = discord.Embed(title="⚠️メンバーの追放に失敗しました！",
                              description=f"メンバーの取得に失敗したか、既に退出している可能性があります！\n出現した例外：{e}")
        await interaction.followup.send(embed=embed)
        logger.error(f"[kick]にてエラー：{e}")


@client.tree.command(name="ban", description="指定したメンバーをBanします。")
@discord.app_commands.describe(member="Banするメンバー(どちらか)", member_id="Banするメンバーの ID(どちらか)", reason="Banする理由")
@discord.app_commands.default_permissions(kick_members=True, ban_members=True)
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(kick_members=True, ban_members=True)
@discord.app_commands.autocomplete(reason=reason_autocomplete)
async def ban(interaction:  discord.Interaction, member:  discord.Member = None, member_id: str = None, reason: str = None):
    await interaction.response.defer()
    try:
        if member is None and member_id is None:
            embed = discord.Embed(title="メンバーを指定してください！",
                                  description="memberかmember_idのどちらかでメンバーの指定する必要があります！")
            await interaction.followup.send(embed=embed)
            return

        if not reason:
            reason = "無し"

        member_got = await client.fetch_user(int(member_id)) if member is None else member

        now = str(JSTTime.timeJST("raw"))
        member_punishments = []
        search_id = str(member_got.id)

        punishments = await punishment_load()
        if search_id in punishments:
            criminal_record = punishments[search_id]
            member_punishments = criminal_record["punishments"]

        embed = discord.Embed(title="⚠️メンバーをBanしました",
                              description=f"メンバー「{member_got.display_name}」を「**Ban**」しました。\n- 理由：{reason}\n- これは{len(member_punishments)+1}回目の処罰で、このメンバーは二度とサーバーに参加することは出来ません。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。",
                              color=member_got.accent_color)
        embed.set_author(name=member_got.display_name, icon_url=member_got.display_avatar)
        embed.set_footer(text=f"{now} | このメッセージは削除しないでください。")
        message = await interaction.followup.send(embed=embed)

        punishment = {"id": message.id, "type": "ban",
                      "date": now, "reason": reason, "by": interaction.user.id}

        if search_id in punishments:
            member_punishments.append(punishment)
            new = {"userName": str(member_got), "userID": member_got.id,
                   "banned": True, "punishments": member_punishments}
            punishments[search_id] = new
            await punishment_write(punishments)

        else:
            lists = []
            lists.append(punishment)
            new = {"userName": str(
                member_got), "userID": member_got.id, "banned": True, "punishments": lists}
            punishments[search_id] = new
            await punishment_write(punishments)

        if interaction.channel_id != config.moderatorchannel:
            channel = client.get_channel(config.moderatorchannel)
            await channel.send(embed=embed)

        if reason != "無し" and member:
            embed = discord.Embed(title="⚠️あなたはサーバーからBanされました",
                                  description=f"{member_got.display_name}さん、あなたはスタッフの判断によってサーバーから「**Ban**」されました。\n- 処罰の理由: {reason}\n\nあなたはもう二度とサーバーに入りなおす事が出来ませんが、この処罰に身に覚えが無い場合、あなたは/modmailコマンドでアピールすることが出来ます。")
            embed.set_author(
                name="あしたはこぶね", url=config.server_invite_link, icon_url=config.server_icon)
            logger.info(f"DMを送信しました。: {embed.description}")
            await member_got.send(embed=embed)

        #ban
        await interaction.guild.ban(user=member_got, reason=reason)

    except Exception as e:
        embed = discord.Embed(title="⚠️メンバーのBanに失敗しました！",
                              description=f"メンバーの取得に失敗したか、既に退出している可能性があります！\nメッセージを送信出来なかった場合、理由を入力せずにもう一度お願いします。\n出現した例外：{e}")
        await interaction.followup.send(embed=embed)
        logger.error(f"[ban]にてエラー：{e}")


@client.tree.command(name="unban", description="指定したメンバーのBanを解除します。")
@discord.app_commands.describe(member="Banされたメンバー(どちらか)", member_id="Banされたメンバーの ID(どちらか)", delete="Banの経歴を削除するかどうか(デフォルトはFalse)")
@discord.app_commands.default_permissions(kick_members=True, ban_members=True)
@discord.app_commands.guild_only()
@discord.app_commands.checks.has_permissions(kick_members=True, ban_members=True)
async def unban(interaction:  discord.Interaction, member:  discord.Member = None, member_id: str = None, delete: bool = False):
    await interaction.response.defer()
    try:
        if member is None and member_id is None:
            embed = discord.Embed(title="メンバーを指定してください！",
                                  description="memberかmember_idのどちらかでメンバーの指定する必要があります！")
            await interaction.followup.send(embed=embed)
            return

        member_got = await client.fetch_user(int(member_id)) if member is None else member

        await interaction.guild.unban(user=member_got)

        now = str(JSTTime.timeJST("raw"))
        search_id = str(member_got.id)

        punishments = await punishment_load()
        if search_id in punishments:
            if punishments[search_id]["banned"] == True:
                punishments[search_id]["banned"] = False
            if delete == True:
                criminal_record = punishments[search_id]
                member_punishments = criminal_record["punishments"]
                for index in range(len(member_punishments)):
                    if member_punishments[index]["type"] == "ban":
                        del member_punishments[index]

        await punishment_write(punishments)

        embed = discord.Embed(title="✅メンバーのBanを解除しました",
                              description=f"スタッフの判断により、メンバー「{member_got.display_name}」の「**Banを解除**」しました。\nこのメンバーはまたサーバーに参加することが出来ます。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。",
                              color=member_got.accent_color)
        embed.set_author(name=str(member_got), icon_url=member_got.avatar)
        embed.set_footer(text=f"{now}")
        await interaction.followup.send(embed=embed)

        if interaction.channel_id != config.moderatorchannel:
            channel = client.get_channel(config.moderatorchannel)
            await channel.send(embed=embed)

        if delete == True and member:
            embed = discord.Embed(title="✅あなたのBanは解除されました",
                                  description=f"{member_got.display_name}さん、あなたはスタッフの判断によってサーバーからの「**Banを解除**」されました。\nBanの経歴も削除されます。\n「あしたはこぶね」をクリックすると、サーバーに入りなおすことができます。これからも「あしたはこぶね」をよろしくお願いします。")
            embed.set_author(
                name="あしたはこぶね", url=config.server_invite_link, icon_url=config.server_icon)
            logger.info(f"DMを送信しました。: {embed.description}")
            await member_got.send(embed=embed)

    except Exception as e:
        embed = discord.Embed(title="⚠️メンバーのBan解除に失敗しました！",
                              description=f"メンバーの取得に失敗したか、既に退出している可能性があります！\nメッセージを送信出来なかった場合、無視しても構いません。\n出現した例外：{e}")
        await interaction.followup.send(embed=embed)
        logger.error(f"[unban]にてエラー：{e}")


@discord.app_commands.default_permissions(view_audit_log=True)
@discord.app_commands.guild_only()
class ModerateCommand(discord.app_commands.Group):

    @discord.app_commands.command(name="show_all_bots", description="botロールを持っているメンバーを確認・追放します。#botmoderate専用コマンドです")
    @discord.app_commands.checks.has_permissions(view_audit_log=True)
    async def show_all_bots(self, interaction:  discord.Interaction):
        await interaction.response.defer()
        try:
            if interaction.channel_id != config.moderatorchannel:
                embed = discord.Embed(title=f"専用チャンネルで使用してください！",
                                      description=f"このコマンドは<#{config.moderatorchannel}>限定のコマンドです。")
                await interaction.followup.send(embed=embed)
                return
            
            bot_role = interaction.guild.get_role(config.spam_role)
            spam_members = bot_role.members
            
            if len(spam_members) <= 25:
                embed = discord.Embed(title = "botロールを取得しているメンバー一覧", description=f"botロールを取得しているメンバーは現在{len(spam_members)}人います。")
            else:
                embed = discord.Embed(title = "botロールを取得しているメンバー一覧", description=f"メンバーの数が25人を超えました({len(spam_members)}人)。最初の25人のみを表示しています。")
            number = 0
            for member in spam_members:
                number += 1
                if number <= 25:
                    embed.add_field(name = str(member), value = f"id: {member.id}")
                    
            await interaction.followup.send(embed = embed)
        except Exception as e:
            embed = discord.Embed(title="⚠️例外が発生しました！",
                                  description=f"出現した例外：{e}")
            await interaction.followup.send(embed=embed)
            logger.error(f"[ModerateCommand]にてエラー：{e}") 
            
   
    @discord.app_commands.command(name="kick_all_bots", description="botロールを持っているメンバー全員を追放します。#botmoderate専用コマンドです。")
    @discord.app_commands.checks.has_permissions(view_audit_log=True)
    async def kick_all_bots(self, interaction:  discord.Interaction):
        await interaction.response.defer()
        try:
            if interaction.channel_id != config.moderatorchannel:
                embed = discord.Embed(title=f"専用チャンネルで使用してください！",
                                      description=f"このコマンドは<#{config.moderatorchannel}>限定のコマンドです。")
                await interaction.followup.send(embed=embed)
                return
            
            bot_role = interaction.guild.get_role(config.spam_role)
            spam_members = bot_role.members
            now = str(JSTTime.timeJST("raw"))
            punishments = await punishment_load()
            reason = "botロールの取得"
            
            for member_got in spam_members:
                
                member_punishments = []
                search_id = str(member_got.id)

                
                if search_id in punishments:
                    criminal_record = punishments[search_id]
                    member_punishments = criminal_record["punishments"]

                embed = discord.Embed(title="⚠️メンバーを追放しました",
                                    description=f"メンバー「{member_got.display_name}」をサーバーから「**追放**」しました。\n- 理由：{reason}\n- これは{len(member_punishments)+1}回目の処罰で、このメンバーはサーバーに入りなおすことが出来ます。\n[サーバールール]({config.server_rule_link})や[Discordのコミュニティガイドライン]({config.community_guideline_link})を良く読んで、それらに違反しないようにご注意ください。",
                                    color=member_got.accent_color)
                embed.set_author(name=member_got.display_name, icon_url=member_got.display_avatar)
                embed.set_footer(text=f"{now} | このメッセージは削除しないでください。")
                message = await interaction.followup.send(embed=embed)

                punishment = {"id": message.id, "type": "kick",
                            "date": now, "reason": reason, "by": interaction.user.id}

                if search_id in punishments:
                    member_punishments.append(punishment)
                    new = {"userName": str(member_got), "userID": member_got.id,
                        "banned": False, "punishments": member_punishments}
                    punishments[search_id] = new

                else:
                    lists = []
                    lists.append(punishment)
                    new = {"userName": str(
                        member_got), "userID": member_got.id, "banned": False, "punishments": lists}
                    punishments[search_id] = new
                
                #DM送信
                embed = discord.Embed(title="⚠️あなたはサーバーから追放されました",
                                    description=f"{member_got.display_name}さん、あなたはスタッフの判断によってサーバーから「**追放**」されました。\n- 処罰の理由: {reason}\n\nあなたはまたサーバーに入りなおすことが出来ますが、これは{len(member_punishments)+1}回目の処罰です。回数が重なると、あなたはサーバーに入りなおすことが出来なくなります。\nこの処罰に身に覚えが無い場合、あなたは/modmailコマンドでアピールすることが出来ます。")
                embed.set_author(
                    name="あしたはこぶね", url=config.server_invite_link, icon_url=config.server_icon)
                logger.info(f"DMを送信しました。: {embed.description}")
                await member_got.send(embed=embed)

                #キック
                await interaction.guild.kick(user=member_got, reason=reason)
                
                #メンバー情報の表標示
                embed = discord.Embed(title=f"{member_got.display_name}(@{str(member_got)})さんの情報",
                                      description=f"{member_got.mention}\nユーザー名: {str(member_got)}\nグローバルネーム: {member_got.global_name}", color=member_got.accent_color)
                embed.set_thumbnail(url=member_got.display_avatar)
                embed.set_author(name=member_got.display_name,
                                 icon_url=member_got.avatar)
                if member_got.system == True:
                    member_stats = "システム(Discord公式)アカウント"
                elif member_got.bot == True:
                    member_stats = "Botアカウント"
                else:
                    member_stats = "ユーザー(通常)アカウント"
                embed.add_field(name = "アカウントの種類", value = member_stats)
                embed.add_field(name = "ID", value = member_got.id, inline = False)
                embed.add_field(name = "アカウント作成日", value = "<t:{0}:F>( <t:{0}:R> )".format(round(member_got.created_at.timestamp())), inline = False)

                user_puni = punishments[search_id]["punishments"]

                embed2 = discord.Embed(
                    title="処罰履歴", description=f"このユーザーは{len(user_puni)}回処罰を受けています")

                for index in range(len(user_puni)):
                    id = user_puni[index]["id"]
                    date = user_puni[index]["date"]
                    reason = user_puni[index]["reason"]
                    by = user_puni[index]["by"]
                    if "timeout" in user_puni[index].keys():
                        timeout = f"{user_puni[index]['timeout']}分" if user_puni[index]['timeout'] else "無し"
                        value = f"- ID: {id}\n- 時間: {date}\n- タイムアウト: {timeout}\n- 理由: {reason}\n- 処罰者: <@{by}>"
                    else:
                        value= f"- ID: {id}\n- 時間: {date}\n- 理由: {reason}\n- 処罰者: <@{by}>"
                    embed2.add_field(name=user_puni[index]["type"], value=value, inline=False)
                
                embeds = [embed, embed2]
                await interaction.followup.send(embeds = embeds)
                
            await punishment_write(punishments)
        except Exception as e:
            embed = discord.Embed(title="⚠️例外が発生しました！",
                                  description=f"出現した例外：{e}")
            await interaction.followup.send(embed=embed)
            logger.error(f"[ModerateCommand]にてエラー：{e}")                
            
    
    @discord.app_commands.command(name="show", description="指定されたメンバーの情報/処罰履歴を確認します。#botmoderate限定")
    @discord.app_commands.describe(member="メンバー(推奨)", member_id="ユーザーID(メンバー以外)")
    @discord.app_commands.checks.has_permissions(view_audit_log=True)
    async def show(self, interaction:  discord.Interaction, member:  discord.Member = None, member_id: str = None):
        await interaction.response.defer()
        try:
            if member is None and member_id is None:
                embed = discord.Embed(title="メンバーを指定してください！",
                                      description="memberかmember_idのどちらかでメンバーの指定する必要があります!")
                await interaction.followup.send(embed=embed)
                return

            if interaction.channel_id != config.moderatorchannel:
                embed = discord.Embed(title=f"専用チャンネルで使用してください！",
                                      description=f"このコマンドは<#{config.moderatorchannel}>限定のコマンドです。")
                await interaction.followup.send(embed=embed)
                return

            if member:
                member_got = member

                # ロール
                roles = []
                
                for index, role in enumerate(member_got.roles):
                    role_mention = role.name if index == 0 else role.mention
                    roles.append(role_mention)

                role = "\n".join(roles)

                embed = discord.Embed(title=f"{member_got.display_name}(@{str(member_got)})さんの情報",
                                      description=f"{member_got.mention}\nユーザー名: {str(member_got)}\nグローバルネーム: {member_got.global_name}", color=member_got.accent_color)
                embed.set_thumbnail(url=member_got.display_avatar)
                embed.set_author(name=member_got.display_name,
                                 icon_url=member_got.avatar)
                if member_got.system == True:
                    member_stats = "システム(Discord公式)アカウントです"
                elif member_got.bot == True:
                    member_stats = "Botアカウント"
                else:
                    member_stats = "ユーザー(通常)アカウント"
                embed.add_field(name = "アカウントの種類", value = member_stats)
                embed.add_field(name = "ID", value = member_got.id, inline = False)
                embed.add_field(name = "サーバー参加日", value = "<t:{0}:F>( <t:{0}:R> )".format(round(member_got.joined_at.timestamp())), inline = False)
                embed.add_field(name = "アカウント作成日", value = "<t:{0}:F>( <t:{0}:R> )".format(round(member_got.created_at.timestamp())), inline = False)
                embed.add_field(name = "所持しているロール", value = role, inline = True)
                embed.add_field(name = "最高のロール", value = "<@&{0}>".format(member_got.top_role.id), inline = True)
                if member_got.is_timed_out() == True:
                    embed.add_field(name="タイムアウト状態", value="<t:{0}:F>( <t:{0}:R> )まで".format(
                        round(member_got.timed_out_until.timestamp())), inline=False)

            else:
                try:
                    member_got = await client.fetch_user(int(member_id))
                except ValueError:
                    embed = discord.Embed(title=f"member_idに整数以外が渡されています",
                                      description=f"ユーザーIDが分からない場合、member引数を利用してください!")
                    await interaction.followup.send(embed=embed)
                    return
                    
                embed = discord.Embed(title=f"{member_got.display_name}(@{str(member_got)})さんの情報",
                                      description=f"{member_got.mention}\nユーザー名: {str(member_got)}\nグローバルネーム: {member_got.global_name}", color=member_got.accent_color)
                embed.set_thumbnail(url=member_got.display_avatar)
                embed.set_author(name=member_got.display_name,
                                 icon_url=member_got.avatar)
                if member_got.system == True:
                    member_stats = "システム(Discord公式)アカウント"
                elif member_got.bot == True:
                    member_stats = "Botアカウント"
                else:
                    member_stats = "ユーザー(通常)アカウント"
                embed.add_field(name = "アカウントの種類", value = member_stats)
                embed.add_field(name = "ID", value = member_got.id, inline = False)
                embed.add_field(name = "アカウント作成日", value = "<t:{0}:F>( <t:{0}:R> )".format(round(member_got.created_at.timestamp())), inline = False)
            search_id = str(member_got.id)
            embed2 = None

            punishments = await punishment_load()
            if search_id in punishments:
                banned = punishments[search_id]["banned"]
                user_puni = punishments[search_id]["punishments"]

                if banned == True:
                    embed.add_field(
                        name="Banされています", value="このユーザーはサーバーからBanされています", inline=False)

                embed2 = discord.Embed(
                    title="処罰履歴", description=f"このユーザーは{len(user_puni)}回処罰を受けています")

                for index in range(len(user_puni)):
                    id = user_puni[index]["id"]
                    date = user_puni[index]["date"]
                    reason = user_puni[index]["reason"]
                    by = user_puni[index]["by"]
                    if "timeout" in user_puni[index].keys():
                        timeout = f"{user_puni[index]['timeout']}分" if user_puni[index]['timeout'] else "無し"
                        value = f"- ID: {id}\n- 時間: {date}\n- タイムアウト: {timeout}\n- 理由: {reason}\n- 処罰者: <@{by}>"
                    else:
                        value= f"- ID: {id}\n- 時間: {date}\n- 理由: {reason}\n- 処罰者: <@{by}>"
                    embed2.add_field(name=user_puni[index]["type"], value=value, inline=False)

            if embed2:
                embeds = [embed, embed2]
                await interaction.followup.send(embeds=embeds)

            else:
                await interaction.followup.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(title="⚠️メンバーの情報を取得できませんでした！",
                                  description=f"メンバーの取得に失敗したか、既に退出している可能性があります！\n出現した例外：{e}")
            await interaction.followup.send(embed=embed)
            logger.error(f"[ModerateCommand.show]にてエラー：{e}")

    @discord.app_commands.command(name="delete", description="指定された処罰履歴を削除します。#botmoderate限定")
    @discord.app_commands.describe(id="処罰ID(/moderate showコマンドで表示されます)", member="メンバー(どちらか)", member_id="メンバーの ID(どちらか)")
    @discord.app_commands.checks.has_permissions(view_audit_log=True)
    async def delete(self, interaction:  discord.Interaction, id: str,  member:  discord.Member = None, member_id: str = None):
        await interaction.response.defer()
        try:
            if member is None and member_id is None:
                embed = discord.Embed(title="メンバーを指定してください！",
                                      description="memberかmember_idのどちらかでメンバーの指定する必要があります！")
                await interaction.followup.send(embed=embed)
                return
            
            member_got = await client.fetch_user(int(member_id)) if member is None else member
            id = int(id)

            result = await punishment_delete(member=member_got, id=id)
            if result != "False":
                if result == "Timeout" and member_got.is_timed_out() == True:
                    await member_got.timeout(None, reason = "処罰の訂正")
                embed = discord.Embed(title="処罰履歴の削除",
                                      description=f"{member_got.display_name}さんの処罰履歴#{id}を削除しました。")
                embed.set_author(name=str(member_got),
                                 icon_url=member_got.avatar)
                await interaction.followup.send(embed=embed)

            else:
                raise ValueError("result False")

        except Exception as e:
            embed = discord.Embed(title="⚠️処罰履歴の削除に失敗しました！",
                                  description=f"メンバーの取得に失敗したか、既に退出している可能性があります！\n出現した例外：{e}\n{str(member_got)}")
            await interaction.followup.send(embed=embed)
            logger.error(f"[ModerateCommand.delete]にてエラー：{e}")
    
    @discord.app_commands.command(name="modmail", description="指定されたメンバーと直接連絡を取り合います")
    @discord.app_commands.describe(member="メンバー(推奨)", member_id="ユーザーID(メンバー以外)")
    @discord.app_commands.checks.has_permissions(view_audit_log=True)
    async def modmail(self, interaction:  discord.Interaction, member:  discord.Member = None, member_id: str = None):
        await interaction.response.defer(ephemeral=True)
        try:
            if member is None and member_id is None:
                embed = discord.Embed(title="メンバーを指定してください！",
                                      description="memberかmember_idのどちらかでメンバーの指定する必要があります!")
                await interaction.followup.send(embed=embed)
                return

            member_got = await client.fetch_user(int(member_id)) if member is None else member
            
            await modmails.create_modmail(member_got)
            embed = discord.Embed(title="あしたはこぶね・個別連絡", description="**運営スタッフからの個別連絡が始まりました！**\nスタッフから連絡が入るまで今しばらくお待ちください。", color=discord.Color.green())
            embed.set_author(name="あしたはこぶねスタッフ", icon_url=config.server_icon)
            
            await member_got.send(embed=embed)
            await interaction.followup.send("Modmailの作成に成功しました！", ephemeral=True)
        except Exception as e:
            embed = discord.Embed(title="⚠️Modmailの作成に失敗しました！",
                                  description=f"メンバーの取得に失敗したか、メンバーへのDM送信に失敗した可能性があります！\n出現した例外：{e}")
            await interaction.followup.send(embed=embed, ephemeral = True)
            logger.error(f"[ModerateCommand.modmail]にてエラー：{e}")
