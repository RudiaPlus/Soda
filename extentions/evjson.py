import json
import os
import time
import datetime
from extentions import log, JSTTime

logger = log.setup_logger(__name__)
timeDay = JSTTime.timetoJST

def eventget():
    dir = os.path.abspath(__file__ + "/../")
    json_name = "jsons/events.json"
    with open(os.path.join(dir, json_name), encoding="utf-8") as f:
        event_dic = json.load(f)
        
        eventtime = 0
        eventEndtime = 0
        eventRewardEndTime = 0
        event_value = 0
        event_now = 0
        event_end = 0
        event_value_list = []
        event_now_list = []
        event_end_list = []
        events = []
        link = ""
        
        for k in event_dic.keys():
            #イベントのJsonから開始時間、終了時間、報酬受け取り期限を取得
            try:
                type =  event_dic[k]["type"]
                eventtime = event_dic[k]["startTime"]
                eventEndtime = event_dic[k]["endTime"]
                eventRewardEndTime = event_dic[k]["rewardEndTime"]
            
            except KeyError:
                pass
            
            #開始時間より今の時間が早かった場合、開催予定リストに入れる
            if time.time() < eventtime:
                event_value += 1
                event_value_list.append(k)
            
            #終了時間より今の時間が早かった場合、開催中リストに入れる    
            elif time.time() < eventEndtime:
                event_now += 1
                event_now_list.append(k)
            
            #報酬受け取り期限より今の時間が早かった場合、終了リストに入れる  
            elif time.time() < eventRewardEndTime:
                event_end += 1
                event_end_list.append(k)
        
        for i in range(len(event_now_list)):
            #開催中リストから「名前(name)、イベントの種類(type)、開始時間(startTime)、*終了時間(endTime)*、公式告知(news)、攻略リンク(link)、*ステージ追加(stageAdd)*」の有無を取得する←これらは必須です！
            #*ローグライクには必要なし
            try:
                name = event_dic[event_now_list[i]]["name"]
                type = event_dic[event_now_list[i]]["type"]
                startTime = "<t:{0}:F>( <t:{0}:R> )".format(event_dic[event_now_list[i]]["startTime"])
                
                if not type == "ROGUELIKE":
                    endTime = "<t:{0}:F>( <t:{0}:R> )".format(event_dic[event_now_list[i]]["endTime"])
                    stageAdd = event_dic[event_now_list[i]]["stageAdd"]
                news = event_dic[event_now_list[i]]["news"]    
                link = event_dic[event_now_list[i]]["link"]
                pic = event_dic[event_now_list[i]]["pic"]
            except KeyError as e:
                logger.exception(f"[event_now_list]にてエラー：{e}")
                                
            if type == "CRISIS":
                try:
                    dailyStage = event_dic[event_now_list[i]]["dailyStage"]
                    permStage = event_dic[event_now_list[i]]["permStage"]["stageName"]
                    eventColor = event_dic[event_now_list[i]]["eventColor"]
                except KeyError as e:
                    logger.exception(f"[CRISIS.dailyStage]にてエラー：{e}")
                
                dt = datetime.datetime.fromtimestamp(event_dic[event_now_list[i]]["startTime"] - 43200) #starttimeは16時なので、4時にするために-43200にする
                now = datetime.datetime.now()
                delta = now - dt
                crisis_day = delta.days + 1 #差の日にち+1日＝何日目
                
                if crisis_day == 1 or crisis_day == 2:
                    todaysDaily = dailyStage[0]
                else:
                    todaysDaily = dailyStage[crisis_day - 2]
                    
                if crisis_day >= 8:
                    contractAdd = True
                    contractAddTime = 0
                else:
                    contractAdd = False
                    contractAddTime = "<t:{0}:F>( <t:{0}:R> )".format(event_dic[event_now_list[i]]["firstAddTime"])
                    
                events.append({"name": name, "dif": "present", "type": type, "time": f"開始: {startTime}\n終了: {endTime}", "eventColor": eventColor, "permStage": permStage, "news": news, "link": link, "todaysDaily": todaysDaily, "contractAdd": contractAdd, "contractAddTime": contractAddTime, "pic": pic})
            
            elif type == "ROGUELIKE":
                try:
                    monthlyUpdate = event_dic[event_now_list[i]]["monthlyUpdate"]
                except KeyError as e:
                    logger.error(e)
                    
                month = content = updateEndTime = nextmonth = nextcontent = nextUpdateStartTime = None
                    
                if monthlyUpdate:
                    for update in monthlyUpdate:
                        if update["startTime"] < time.time() and time.time() < update["endTime"]:
                            
                            month = update["month"]
                            content = update["contents"]
                            updateEndTime = "<t:{0}:F>( <t:{0}:R> )".format(update["endTime"])
                            
                        elif time.time() < update["startTime"]:
                            
                            nextmonth = update["month"]
                            nextcontent = update["contents"]
                            nextUpdateStartTime = "<t:{0}:F>( <t:{0}:R> )".format(update["startTime"])
                            
                events.append({"name": name, "dif": "present", "type": type, "news": news, "link": link, "pic": pic, "month": month, "content": content, "updateTime": f"今月の任務終了: {updateEndTime}",
                               "nextmonth": nextmonth, "nextcontent": nextcontent, "nextUpdateTime": f"開始: {nextUpdateStartTime}"})    
                
            elif stageAdd == "True":
                try:
                    additionalStage = event_dic[event_now_list[i]]["additionalStage"]
                    stageAddTime = additionalStage[0]["startTime"]
                    remark = None
                except KeyError as e:
                    logger.error(e)
                    
                if additionalStage[0]["startTime"] > time.time():
                    nextStageName = additionalStage[0]["name"]
                    nextAddTime = "<t:{0}:F>( <t:{0}:R> )".format(additionalStage[0]["startTime"])
                    if len(additionalStage) == 1:
                        remark = "**このイベントはEXステージが登場予定です**\n"
                    elif len(additionalStage) == 2:
                        remark = "**このイベントはEXステージ、Sステージが登場予定です**\n"
                    else:
                        logger.error("予期されていないイベント内容です。")
                        continue
                        
                elif additionalStage[-1]["startTime"] > time.time():
                    nextStageName = additionalStage[1]["name"]
                    nextAddTime = "<t:{0}:F>( <t:{0}:R> )".format(additionalStage[1]["startTime"])
                    remark = "**EXステージが追加されました！**\n"
                    if len(additionalStage) == 2:
                        remark = "**EXステージが追加されました！Sステージが今後登場予定です**\n"
                
                elif len(additionalStage) == 1:
                    stageAdd = "False"
                    remark = "**EXステージが追加されました！**\n"
                    nextStageName = ""
                    nextAddTime = ""
                elif len(additionalStage) == 2:
                    stageAdd = "False"
                    remark = "**EXステージ、Sステージが追加されました！**\n"
                    nextStageName = ""
                    nextAddTime = ""
                else:
                    logger.error("予期されていないイベント内容です。")
                    continue
                    
                events.append({"name": name, "dif": "present", "type": type, "time": f"開始: {startTime}\n終了: {endTime}", "news": news, "link": link, "stageAdd": stageAdd, "nextStageName": nextStageName, "nextAddTime": nextAddTime, "pic": pic, "remark": remark})
                
            else:
                remark = None
                events.append({"name": name, "dif": "present", "type": type, "time": f"開始: {startTime}\n終了: {endTime}", "news": news, "link": link, "stageAdd": stageAdd, "pic": pic, "remark": remark})
            
        for i in range(len(event_end_list)):
            try:
                name = event_dic[event_end_list[i]]["name"]
                type = event_dic[event_end_list[i]]["type"]
                rewardEndTime = "<t:{0}:F>( <t:{0}:R> )".format(event_dic[event_end_list[i]]["rewardEndTime"])
                link = event_dic[event_end_list[i]]["link"]
                pic = event_dic[event_end_list[i]]["pic"]
            except KeyError as e:
                logger.exception(f"[event_end_list]にてエラー：{e}")
                
            events.append({"name": name, "dif": "past", "type": type, "rewardEndTime": rewardEndTime, "link": link, "pic": pic})
                
        
        for i in range(len(event_value_list)):
            
            if event_dic[event_value_list[i]]["type"] == "ROGUELIKE":
                
                try:
                    name = event_dic[event_value_list[i]]["name"]
                    type = event_dic[event_value_list[i]]["type"]
                    startTime = "<t:{0}:F>( <t:{0}:R> )".format(event_dic[event_value_list[i]]["startTime"])
                    news = event_dic[event_value_list[i]]["news"]
                    pic = event_dic[event_value_list[i]]["pic"]
                
                except KeyError as e:
                    logger.exception(f"[event_value_list]にてエラー：{e}")
                
                events.append({"name": name, "dif": "future", "type": type, "time": f"開始: {startTime}", "news": news, "pic": pic})                
                
            else:
            
                try:
                    name = event_dic[event_value_list[i]]["name"]
                    type = event_dic[event_value_list[i]]["type"]
                    startTime = "<t:{0}:F>( <t:{0}:R> )".format(event_dic[event_value_list[i]]["startTime"])
                    endTime = "<t:{0}:F>( <t:{0}:R> )".format(event_dic[event_value_list[i]]["endTime"])
                    news = event_dic[event_value_list[i]]["news"]
                    pic = event_dic[event_value_list[i]]["pic"]
                
                except KeyError as e:
                    logger.exception(f"[event_value_list]にてエラー：{e}")
                
                events.append({"name": name, "dif": "future", "type": type, "time": f"開始: {startTime}\n終了: {endTime}", "news": news, "pic": pic})
            
    return(events)

