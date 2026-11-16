from decimal import Decimal,ROUND_CEILING

def percentile(values,q):
    if not values:return None
    ordered=sorted(Decimal(v) for v in values);rank=int((Decimal(len(ordered))*Decimal(q)).to_integral_value(rounding=ROUND_CEILING))
    return str(ordered[max(0,rank-1)])

def compare(intake,calculation,isolated):
    groups={}
    for row in calculation['rows']:groups.setdefault(row['department'],[]).append(row)
    departments=[]
    for name,rows in sorted(groups.items()):
        departments.append({'department':name,'total':len(rows),'late':sum(r['state']=='超时' for r in rows),'p50':percentile([r['elapsed_minutes'] for r in rows],'.5'),'p95':percentile([r['elapsed_minutes'] for r in rows],'.95')})
    delta=intake['input']-calculation['total']-isolated['total']-intake['blank']
    return {'input':intake['input'],'output':calculation['total'],'isolated':isolated['total'],'blank':intake['blank'],'row_delta':delta,'balanced':delta==0 and calculation['total']==calculation['pass']+calculation['late'],'departments':departments,'conclusion':'通过' if delta==0 else '不平'}
