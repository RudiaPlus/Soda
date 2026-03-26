import time
import datetime
from math import floor
import discord
from discord import app_commands

from extentions import log

logger = log.setup_logger()

def format_time(timestamp: int) -> str:
    return f"<t:{timestamp}:F>( <t:{timestamp}:R> )"

ARKNIGHTS_EVENT_STYLES = {
    "SIDESTORY": {"name": "サイドストーリー", "future_color": discord.Color.blue(), "present_color": 0xD94A36},
    "MINISTORY": {"name": "オムニバスストーリー", "future_name": "ミニストーリー", "future_color": discord.Color.green(), "present_color": 0xCAC531},
    "ROGUELIKE": {"name": "統合戦略", "future_color": 0x0096fa, "present_color": 0x0096fa},
    "SANDBOX": {"name": "生息演算", "future_color": 0xffa500, "present_color": 0xffa500},
    "BOSS_RUSH": {"name": "導灯の試練", "future_color": discord.Color.orange(), "present_color": 0xFFBA00},
    "MULTIPLAY": {"name": "マルチイベント", "future_color": discord.Color.orange(), "present_color": 0xCAC531},
    "MAIN": {"name": "新章実装キャンペーン", "future_color": discord.Color.orange(), "present_color": 0x353536},
    "SUPPORT": {"name": "新章公開 - 事前準備", "future_color": discord.Color.orange(), "present_color": 0x5C7CA8},
    "AUTOCHESS": {"name": "堅守協定", "future_color": discord.Color.orange(), "present_color": 	0x669933},
    "DEFAULT": {"name": "イベント", "future_color": discord.Color.orange(), "present_color": 0xf29382}
}

