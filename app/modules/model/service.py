from datetime import datetime
from decimal import Decimal
from app.modules.model.calendar import merge,intersection,minutes,windows
from app.modules.contract.service import instant
from app.errors import RuleError

def build(rows,calendar,pauses):
    result=[];issues=[]
    for row in rows:
        a=instant(row['received']);b=instant(row['released'])
        try:
            work=[(a,b)] if row['urgent'] and b>a else ([] if row['urgent'] else windows(a,b,calendar))
            approved=[]
            for pause in pauses.get(row['specimen'],[]):
                if not pause.get('approved'):continue
                left=instant(pause['start']);right=instant(pause['end'])
                if right<=left:raise RuleError('PAUSE','暂停区间结束不晚于开始')
                hit=intersection((a,b),(left,right))
                if hit:approved.append(hit)
            merged=merge(approved)
            deduction=minutes([hit for w in work for p in merged if (hit:=intersection(w,p))])
            gross=minutes(work);natural=Decimal(str((b-a).total_seconds()))/60
            result.append(dict(row,working_minutes=str(gross),pause_minutes=str(deduction),elapsed_minutes=str(gross-deduction),natural_minutes=str(natural),windows=[{'start':x.isoformat(),'end':y.isoformat()} for x,y in work],pause_count=len(merged)))
        except RuleError as e:issues.append({'line':row['line'],'code':e.code,'raw':row})
    return {'rows':result,'issues':issues,'calendar':calendar,'pauses':pauses}
