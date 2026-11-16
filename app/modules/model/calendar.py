from datetime import datetime,timedelta,time
from zoneinfo import ZoneInfo
from decimal import Decimal
from app.errors import RuleError
ZONE=ZoneInfo('Asia/Shanghai')

def merge(intervals):
    out=[]
    for start,end in sorted(intervals):
        if end<=start:raise RuleError('PAUSE','暂停结束必须晚于开始')
        if out and start<=out[-1][1]:out[-1]=(out[-1][0],max(end,out[-1][1]))
        else:out.append((start,end))
    return out

def intersection(a,b):
    start=max(a[0],b[0]);end=min(a[1],b[1]);return (start,end) if start<end else None

def minutes(intervals):
    return sum((Decimal(str((b-a).total_seconds()))/60 for a,b in intervals),Decimal(0))

def windows(start,end,calendar):
    day=start.astimezone(ZONE).date();last=end.astimezone(ZONE).date();out=[]
    while day<=last:
        if day.weekday() in calendar['weekdays'] and day.isoformat() not in calendar['holidays']:
            for a,b in calendar['hours']:
                left=datetime.combine(day,time.fromisoformat(a),ZONE);right=datetime.combine(day,time.fromisoformat(b),ZONE)
                if right<=left:raise RuleError('CALENDAR','工作区间必须同日且有序')
                hit=intersection((start,end),(left,right))
                if hit:out.append(hit)
        day+=timedelta(days=1)
    return merge(out)