class BaseArknightsEvent(dict):
    def __init__(self, raw_data, dif):
        super().__init__()
        self.raw_data = raw_data
        self.dif = dif
        
        name = raw_data.get("name")
        type_ = raw_data.get("type")
        news = raw_data.get("news")
        link = raw_data.get("link")
        pic = raw_data.get("pic")
        
        self.update({
            "name": name,
            "dif": dif,
            "type": type_,
            "news": news,
            "link": link,
            "pic": pic
        })

    def parse(self):
        if self.dif == "past":
            try:
                self["rewardEndTime"] = format_time(self.raw_data["rewardEndTime"])
            except KeyError as e:
                logger.exception(f"[event_end_list]にてエラー：{e}")
        elif self.dif == "future":
            try:
                self["time"] = f"> 開始: {format_time(self.raw_data['startTime'])}"
                if self.get("type") not in ("ROGUELIKE", "SANDBOX"):
                    self["time"] += f"\n> 終了: {format_time(self.raw_data['endTime'])}"
            except KeyError as e:
                logger.exception(f"[event_value_list]にてエラー：{e}")
        elif self.dif == "present":
            try:
                self["startTime"] = format_time(self.raw_data["startTime"])
            except KeyError as e:
                logger.exception(f"startTime parsing error: {e}")
                
            if self.get("type") not in ("ROGUELIKE", "SANDBOX"):
                try:
                    self["endTime"] = format_time(self.raw_data["endTime"])
                    self["stageAdd"] = self.raw_data.get("stageAdd", False)
                except KeyError:
                    pass
            self.parse_present()
        return self

    def parse_present(self):
        """Override for specific present parsing"""
        if self.get("type") not in ("ROGUELIKE", "SANDBOX"):
            self["time"] = f"> 開始: {self.get('startTime')}\n> 終了: {self.get('endTime')}"
        if self.get("stageAdd"):
            try:
                additionalStage = self.raw_data.get("additionalStage", [])
                remark = None
                if additionalStage and additionalStage[0]["startTime"] > time.time():
                    self["nextStageName"] = additionalStage[0]["name"]
                    self["nextAddTime"] = format_time(additionalStage[0]["startTime"])
                    if len(additionalStage) == 1:
                        remark = "**このイベントはEXステージが登場予定です**\n"
                    elif len(additionalStage) == 2:
                        remark = "**このイベントはEXステージ、Sステージが登場予定です**\n"
                elif len(additionalStage) > 1 and additionalStage[1]["startTime"] > time.time():
                    self["nextStageName"] = additionalStage[1]["name"]
                    self["nextAddTime"] = format_time(additionalStage[1]["startTime"])
                    remark = "**EXステージが追加されました！**\n"
                    if len(additionalStage) == 2:
                        remark = "**EXステージが追加されました！Sステージが今後登場予定です**\n"
                elif len(additionalStage) == 1:
                    self["stageAdd"] = False
                    remark = "**EXステージが追加されました！**\n"
                    self["nextStageName"] = ""
                    self["nextAddTime"] = ""
                elif len(additionalStage) == 2:
                    self["stageAdd"] = False
                    remark = "**EXステージ、Sステージが追加されました！**\n"
                    self["nextStageName"] = ""
                    self["nextAddTime"] = ""
                self["remark"] = remark
            except Exception as e:
                logger.error(e)
                self["remark"] = None
        else:
            self["remark"] = None

    def build_embed(self) -> discord.Embed:
        if self.dif == "past":
            embed = discord.Embed(
                title=self.get("name"),
                description=f"- 攻略情報: [有志Wiki]({self.get('link')})\n> 報酬交換期限: {self.get('rewardEndTime')}",
                color=discord.Color.dark_grey(),
                url=self.get("link")
            )
            embed.set_author(name="終了したイベント")
            if self.get("pic"):
                embed.set_image(url=self.get("pic"))
            return embed
        
        elif self.dif == "future":
            return self.build_future_embed()
            
        elif self.dif == "present":
            return self.build_present_embed()

    def build_future_embed(self) -> discord.Embed:
        event_type = self.get("type", "")
        style = ARKNIGHTS_EVENT_STYLES.get(event_type, ARKNIGHTS_EVENT_STYLES["DEFAULT"])
        
        author_name = style.get("future_name", style["name"])
        color = style["future_color"]
        embed = discord.Embed(
            title=self.get("name"),
            description=f"- 詳細: [公式サイト]({self.get('news')})\n{self.get('time', '')}",
            color=color,
            url=self.get("news")
        )
        embed.set_author(name=f"開催予定の{author_name}")
        if self.get("pic"):
            embed.set_image(url=self.get("pic"))
        return embed

    def build_present_embed(self) -> discord.Embed:
        event_type = self.get("type", "")
        style = ARKNIGHTS_EVENT_STYLES.get(event_type, ARKNIGHTS_EVENT_STYLES["DEFAULT"])
        
        author_name = style["name"]
        color = style["present_color"]
        
        if event_type == "SIDESTORY" and self.get("stageAdd"):
            color = 0x24ab12
        embed = discord.Embed(
            title=self.get("name"),
            description=f"- 詳細: [公式サイト]({self.get('news')})\n- 攻略情報: [有志Wiki]({self.get('link')})\n{self.get('time', '')}",
            color=color,
            url=self.get("link")
        )
        embed.set_author(name=author_name)
        
        if self.get("remark"):
            embed.description = f"- {self.get('remark')}\n" + embed.description
            
        if self.get("stageAdd"):
            embed.add_field(
                name="・追加ステージ",
                value=f'**{self.get("nextStageName")}**\n> 追加: {self.get("nextAddTime")}',
                inline=False
            )
            
        if self.get("pic"):
            embed.set_image(url=self.get("pic"))
        return embed

