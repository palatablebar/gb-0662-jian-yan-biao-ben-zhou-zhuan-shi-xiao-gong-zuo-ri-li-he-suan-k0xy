from fastapi.templating import Jinja2Templates
from app.config import ROOT
from app import store
from app.modules.batches import formal
PAGES=[('intake','标本采信'),('contract','项目契约'),('model','节假日历'),('calculate','时效计算'),('quarantine','异常隔离'),('reconcile','科室对账'),('batches','批次复核')]
templates=Jinja2Templates(directory=str(ROOT/'app/templates'))
def _previous(items):
    """The revision the active one replaced, so the restore button names the right target."""
    active=next((c for c in items if c['active']),None)
    if not active:return None
    return next((c for c in items if c['superseded_by']==active['revision']),None)
ACTIONS={'review':'复核','lock':'定版','restore':'恢复'}
OUTCOMES={'approved':'通过','stale':'版本过期','activated':'生效','reactivated':'恢复生效','idempotent':'幂等复用'}
def _audit_rows(items):
    rows=[]
    for item in items:
        detail=item['detail'] or {}
        parts=[]
        if 'revision' in detail:parts.append(f"修订 v{detail['revision']}")
        if detail.get('replaced'):parts.append(f"替代 v{detail['replaced']}")
        if detail.get('restored'):parts.append(f"恢复 v{detail['restored']}")
        if detail.get('cutoff'):parts.append(f"截止 {detail['cutoff']}")
        counts=detail.get('counts') or {}
        if counts:parts.append(f"纳入 {counts.get('total')} / 超时 {counts.get('late')}")
        rows.append(dict(item,action=ACTIONS.get(item['action'],item['action']),
                         outcome=OUTCOMES.get(item['outcome'],item['outcome']),detail='；'.join(parts) or '—'))
    return rows
def page(request,slug):
    from datetime import date,timedelta
    bundle=store.latest();history=store.history();calendar=bundle['model']['calendar'];first=date(2026,11,2)
    days=[{'day':(first+timedelta(days=i)).strftime('%d'),'working':(first+timedelta(days=i)).weekday() in calendar['weekdays'] and (first+timedelta(days=i)).isoformat() not in calendar['holidays'],'hours':calendar['hours']} for i in range(7)]
    counted=formal.decorate(bundle['calculate'],formal.state(bundle,store.active(),store.arrivals()))
    conclusions=store.conclusions();reviews=_audit_rows(store.reviews())
    counts=[(bundle['intake']['input'],len(bundle['intake']['rows']),len(bundle['intake']['issues'])),(len(bundle['intake']['rows']),len(bundle['contract']['rows']),len(bundle['contract']['issues'])),(len(bundle['contract']['rows']),len(bundle['model']['rows']),len(bundle['model']['issues'])),(len(bundle['model']['rows']),bundle['calculate']['total'],0),(bundle['reconcile']['input'],bundle['quarantine']['total'],bundle['quarantine']['total']),(bundle['reconcile']['input'],bundle['reconcile']['output'],bundle['reconcile']['isolated']),(len(history),len(conclusions),0)]
    context={'bundle':bundle,'pages':PAGES,'slug':slug,'title':dict(PAGES)[slug],'history':history,
             'calendar_days':days,'stage_counts':counts,'formal':counted['formal'],
             'calculation':counted,'conclusions':conclusions,'reviews':reviews,
             'previous':_previous(conclusions)}
    return templates.TemplateResponse(request=request,name=slug+'.html',context=context)
