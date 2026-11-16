from datetime import datetime,timezone
from app.errors import RuleError

def instant(s):
    try:
        d=datetime.fromisoformat(s.replace('Z','+00:00'))
        if d.tzinfo is None:raise ValueError()
        return d.astimezone(timezone.utc)
    except (ValueError,TypeError):raise RuleError('TIME','时间必须含时区偏移')

def select(project,at,versions):
    candidates=[v for v in versions if v['project']==project]
    if not candidates:raise RuleError('PROJECT','检验项目未登记')
    matched=[v for v in candidates if instant(v['start'])<=at<instant(v['end'])]
    if len(matched)!=1:raise RuleError('VERSION','项目规则版本重叠或缺失')
    return matched[0]