#危機契約
class CrisisHandler(BaseArknightsEvent):
    def parse_present(self):
        super().parse_present()
        try:
            self["dailyStage"] = self.raw_data["dailyStage"]
            self["permStage"] = self.raw_data["permStage"]["stageName"]
            self["eventColor"] = self.raw_data["eventColor"]
        except KeyError as e:
            logger.exception(f"[CRISIS.dailyStage]にてエラー：{e}")
        
        dt = datetime.datetime.fromtimestamp(self.raw_data["startTime"] - 43200)
        now = datetime.datetime.now()
        delta = now - dt
        crisis_day = delta.days + 1
        
        dailyStage = self.get("dailyStage", [])
        if 1 <= crisis_day <= 4:
            todaysDaily = dailyStage[0] if len(dailyStage) > 0 else {}
            dailyEnd_date = dt + datetime.timedelta(days=4)
        elif 5 <= crisis_day <= 7:
            todaysDaily = dailyStage[1] if len(dailyStage) > 1 else {}
            dailyEnd_date = dt + datetime.timedelta(days=7)
        elif 8 <= crisis_day <= 10:
            todaysDaily = dailyStage[2] if len(dailyStage) > 2 else {}
            dailyEnd_date = dt + datetime.timedelta(days=10)
        else:
            todaysDaily = dailyStage[3] if len(dailyStage) > 3 else {}
            dailyEnd_date = dt + datetime.timedelta(days=14)
            
        self["todaysDaily"] = todaysDaily
        self["dailyEnd"] = floor(dailyEnd_date.timestamp())

    def build_present_embed(self) -> discord.Embed:
        c_str = self.get("eventColor", "0xffffff")
        color_val = int(c_str, 16) if isinstance(c_str, str) else c_str
        embed = discord.Embed(
            title=self.get("name"),
            description=f"- **高難易度のイベントです！**\n- 詳細: [公式サイト]({self.get('news')})\n- 攻略情報: [有志Wiki]({self.get('link')})\n{self.get('time', '')}",
            color=color_val,
            url=self.get("link")
        )
        embed.set_author(name="危機契約")
        embed.add_field(name="・通常試験区画", value=f'**{self.get("permStage")}**')
        todays_daily = self.get("todaysDaily", {})
        embed.add_field(
            name="・特別試験区画",
            value=f'**{todays_daily.get("stageName", "")}**\n> 賞金獲得期限: <t:{self.get("dailyEnd")}:R>'
        )
        if self.get("pic"):
            embed.set_image(url=self.get("pic"))
        return embed

#統合戦略
class RoguelikeHandler(BaseArknightsEvent):
    def parse_present(self):
        monthlyUpdate = self.raw_data.get("monthlyUpdate", [])
        month = content = updateEndTime = nextmonth = nextcontent = nextUpdateStartTime = None
        for update in monthlyUpdate:
            if update["startTime"] < time.time() and time.time() < update["endTime"]:
                month = update["month"]
                content = update["contents"]
                updateEndTime = format_time(update["endTime"])
            elif time.time() < update["startTime"]:
                nextmonth = update["month"]
                nextcontent = update["contents"]
                nextUpdateStartTime = format_time(update["startTime"])
        
        self.update({
            "month": month,
            "content": content,
            "updateTime": f"今月の任務終了: {updateEndTime}" if updateEndTime else None,
            "nextmonth": nextmonth,
            "nextcontent": nextcontent,
            "nextUpdateTime": f"開始: {nextUpdateStartTime}" if nextUpdateStartTime else None
        })

    def build_present_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.get("name"),
            description=f"- 詳細: [公式サイト]({self.get('news')})\n- 攻略情報: [有志Wiki]({self.get('link')})",
            color=0x852B2F,
            url=self.get("link")
        )
        embed.set_author(name="統合戦略")
        if self.get("month"):
            embed.add_field(
                name=f'・{self.get("month")}月の任務',
                value=f'{self.get("content")}\n> {self.get("updateTime")}',
                inline=False
            )
        if self.get("nextmonth"):
            embed.add_field(
                name=f'・{self.get("nextmonth")}月の任務',
                value=f'{self.get("nextcontent")}\n> {self.get("nextUpdateTime")}',
                inline=False
            )
        if self.get("pic"):
            embed.set_image(url=self.get("pic"))
        return embed

#生息演算
class SandboxHandler(BaseArknightsEvent):
    def parse_present(self):
        monthlyUpdate = self.raw_data.get("monthlyUpdate", [])
        month = content = updateEndTime = nextmonth = nextcontent = nextUpdateStartTime = None
        for update in monthlyUpdate:
            if update["startTime"] < time.time() and time.time() < update["endTime"]:
                month = update["month"]
                content = update["contents"]
                updateEndTime = format_time(update["endTime"])
            elif time.time() < update["startTime"]:
                nextmonth = update["month"]
                nextcontent = update["contents"]
                nextUpdateStartTime = format_time(update["startTime"])
                
        self.update({
            "month": month,
            "content": content,
            "updateTime": f"闘争の潮流入れ替え: {updateEndTime}" if updateEndTime else None,
            "nextmonth": nextmonth,
            "nextcontent": nextcontent,
            "nextUpdateTime": f"開始: {nextUpdateStartTime}" if nextUpdateStartTime else None
        })

    def build_present_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.get("name"),
            description=f"- 詳細: [公式サイト]({self.get('news')})\n- 攻略情報: [有志Wiki]({self.get('link')})",
            color=0xB0DB34,
            url=self.get("link")
        )
        embed.set_author(name="生息演算")
        if self.get("month"):
            embed.add_field(
                name=f'・{self.get("month")}月の闘争の潮流',
                value=f'{self.get("content")}\n> {self.get("updateTime")}',
                inline=False
            )
        if self.get("nextmonth"):
            embed.add_field(
                name=f'・{self.get("nextmonth")}月の闘争の潮流',
                value=f'{self.get("nextcontent")}\n> {self.get("nextUpdateTime")}',
                inline=False
            )
        if self.get("pic"):
            embed.set_image(url=self.get("pic"))
        return embed

