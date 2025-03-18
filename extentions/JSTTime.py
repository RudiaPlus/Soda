import datetime
import math
import traceback
from extentions import log

logger = log.setup_logger()
t_delta = datetime.timedelta(hours=9)
tz_JST = datetime.timezone(t_delta, 'JST')

def timeJST(type: str):
    try:
        now = datetime.datetime.now(tz_JST)
        week = ["月","火","水","木","金","土","日"]
        weekday = week[now.weekday()]
        month = str(now.month).zfill(2)
        day = str(now.day).zfill(2)
        hour = str(now.hour).zfill(2)
        minute = str(now.minute).zfill(2)
        second = str(now.second).zfill(2)

        if type == "full":
            return(f"{now.year}年{now.month}月{now.day}日 ({weekday}) {now.hour}時{now.minute}分{now.second}秒")
        elif type == "raw":
            return(now)
        elif type == "hour":
            return(f"{now.hour}時{now.minute}分")
        elif type == "JST":
            return(tz_JST)
        elif type == "weekday":
            return(weekday)
        elif type == "m/d":
            return(f"{month}/{day}")
        elif type == "md":
            return(f"{month}{day}")
        elif type == "timestamp":
            return(math.floor(now.timestamp()))
        elif type == "timefull":
            return(f"{now.year}-{month}-{day} {hour}:{minute}:{second}")
        elif type == "time":   
            return(f"{hour}:{minute}")
        elif type == "file":
            return(f"{now.year}-{month}-{day}_{hour}-{minute}-{second}")
        else :
            raise ValueError("argument 'type' didn't match correctly.")
        
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
            
def timetoJST(timestamp: int, type: str) -> str:
    
    time = (datetime.datetime.fromtimestamp(timestamp, tz_JST))
    week = ["月","火","水","木","金","土","日"]
    weekday = week[time.weekday()]
    
    
    if type == "full":
        return(f"{time.year}年{time.month}月{time.day}日 ({weekday}) {time.hour}時{time.minute}分{time.second}秒")
    elif type == "m/d":
        return(f"{time.month}/{time.day}")
    elif type == "minute":
        return(f"{time.year}年{time.month}月{time.day}日 ({weekday}) {time.hour}時{time.minute}分")
    elif type == "hour":
        return(f"{time.hour}時{time.minute}分")
    else :
        return("3時12分")