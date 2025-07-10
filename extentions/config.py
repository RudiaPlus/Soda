import datetime
import json
import os


class Config():
    def __init__(self):
        
        #~~~~static: not rewritable config.~~~~
        
        self.dir = os.path.abspath(__file__ + "/../")
        
        #ABILITY SWITCH
        self.test = False #TESTMODE(Switch to OverRein), default = False
        self.logging = True #Write log to your file, default = True
        self.voicechat = True #Voicechat command
        self.voice_suggest = True #suggest text speech to voicechat user
        self.selenium = True #use selenium to correct twitterpost exc.
        self.voice_clients = 5 #voice clients number

        #CLIENTS
        self.voice_clients_id = [1321765242489016340, 1322054520364208231, 1322063853231804426, 1322066754171834480, 1322067201972375664]

        #MAIN
        self.t_delta = datetime.timedelta(hours=9)
        self.JST = datetime.timezone(self.t_delta, 'JST')

        self.test_client = os.environ["TEST_DISCORD_TOKEN"]
        self.token = os.environ["DISCORD_TOKEN"]
        self.voice_tokens = [os.environ["DISCORD_VOICE_TOKEN_01"], os.environ["DISCORD_VOICE_TOKEN_02"], os.environ["DISCORD_VOICE_TOKEN_03"], os.environ["DISCORD_VOICE_TOKEN_04"], os.environ["DISCORD_VOICE_TOKEN_05"]]

        self.server_invite_link = "https://discord.gg/AshC"
        self.server_rule_link = "https://discord.com/channels/1018858818345631745/1018858818932842589/1018863690914729986"
        self.community_guideline_link = "https://discord.com/guidelines"
        self.main_server = 1018858818345631745 #あしたはこぶね
        self.testserverid = 1059155328584908810 #メンテナンス部屋

        self.collect_agree_days = 7 * 86400 #聖堂の取得日数　86400 = 1日

        self.me = 870729549833465917 #rudiaのユーザーID
        self.server_icon = "https://cdn.discordapp.com/icons/1018858818345631745/a_8025349dd827dee56db7088ef01ccae7.webp?size=1024"


        #RECRUIT
        self.tagList = ["上級エリート", "エリート", "初期", "ロボット", "前衛タイプ", "狙撃タイプ", "重装タイプ", "医療タイプ", "補助タイプ", 
                "術師タイプ", "特殊タイプ", "先鋒タイプ", "近距離", "遠距離", "治療", "支援", "生存", "火力", "減速", "COST回復", 
                "強制移動", "高速再配置", "弱化", "防御", "範囲攻撃", "爆発力" , "召喚" ,"牽制", "元素"]

        self.tag_rarity = ["上級エリート", "エリート", "初期", "ロボット"]

        self.tag_profession = ["前衛タイプ", "狙撃タイプ", "重装タイプ", "医療タイプ", "補助タイプ", "術師タイプ", "特殊タイプ", "先鋒タイプ"]

        self.tag_range = ["近距離", "遠距離"]

        self.tag_type = ["治療", "支援", "生存", "火力", "減速", "COST回復", "強制移動", "高速再配置", "弱化", "防御", "範囲攻撃", "爆発力" , "召喚" ,"牽制", "元素"]

        #OPERATOR
        self.operator_classes = {"先鋒": "PIONEER", "前衛": "WARRIOR", "重装": "TANK", "狙撃": "SNIPER", "術師": "CASTER", "医療": "MEDIC", "補助": "SUPPORT", "特殊": "SPECIAL"}
        self.profession_id_to_name = {"SNIPER": "狙撃", "TANK": "重装", "MEDIC": "医療", "SPECIAL": "特殊", "PIONEER": "先鋒", "CASTER": "術師", "WARRIOR": "前衛", "SUPPORT": "補助"}

        #TASK TIME
        self.morningtime = datetime.time(hour=4, minute=00, tzinfo=self.JST)
        self.threadtime = datetime.time(hour=6, minute=30, tzinfo=self.JST)
        self.afternoontime = datetime.time(hour=10, minute=00, tzinfo=self.JST)
        self.eveningtime = datetime.time(hour=16, minute=00, tzinfo=self.JST)
        self.newdaytime = datetime.time(hour=0, minute=00, tzinfo=self.JST)


        #ROLE
        self.administrator_role = 1019295385967149057 #Administrator(赤)
        self.Moderator_role = 1093773233410547735 #Moderator(橙)
        self.cathedral_NG_role = 1183346673469100043 #聖堂NG
        self.server_app_role = 1019206899209605190 #愉快な仲間たち（bot）
        self.vc_allowed_role = 1155320615922843748 #情報郷友会(VC)
        self.user_bot_role = 1207273509462736966 #私はbotです。追放してください。
        self.spam_role = 1207273509462736966 #私はbotです


        #CHANNEL

        self.remind_TEST = 1156850119451353110 #メンテナンス部屋/リマインド
        self.remind = 1140326740158333048 if self.test is False else self.remind_TEST  #リマインド
        self.ake_news_test = 1166921222785859684 #メンテナンス部屋/ニューステスト
        self.ake_news = 1166620310750113802 if self.test is False else self.ake_news_test #ニュース

        self.cathedral = 1183254115338420285 if self.test is False else self.ake_news_test #聖堂


        self.maintenance = 1081251314958344313 #メンテナンス
        self.request = 1093849433621401600 if self.test is False else 1285907503695007846#サポートリクエスト
        self.request_url = f"https://discord.com/channels/{self.main_server}/{self.request}" if self.test is False else f"https://discord.com/channels/{self.testserverid}/{self.request}"

        self.chat = 1072158278634713108  #bot/ロードの部屋

        self.action_logs = 1111276658540937308 #action-logs
        self.moderatorchannel = 1093777243601371157 #botmoderate
        self.modmail_save_channel = 1108480334024167514 #議事録

        self.screenshot_recruit_channel = 1284115621465948171 #公開求人ツール（スクショ認識）
        self.screenshot_recruit_channel_url = f"https://discord.com/channels/{self.main_server}/{self.screenshot_recruit_channel}"

        self.voicecreate_channel = 1305508824781815899 #個別VC作成方法
        self.voicecreate_vc = 1305536169924231229 #>>VC作成<<

        self.vccreate_log_channel = 1305570776690200636 #個別VCチャットログ
        self.multiplay_request_channel = 1306450120669139024 #

        self.logging_channel = 1318532200588640297
        
        self.event_stage_channel = 1232585432756129813 #イベント

        self.announcement = 1019202000975560754 #アナウンス


        #categories
        self.feedback_category = 1108189699715125268
        self.vccreate_category = 1305500357958307860
        
        #Twitter
        self.twitter_account_name = "Eluneige"
        self.twitter_account_token = os.environ["TWITTER_ACCOUNT_TOKEN"]
        self.notify_list_id = 1936269194817163642 #通知リストID

        #speech
        self.default_waveform_base64 = "acU6Va9UcSVZzsVw7IU/80s0Kh/pbrTcwmpR9da4mvQejIMykkgo9F2FfeCd235K/atHZtSAmxKeTUgKxAdNVO8PAoZq1cHNQXT/PHthL2sfPZGSdxNgLH0AuJwVeI7QZJ02ke40+HkUcBoDdqGDZeUvPqoIRbE23Kr+sexYYe4dVq+zyCe3ci/6zkMWbVBpCjq8D8ZZEFo/lmPJTkgjwqnqHuf6XT4mJyLNphQjvFH9aRqIZpPoQz1sGwAY2vssQ5mTy5J5muGo+n82b0xFROZwsJpumDsFi4Da/85uWS/YzjY5BdxGac8rgUqm9IKh7E6GHzOGOy0LQIz3O4ntTg=="

        self.aivis_speaker_ids = {
            "ノーマル": 888753760,
            "通常": 888753761,
            "テンション高め": 888753762,
            "落ち着き": 888753763,
            "上機嫌": 888753764,
            "怒り・悲しみ": 888753765
            }
        
        #~~~~dynamic: rewritable config.~~~~
        self.dynamic = {}
    
    #load
    def load_dynamic_config(self):
        with open(os.path.join(self.dir, "configs\\dynamic.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        self.dynamic = data
        
    def reload(self):
        self.load_dynamic_config()
    
    #write
    def write_dynamic_config(self):
        with open(os.path.join(self.dir, "configs\\dynamic.json"), "w", encoding="utf-8") as f:
            json.dump(self.dynamic, f, indent=4, ensure_ascii=False)
        self.reload()
        
    #dynamic_set
    def dynamic_set(self, key, value):
        self.dynamic[key] = value
        self.write_dynamic_config()
        
    #add_recruit_list (overwrite existing list if exists in dynamic.json)
    def add_recruit_list(self, diff_list: list):
        if "recruit_list" not in self.dynamic:
            self.dynamic["recruit_list"] = []
        self.dynamic["recruit_list"] = self.dynamic["recruit_list"] + diff_list
        self.write_dynamic_config()
        


config = Config()
config.reload()