#鋒矢突破
class BreakHandler(BaseArknightsEvent):
    def parse_present(self):
        super().parse_present()
        try:
            p2 = self.raw_data["phase2StartTime"]
            self["phase2StartTime"] = format_time(p2)
            self["eventColor"] = self.raw_data["eventColor"]
        except KeyError as e:
            logger.error(e)

    def build_present_embed(self) -> discord.Embed:
        c_str = self.get("eventColor", "0xffffff")
        color_val = int(c_str, 16) if isinstance(c_str, str) else c_str
        embed = discord.Embed(
            title=self.get("name"),
            description=f"- **高難易度のイベントです！**\n- 詳細: [公式サイト]({self.get('news')})\n- 攻略情報: [有志Wiki]({self.get('link')})\n{self.get('time', '')}",
            color=color_val,
            url=self.get("link")
        )
        embed.set_author(name="鋒矢突破")
        embed.add_field(name="・総力戦開放", value=f'> 開放: {self.get("phase2StartTime")}')
        if self.get("pic"):
            embed.set_image(url=self.get("pic"))
        return embed

ARKNIGHTS_HANDLERS = {
    "CRISIS": CrisisHandler,
    "ROGUELIKE": RoguelikeHandler,
    "SANDBOX": SandboxHandler,
    "BREAK": BreakHandler
}

def get_arknights_handler(event_data, dif):
    event_type = event_data.get("type", "DEFAULT")
    HandlerClass = ARKNIGHTS_HANDLERS.get(event_type, BaseArknightsEvent)
    return HandlerClass(event_data, dif).parse()

# ---- Endfield ----
ENDFIELD_EVENT_STYLES = {
    "OPSTORY": {"name": "物語イベント", "color": 0x0096fa},
    "GUIDE": {"name": "案内イベント", "color": 0x8A2BE2},
    "SANITY": {"name": "理性消費軽減", "color": 0x3CB371},
    "OTHER": {"name": "イベント", "color": 0xFFA500},
    "MONUMENT": {"name": "映像の記念碑・記憶の痕", "color": 0xcb2b26},
    "DEFAULT": {"name": "イベント", "color": 0xFFA500}
}

class BaseEndfieldEvent(dict):
    def __init__(self, raw_data, dif):
        super().__init__()
        self.raw_data = raw_data
        self.dif = dif
        self.update({
            "name": raw_data.get("name"),
            "dif": dif,
            "type": raw_data.get("type"),
            "description": raw_data.get("description", ""),
            "news": raw_data.get("news"),
            "link": raw_data.get("link"),
            "pic": raw_data.get("pic")
        })

    def parse(self):
        start = self.raw_data.get("startTime")
        end = self.raw_data.get("endTime")
        
        if self.dif == "present" or self.dif == "future":
            if start and end:
                self["time"] = f"> 開始: {format_time(start)}\n> 終了: {format_time(end)}"
        elif self.dif == "past":
            try:
                self["rewardEndTime"] = format_time(self.raw_data["rewardEndTime"])
            except KeyError:
                pass
        return self

    def build_embed(self) -> discord.Embed:
        if self.dif == "past":
            embed = discord.Embed(
                title=self.get("name"),
                description=f"- 攻略情報: [有志Wiki]({self.get('link')})\n> 報酬交換期限: {self.get('rewardEndTime')}",
                color=discord.Color.dark_grey(),
                url=self.get("link")
            )
            embed.set_author(name="終了したイベント")
            if self.get("pic"):
                embed.set_image(url=self.get("pic"))
            return embed

        event_type = self.get("type", "")
        style = ENDFIELD_EVENT_STYLES.get(event_type, ENDFIELD_EVENT_STYLES["DEFAULT"])
        color = style["color"]
        author_name = style["name"]
        
        if self.dif == "future":
            author_name = f"開催予定の{author_name}"
            
        embed = discord.Embed(
            title=self.get("name"),
            description=self.get("description", "") if self.dif == "present" else "",
            color=color
        )
        embed.set_author(name=author_name)
        
        if self.get("time"):
            embed.add_field(name="\u200b", value=self.get("time"), inline=False)
            
        if self.get("news"):
            embed.add_field(name="ニュース", value=f"[リンク]({self.get('news')})", inline=self.dif == "present")
            
        if self.dif == "present" and self.get("link"):
            embed.add_field(name="攻略情報", value=f"[リンク]({self.get('link')})", inline=True)
            
        if self.get("pic"):
            embed.set_image(url=self.get("pic"))
            
        return embed

