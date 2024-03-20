import datetime
import os

#ABILITY SWITCH
test = False #TESTMODE(Switch to OverRein), default = False
logging = True #Write log to your file, default = True
voicechat = False #Voicechat command
voice_suggest = False #suggest text speech to voicechat user

#MAIN
t_delta = datetime.timedelta(hours=9)
JST = datetime.timezone(t_delta, 'JST')

test_client = os.environ["TEST_DISCORD_TOKEN"]
token = os.environ["DISCORD_TOKEN"]

server_invite_link = "https://discord.gg/AshC"
server_rule_link = "https://discord.com/channels/1018858818345631745/1018858818932842589/1018863690914729986"
community_guideline_link = "https://discord.com/guidelines"
main_server = 1018858818345631745 #あしたはこぶね
testserverid = 1059155328584908810 #メンテナンス部屋

openAI_key = os.environ["OPENAI_API_KEY"]

me = 870729549833465917 #rudiaのユーザーID
server_icon = "https://cdn.discordapp.com/icons/1018858818345631745/a_8025349dd827dee56db7088ef01ccae7.webp?size=1024"


#RECRUIT
tagList = ["上級エリート", "エリート", "初期", "ロボット", "前衛タイプ", "狙撃タイプ", "重装タイプ", "医療タイプ", "補助タイプ", 
           "術師タイプ", "特殊タイプ", "先鋒タイプ", "近距離", "遠距離", "治療", "支援", "生存", "火力", "減速", "COST回復", 
           "強制移動", "高速再配置", "弱化", "防御", "範囲攻撃", "爆発力" , "召喚" ,"牽制"]

tag_rarity = ["上級エリート", "エリート", "初期", "ロボット"]

tag_profession = ["前衛タイプ", "狙撃タイプ", "重装タイプ", "医療タイプ", "補助タイプ", "術師タイプ", "特殊タイプ", "先鋒タイプ"]

tag_range = ["近距離", "遠距離"]

tag_type = ["治療", "支援", "生存", "火力", "減速", "COST回復", "強制移動", "高速再配置", "弱化", "防御", "範囲攻撃", "爆発力" , "召喚" ,"牽制"]

recruitList = ["Lancet-2", "Castle-3", "THRM-EX", "ジャスティスナイト", "ヤトウ", "ノイルホーン", "レンジャー", "ドゥリン", 
               "12F", "アドナキエル", "フェン", "バニラ", "プリュム", "メランサ", "ビーグル", "クルース", "ラヴァ", 
               "ハイビスカス", "アンセル", "スチュワード", "オーキッド", "カタパルト", "ミッドナイト", "ポプカル", "スポット", 
               "エステル", "セイリュウ", "ヘイズ", "ギターノ", "ジェシカ", "メテオ", "シラユキ", "スカベンジャー", "ヴィグナ", 
               "ドーベルマン", "マトイマル", "フロストリーフ", "ムース", "グラベル", "ロープ", "ミルラ", "パフューマー", 
               "マッターホルン", "クオーラ", "グム", "アーススピリット", "ショウ", "ビーハンター", "グレイ", "ススーロ", "テンニンカ", 
               "ヴァーミル", "メイ", "アンブリエル", "ウタゲ", "カッター", "ポデンコ", "インドラ", "ヴァルカン", "フィリオプシス", 
               "ズィマー", "テキサス", "スペクター", "アズリウス", "プラチナ", "メテオリーテ", "メイヤー", "サイレンス", "ワルファリン", 
               "ニアール", "レッド", "リスカム", "クロワッサン", "プロヴァンス", "ファイヤーウォッチ", "クリフハート", "プラマニクス", 
               "イースチナ", "マンティコア", "エフイーター", "ナイトメア", "スワイヤー", "グラウコス", "アステシア", "イグゼキュター", 
               "ワイフー", "グレースロート", "リード", "ブローカ", "ウン", "レイズ", "シェーシャ", "シャマレ", "エリジウム", 
               "アスベストス", "ツキノギ", "レオンハルト", "エクシア", "シージ", "イフリータ", "シャイニング", "ナイチンゲール", 
               "ホシグマ", "サリア", "シルバーアッシュ", "スカジ", "チェン", "シュヴァルツ", "ヘラグ", "マゼラン", "モスティマ", 
               "ブレイズ", "ア", "ケオベ", "バグパイプ", "ファントム", "ウィーディ", "ロサ", "スズラン", "エアースカーペ", "カシャ",
               "Friston-3", "ソーンズ", "アンドレアナ", "キアーベ", "ビーズワクス", "ジェイ"]

#OPERATOR
operator_classes = {"先鋒": "PIONEER", "前衛": "WARRIOR", "重装": "TANK", "狙撃": "SNIPER", "術師": "CASTER", "医療": "MEDIC", "補助": "SUPPORT", "特殊": "SPECIAL"}

#TASK TIME
morningtime = datetime.time(hour=4, minute=00, tzinfo=JST)
threadtime = datetime.time(hour=6, minute=30, tzinfo=JST)
afternoontime = datetime.time(hour=10, minute=00, tzinfo=JST)
eveningtime = datetime.time(hour=16, minute=00, tzinfo=JST)
newdaytime = datetime.time(hour=0, minute=00, tzinfo=JST)


#ROLE
administrator_role = 1019295385967149057 #Administrator(赤)
Moderator_role = 1093773233410547735 #Moderator(橙)
cathedral_NG_role = 1183346673469100043 #聖堂NG
user_bot_role = 1207273509462736966 #私はbotです。追放してください。


#CHANNEL

remind_TEST = 1156850119451353110 #メンテナンス部屋/リマインド
remind = 1140326740158333048 if test == False else remind_TEST  #リマインド
ake_news_test = 1166921222785859684 #メンテナンス部屋/ニューステスト
ake_news = 1166620310750113802 if test == False else ake_news_test #ニュース

cathedral = 1183254115338420285 if test == False else ake_news_test #聖堂


maintenance = 1081251314958344313 #メンテナンス
request = 1093849433621401600 #サポートリクエスト

chat = 1072158278634713108  #bot/ロードの部屋

action_logs = 1111276658540937308 #action-logs
moderatorchannel = 1093777243601371157 #botmoderate
modmail_save_channel = 1108480334024167514 #議事録


#categories
feedback_category = 1108189699715125268