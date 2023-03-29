import datetime

def timeJST(type: str) -> str:
    
    t_delta = datetime.timedelta(hours=9)
    JST = datetime.timezone(t_delta, 'JST')
    now = datetime.datetime.now(JST)
    week = ["月","火","水","木","金","土","日"]
    weekday = week[now.weekday()]

    if type == "full":
        return(f"{now.year}年{now.month}月{now.day}日 ({weekday}) {now.hour}時{now.minute}分{now.second}秒")
    elif type == "hour":
        return(f"{now.hour}時{now.minute}分")
    elif type == "JST":
        return(JST)
    elif type == "weekday":
        return(weekday)
    elif type == "m/d":
        return(f"{now.month}/{now.day}")
    else :
        return("3時12分")
    
def timetoJST(timestamp: int, type: str) -> str:
    
    t_delta = datetime.timedelta(hours=9)
    JST = datetime.timezone(t_delta, 'JST')
    time = (datetime.datetime.fromtimestamp(timestamp, JST))
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