def eventcount():
    dir = os.path.abspath(__file__ + "/../")
    json_name = "jsons/events.json"
    with open(os.path.join(dir, json_name), encoding="utf-8") as f:
        event_dic = json.load(f)
        
        eventtime = 0
        eventEndtime = 0
        eventRewardEndTime = 0
        event_value = 0
        event_now = 0
        event_end = 0
        event_today = 0
        event_end_today = 0
        
        for k in event_dic.keys():
            try:
                type = event_dic[k]["type"]
                eventtime = event_dic[k]["startTime"]
                eventEndtime = event_dic[k]["endTime"]
                eventRewardEndTime = event_dic[k]["rewardEndTime"]
            
            except KeyError:
                pass
            
            if time.time() < eventtime:
                event_value += 1
                
                if timeDay(eventtime, type="m/d") == timeDay(time.time(), type="m/d"):
                    event_today += 1
                
            elif time.time() < eventEndtime and not type == "ROGUELIKE":
                event_now += 1
                
                if timeDay(eventEndtime, type="m/d") == timeDay(time.time()+86400, type="m/d"):
                    event_end_today += 1
            
            elif time.time() < eventRewardEndTime:
                event_end += 1
                
    logger.info(f"現在{event_now}個のイベントが進行中です")
    logger.info(f"開催予定のイベントは{event_value}個、終了したイベントは{event_end}個あります")
    logger.info(f"本日から始まるイベントは{event_today}個、本日で終了するイベントは{event_end_today}個です。")
    
    event_count = [event_now, event_end, event_value, event_today, event_end_today]        
    return(event_count)