import datetime
import json
import os
import time
from math import floor

import requests
import arkprts
from bs4 import BeautifulSoup

from extentions import JSTTime, log, event_handlers

logger = log.setup_logger()
timeDay = JSTTime.timetoJST

async def gachaget():
    network=arkprts.NetworkSession("jp")
    announce_dict = await network.request("an")
    await network.close()
    gacha_dict = {}
    for announce in announce_dict["announceList"]:
        if "スカウト" in announce["title"] or "セレクト" in announce["title"] or "ロドスの道のり" in announce["title"]:
            announce_response = ""
            try:
                announce_response = requests.get(announce["webUrl"])
                gacha_soup = BeautifulSoup(announce_response.content, "html.parser")
                gacha_image = gacha_soup.find(class_="banner-image")
                gacha_image_url = gacha_image["src"]
                gacha_dict.update({announce["title"]: gacha_image_url})
                        
            except Exception as e:
                logger.error(e)
    return gacha_dict
                    

def eventget(game: str = "arknights"):
    """
    Get events for specified game
    Args:
        game: "arknights" or "endfield"
    """
    dir = os.path.abspath(__file__ + "/../")
    json_name = "jsons/events.json"
    with open(os.path.join(dir, json_name), encoding="utf-8") as f:
        all_events = json.load(f)
        
        # Get game-specific events
        event_dic = all_events.get(game, {})
        
        if game == "endfield":
            return _process_endfield_events(event_dic)
        else:
            return _process_arknights_events(event_dic)



def _process_arknights_events(event_dic: dict) -> list:
    """Process Arknights events (existing logic)"""
    
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
    
    for event_id in event_now_list:
        try:
            handler = event_handlers.get_arknights_handler(event_dic[event_id], 'present')
            events.append(handler)
        except Exception as e:
            logger.exception(f'[event_now_list]にてエラー：{e}')

    for event_id in event_end_list:
        try:
            handler = event_handlers.get_arknights_handler(event_dic[event_id], 'past')
            events.append(handler)
        except Exception as e:
            logger.exception(f'[event_end_list]にてエラー：{e}')

    for event_id in event_value_list:
        try:
            handler = event_handlers.get_arknights_handler(event_dic[event_id], 'future')
            events.append(handler)
        except Exception as e:
            logger.exception(f'[event_value_list]にてエラー：{e}')

    return events


def _process_endfield_events(event_dic: dict) -> list:
    """Process Endfield events with optional fields support"""
    events = []
    event_now_list = []
    event_end_list = []
    event_value_list = []
    version_calendar = None
    
    for k in event_dic.keys():
        try:
            event_type = event_dic[k]["type"]
            eventtime = event_dic[k]["startTime"]
            eventEndtime = event_dic[k]["endTime"]
            
            # Version calendar handling
            if event_type == "VERSION_CALENDAR":
                if eventtime <= time.time() < eventEndtime:
                    version_calendar = event_dic[k]
                continue
            
            # Categorize events by time
            if time.time() < eventtime:
                event_value_list.append(k)
            elif time.time() < eventEndtime:
                event_now_list.append(k)
            elif "rewardEndTime" in event_dic[k]:
                eventRewardEndTime = event_dic[k]["rewardEndTime"]
                if time.time() < eventRewardEndTime:
                    event_end_list.append(k)
        
        except KeyError:
            pass
    
    # Process current events
    for event_id in event_now_list:
        try:
            events.append(event_handlers.get_endfield_handler(event_dic[event_id], 'present'))
        except Exception as e:
            logger.error(f'Endfield present error: {e}')

    # Process ended events (reward period)
    for event_id in event_end_list:
        try:
            events.append(event_handlers.get_endfield_handler(event_dic[event_id], 'past'))
        except Exception as e:
            logger.error(f'Endfield past error: {e}')

    # Process future events
    for event_id in event_value_list:
        try:
            events.append(event_handlers.get_endfield_handler(event_dic[event_id], 'future'))
        except Exception as e:
            logger.error(f'Endfield future error: {e}')

    # Add version calendar at the beginning if exists
    if version_calendar:
        events.insert(0, event_handlers.get_endfield_handler(version_calendar, 'calendar'))

    return events


def eventcount(game: str = "arknights"):
    """
    Count events for specified game
    Args:
        game: "arknights" or "endfield"
    """
    dir = os.path.abspath(__file__ + "/../")
    json_name = "jsons/events.json"
    with open(os.path.join(dir, json_name), encoding="utf-8") as f:
        all_events = json.load(f)
        
        event_dic = all_events.get(game, {})
        
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
                
                # Skip version calendar
                if type == "VERSION_CALENDAR":
                    continue
                
                eventtime = event_dic[k]["startTime"]
                eventEndtime = event_dic[k]["endTime"]
                eventRewardEndTime = event_dic[k].get("rewardEndTime", 0)
            
            except KeyError:
                pass
            
            if time.time() < eventtime:
                event_value += 1
                
                if timeDay(eventtime, type="m/d") == timeDay(time.time(), type="m/d"):
                    event_today += 1
                
            elif time.time() < eventEndtime and not type == "ROGUELIKE" and not type == "SANDBOX":
                event_now += 1
                
                if timeDay(eventEndtime, type="m/d") == timeDay(time.time()+86400, type="m/d"):
                    event_end_today += 1
            
            elif eventRewardEndTime and time.time() < eventRewardEndTime:
                event_end += 1
                
        logger.info(f"[{game}] 現在{event_now}個のイベントが進行中です")
        logger.info(f"[{game}] 開催予定のイベントは{event_value}個、終了したイベントは{event_end}個あります")
        logger.info(f"[{game}] 本日から始まるイベントは{event_today}個、本日で終了するイベントは{event_end_today}個です。")
        
        event_count = [event_now, event_end, event_value, event_today, event_end_today]        
        return(event_count)