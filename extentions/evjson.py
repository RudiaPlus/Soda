import json
import os
import time
import datetime

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

            
        print(f"【evjson.eventget】現在{event_now}個のイベントが進行中です")
        print(f"【evjson.eventget】開催予定のイベントは{event_value}個、終了したイベントは{event_end}個あります")
        
        for i in range(len(event_now_list)):
            #開催中リストから「名前、イベントの種類、開始時間、終了時間、攻略リンク、ステージ追加」の有無を取得する←これらは必須です！
            try:
                name = event_dic[event_now_list[i]]["name"]
                type = event_dic[event_now_list[i]]["type"]
                startTime = "<t:{0}:F>( <t:{0}:R> )".format(event_dic[event_now_list[i]]["startTime"])
                endTime = "<t:{0}:F>( <t:{0}:R> )".format(event_dic[event_now_list[i]]["endTime"])
                link = event_dic[event_now_list[i]]["link"]
                stageAdd = event_dic[event_now_list[i]]["stageAdd"]
                pic = event_dic[event_now_list[i]]["pic"]
            except KeyError as e:
                print(f"【evjson】event_now_listにてエラー：{e}")
                print(e)
                
            #
            if type == "CRISIS":
                try:
                    dailyStage = event_dic[event_now_list[i]]["dailyStage"]
                    permStage = event_dic[event_now_list[i]]["permStage"]["stageName"]
                except KeyError as e:
                    print(f"【evjson】CRISIS.dailyStageにてエラー：{e}")
                
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
                    
                events.append({"name": name, "dif": "present", "type": type, "time": f"開始: {startTime}\n終了: {endTime}", "permStage": permStage, "link": link, "todaysDaily": todaysDaily, "contractAdd": contractAdd, "contractAddTime": contractAddTime, "pic": pic})
                
            elif stageAdd == "True":
                try:
                    additionalStage = event_dic[event_now_list[i]]["additionalStage"]
                    stageAddTime = additionalStage[0]["startTime"]
                except KeyError as e:
                    print("stageAddにて")
                    
                if additionalStage[0]["startTime"] > time.time():
                    nextStageName = additionalStage[0]["name"]
                    nextAddTime = "<t:{0}:F>( <t:{0}:R> )".format(additionalStage[0]["startTime"])
                        
                elif additionalStage[-1]["startTime"] > time.time():
                    nextStageName = additionalStage[1]["name"]
                    nextAddTime = "<t:{0}:F>( <t:{0}:R> )".format(additionalStage[0]["startTime"])
                
                else:
                    stageAdd = "False"
                    nextStageName = ""
                    nextAddTime = ""
                    
                events.append({"name": name, "dif": "present", "type": type, "time": f"開始: {startTime}\n終了: {endTime}", "link": link, "stageAdd": stageAdd, "nextStageName": nextStageName, "nextAddTime": nextAddTime, "pic": pic})
                
            else:
                events.append({"name": name, "dif": "present", "type": type, "time": f"開始: {startTime}\n終了: {endTime}", "link": link, "stageAdd": stageAdd, "pic": pic})
            
        for i in range(len(event_end_list)):
            try:
                name = event_dic[event_end_list[i]]["name"]
                type = event_dic[event_end_list[i]]["type"]
                rewardEndTime = "<t:{0}:F>( <t:{0}:R> )".format(event_dic[event_end_list[i]]["rewardEndTime"])
                link = event_dic[event_end_list[i]]["link"]
                pic = event_dic[event_now_list[i]]["pic"]
            except KeyError as e:
                print("event_end_listにて")
                
            events.append({"name": name, "dif": "past", "type": type, "rewardEndTime": rewardEndTime, "link": link, "pic": pic})
                
        
        for i in range(len(event_value_list)):
            try:
                name = event_dic[event_value_list[i]]["name"]
                type = event_dic[event_value_list[i]]["type"]
                startTime = "<t:{0}:F>( <t:{0}:R> )".format(event_dic[event_value_list[i]]["startTime"])
                endTime = "<t:{0}:F>( <t:{0}:R> )".format(event_dic[event_value_list[i]]["endTime"])
                pic = event_dic[event_now_list[i]]["pic"]
            
            except KeyError as e:
                print("event_value_listにて")
            
            events.append({"name": name, "dif": "future", "type": type, "time": f"開始: {startTime}\n終了: {endTime}", "pic": pic})
            
    return(events)

def eventcount() :
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
        
        for k in event_dic.keys():
            try:
                eventtime = event_dic[k]["startTime"]
                eventEndtime = event_dic[k]["endTime"]
                eventRewardEndTime = event_dic[k]["rewardEndTime"]
            
            except KeyError:
                pass
            
            if time.time() < eventtime:
                event_value += 1
                
            elif time.time() < eventEndtime:
                event_now += 1
            
            elif time.time() < eventRewardEndTime:
                event_end += 1
    
    event_count = [event_now, event_end, event_value]        
    return(event_count)