from fastapi.templating import Jinja2Templates
from app.config import ROOT
from app import store
PAGES=[('intake','标本采信'),('contract','项目契约'),('model','节假日历'),('calculate','时效计算'),('quarantine','异常隔离'),('reconcile','科室对账'),('batches','批次复核')]
templates=Jinja2Templates(directory=str(ROOT/'app/templates'))
def page(request,slug):
    from datetime import date,timedelta
    bundle=store.latest();history=store.history();calendar=bundle['model']['calendar'];first=date(2026,11,2)
    days=[{'day':(first+timedelta(days=i)).strftime('%d'),'working':(first+timedelta(days=i)).weekday() in calendar['weekdays'] and (first+timedelta(days=i)).isoformat() not in calendar['holidays'],'hours':calendar['hours']} for i in range(7)]
    counts=[(bundle['intake']['input'],len(bundle['intake']['rows']),len(bundle['intake']['issues'])),(len(bundle['intake']['rows']),len(bundle['contract']['rows']),len(bundle['contract']['issues'])),(len(bundle['contract']['rows']),len(bundle['model']['rows']),len(bundle['model']['issues'])),(len(bundle['model']['rows']),bundle['calculate']['total'],0),(bundle['reconcile']['input'],bundle['quarantine']['total'],bundle['quarantine']['total']),(bundle['reconcile']['input'],bundle['reconcile']['output'],bundle['reconcile']['isolated']),(len(history),len(history),0)]
    return templates.TemplateResponse(request=request,name=slug+'.html',context={'bundle':bundle,'pages':PAGES,'slug':slug,'title':dict(PAGES)[slug],'history':history,'calendar_days':days,'stage_counts':counts})