class VersionCalendarHandler(BaseEndfieldEvent):
    def parse(self):
        self.update({
            "version": self.raw_data.get("version"),
            "images": self.raw_data.get("images", [])
        })
        return self

    def build_embed(self):
        embeds = []
        embed = discord.Embed(
            title=self.get("name"),
            description=f"**バージョン:** {self.get('version')}",
            color=discord.Color.dark_grey()
        )
        embed.set_author(name="バージョンスケジュール")
        images = self.get("images", [])
        if images:
            image_url = images[0]
            if "pbs.twimg.com" in image_url and not image_url.endswith((".jpg", ".png", ".webp")):
                image_url += ":large"
            embed.set_image(url=image_url)
        embeds.append(embed)
        
        for img_url in images[1:]:
            if "pbs.twimg.com" in img_url and not img_url.endswith((".jpg", ".png", ".webp")):
                img_url += ":large"
            img_embed = discord.Embed(color=discord.Color.dark_grey())
            img_embed.set_image(url=img_url)
            embeds.append(img_embed)
            
        return embeds
        
ENDFIELD_HANDLERS = {
    "VERSION_CALENDAR": VersionCalendarHandler
}

def get_endfield_handler(event_data, dif):
    event_type = event_data.get("type", "DEFAULT")
    HandlerClass = ENDFIELD_HANDLERS.get(event_type, BaseEndfieldEvent)
    return HandlerClass(event_data, dif).parse()

# ---- Select Options for /add_event ----
ALL_EVENT_CHOICES = [
    app_commands.Choice(name="【AK】危機契約", value="CRISIS"),
    app_commands.Choice(name="【AK】統合戦略", value="ROGUELIKE"),
    app_commands.Choice(name="【AK】生息演算", value="SANDBOX"),
    app_commands.Choice(name="【AK】殲滅作戦", value="BREAK"),
    app_commands.Choice(name="【AK】サイドストーリー", value="SIDESTORY"),
    app_commands.Choice(name="【AK】オムニバスストーリー", value="MINISTORY"),
    app_commands.Choice(name="【AK】導灯の試練", value="BOSS_RUSH"),
    app_commands.Choice(name="【AK】マルチイベント", value="MULTIPLAY"),
    app_commands.Choice(name="【AK】新章実装", value="MAIN"),
    app_commands.Choice(name="【AK】新章公開(事前準備)", value="SUPPORT"),
    app_commands.Choice(name="【AK】その他", value="DEFAULT"),
    app_commands.Choice(name="【EF】バージョンスケジュール", value="VERSION_CALENDAR"),
    app_commands.Choice(name="【EF】物語イベント", value="OPSTORY"),
    app_commands.Choice(name="【EF】案内イベント", value="GUIDE"),
    app_commands.Choice(name="【EF】理性消費軽減", value="SANITY"),
    app_commands.Choice(name="【EF】映像の記念碑等", value="MONUMENT"),
    app_commands.Choice(name="【EF】その他", value="OTHER")
]

def get_game_by_event_type(event_type: str) -> str:
    """Return 'endfield' or 'arknights' based on the event_type"""
    endfield_types = ["VERSION_CALENDAR", "OPSTORY", "MONUMENT", "GUIDE", "SANITY", "OTHER"]
    return "endfield" if event_type in endfield_types else "arknights"

