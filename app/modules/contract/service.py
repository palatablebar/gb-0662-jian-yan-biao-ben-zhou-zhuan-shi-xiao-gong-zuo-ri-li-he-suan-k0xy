from app.modules.contract.versions import instant,select
from app.errors import RuleError
from app.reasons import SENTINELS

def normalize(rows,versions):
    valid=[];issues=[];groups={}
    for row in rows:groups.setdefault(row['specimen'].strip(),[]).append(row)
    for specimen,items in groups.items():
        # The complete signature prevents a later altered release from replacing earlier evidence.
        signatures={tuple(r[k].strip() for k in ('project','department','received','released','urgent')) for r in items}
        if len(signatures)>1:
            issues.extend({'line':r['line'],'code':'CONFLICT','raw':r} for r in items);continue
        row=min(items,key=lambda r:r['line'])
        issues.extend({'line':r['line'],'code':'DUPLICATE','raw':r} for r in items if r is not row)
        try:
            if any(row[k].strip() in SENTINELS for k in ('specimen','project','department','received','released')):raise RuleError('MISSING','标本必填项缺失')
            a=instant(row['received']);b=instant(row['released'])
            if b<a:raise RuleError('REVERSED','签发早于接收')
            if (b-a).total_seconds()>31*86400:raise RuleError('TOO_LONG','周转跨度超过31天')
            if row['urgent'].strip() not in ('0','1'):raise RuleError('URGENT','急诊标志只能为0或1')
            version=select(row['project'].strip(),a,versions)
            valid.append(dict(row,specimen=specimen,received=a.isoformat(),released=b.isoformat(),urgent=row['urgent'].strip()=='1',sla=version['urgent_sla'] if row['urgent'].strip()=='1' else version['sla'],rule_version=version['version']))
        except RuleError as e:issues.append({'line':row['line'],'code':e.code,'raw':row})
    return {'rows':valid,'issues':issues,'versions':versions}
