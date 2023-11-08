import discord
import json
import os
from unicodedata import normalize
from re import match
from extentions import JSTTime, log, config, recruit, requests
from extentions.aclient import client
import traceback

logger = log.setup_logger(__name__)
dir = os.path.abspath(__file__ + "/../")

class AddInformationModal(discord.ui.Modal):
    def __init__(self, title, doctorname):
        super().__init__(title = title, timeout=None)
        if doctorname:
            self.before_doctorname = doctorname
            index_sharp = doctorname.find("#")
            index_dr = doctorname.find("Dr. ")
            before_name = doctorname[index_dr+4:index_sharp]
            before_number = doctorname[index_sharp+1:]
            self.name_input = discord.ui.TextInput(label = f"名前(IDの前半, 「Dr. 」を含まない)の変更 変更前「{before_name}」", custom_id = "name_input")
            self.add_item(self.name_input)
            self.number_input = discord.ui.TextInput(label = f"番号(IDの後半, 「#」を含まない)の変更 変更前「{before_number}」", custom_id = "number_input")
            self.add_item(self.number_input)
        else:
            self.before_doctorname = None
            self.name_input = discord.ui.TextInput(label = f"名前(IDの前半, 「Dr. 」を含まない)の追加 例「Rudia」", custom_id = "name_input")
            self.add_item(self.name_input)
            self.number_input = discord.ui.TextInput(label = f"番号(IDの後半, 「#」を含まない)の追加 例「2726」", custom_id = "number_input")
            self.add_item(self.number_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        tag = self.number_input.value
        name = self.name_input.value
        num_tag = normalize("NFKC", tag)

        if len(tag) > 6 or len(name) > 16:
            embed = discord.Embed(title="名前が長すぎます！",
                                    description="なにかの間違いで無かったら、スタッフまでお問い合わせください",
                                    color=0xf45d5d)
            await interaction.response.send_message(ephemeral = True, embed=embed)
            return

        if tag.isdecimal() == False or match(r"[0-9]{1,6}$", num_tag) is None:
            embed = discord.Embed(title="タグは数字のみを入力してください！",
                                    description="なにかの間違いで無かったら、スタッフまでお問い合わせください",
                                    color=0xf45d5d)
            await interaction.response.send_message(ephemeral = True, embed=embed)
            return
        
        added = await requests.doctor_add(interaction.user, name, num_tag)
        embed = discord.Embed(title="ドクター情報の登録が完了しました！",
                                description=f"新しく設定された貴方のドクターネームは「{added}」です！",
                                color=0x5cb85c)

        embed.set_author(name=interaction.user.name,
                            icon_url=interaction.user.avatar)
        embed.set_footer(text="変更する場合はもう一度「ドクター名登録」、登録を削除する場合は「/doctorname delete」コマンドをご利用ください")
        await interaction.response.send_message(ephemeral= True, embed = embed)
        
        
    async def on_errror(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("エラーが発生しました！")
        traceback.print_exception(type(error), error, error.__traceback__)
        
    

class ToolButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout = None)
    
    #ツールの追加
    @discord.ui.button(label = "公開求人ツール", custom_id = "recruitbutton", style = discord.ButtonStyle.primary, emoji = "📄")
    async def recruitbutton(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        selected_tags = []
        view = recruit.TagSelectView(selected_tags=selected_tags, all = True)
        
        embed = discord.Embed(title = "公開求人シミュレーター", description = f"ドロップダウンメニューからタグを一つずつ指定してください")
        logger.info(f"{interaction.user.name}がrecruitbuttonを使用しました")
        await interaction.followup.send(embed = embed, view = view, ephemeral=True)  
        
    @discord.ui.button(label = "ドクター名登録", custom_id = "addinformationbutton", style = discord.ButtonStyle.primary, emoji = "📝")
    async def addinformationbutton(self, interaction: discord.Interaction, button: discord.ui.Button):
        doctorname = await requests.doctor_check(user = interaction.user)
        if not doctorname:
            modal = AddInformationModal(title = f"ドクター情報の新規登録", doctorname=None)
            await interaction.response.send_modal(modal)
        else:
            modal = AddInformationModal(title = f"ドクター情報({doctorname})の編集", doctorname = doctorname)
            await interaction.response.send_modal(modal)
        logger.info(f"{interaction.user.name}がaddinformationbuttonを使用しました")
               

@client.tree.command(name="tool_form", description = "ツールのチャットを送信します", guild = discord.Object(config.testserverid))
@discord.app_commands.describe(channelid = "フォームを送信するチャンネル デフォルトはあしたはこぶね/#ツール", edit = "新規送信ではなくメッセージの編集にしたい場合、そのメッセージのID")
async def tool_form(interaction: discord.Interaction, channelid: str = "1142491583757951036", edit: str = None):
    await interaction.response.defer(ephemeral = True)
    
    channelid = normalize("NFKC", channelid)
    if edit:
        message_to_edit = normalize("NFKC", edit)
    
    channel = await client.fetch_channel(channelid)
    embed = discord.Embed(title = "コミュニティツール", description = "下のボタンから私の便利ツールをご利用できます！", color = discord.Color.red())
    
    #ツールの説明
    embed.add_field(name = "- 公開求人ツール", value = "公開求人のタグから獲得できるオペレーターを表示します。\nリセットする時はボタンを押し直してください！", inline=False)
    embed.add_field(name = "- ドクター情報登録", value = "アークナイツのホーム画面等から確認できるゲーム内IDをサーバーに登録し、「サポートリクエスト」への応答を可能にします。\n機能は「/doctorname add」コマンドとほぼ同じです。\n※登録した情報はメンバー全員が閲覧できますのでご注意ください。", inline = False)
    
    embed.set_author(name = "ロード", icon_url=client.user.avatar)
    if not edit:
        await channel.send(embed = embed, view = ToolButtons())
    else:
        message = await channel.fetch_message(message_to_edit)
        await message.edit(embed = embed, view = ToolButtons())
    
    await interaction.followup.send("完了しました！")