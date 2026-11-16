from app.modules.calculate.sla import judge
from app.errors import RuleError
from decimal import Decimal,InvalidOperation

def calculate(rows,grace='0'):
    try:g=Decimal(str(grace))
    except InvalidOperation:raise RuleError('PARAMETER','宽限分钟必须为数字')
    if not g.is_finite() or g<0 or g>60:raise RuleError('PARAMETER','宽限分钟应为0至60')
    out=[judge(r,str(g)) for r in rows]
    return {'rows':out,'pass':sum(r['state']=='达标' for r in out),'late':sum(r['state']=='超时' for r in out),'grace':str(g),'total':len(out)}
