import hashlib,json
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from app.errors import RuleError

ZONE=ZoneInfo('Asia/Shanghai')
BASIS_FIELDS=('department','project','urgent','clock','elapsed_minutes','pause_minutes','pause_count',
              'limit_minutes','overdue_minutes','state','sla','rule_version')
COMPARE_FIELDS=('received','department','urgent','clock','elapsed_minutes','pause_minutes','limit_minutes',
                'overdue_minutes','state','sla','rule_version')
FORMAL_LABELS={'late_backfill':'补录已纳入','overdue_backfill':'超窗待裁定','adjusted':'依据已变更',
               'included':'已纳入','next_period':'下一周期','withdrawn':'已移出','unlocked':'未纳入',
               'recovered':'重新采信'}
STATUS_LABELS={'none':('none','未定版'),'current':('current','与正式结论一致'),
               'pending_relock':('pending_relock','待重新定版'),
               'pending_decision':('pending_decision','有超窗补录，待裁定')}

def moment(value,code='CUTOFF',label='统计截止时点'):
    if value in (None,''):return None
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if d.tzinfo is None:raise ValueError()
        return d.astimezone(timezone.utc)
    except (ValueError,TypeError):raise RuleError(code,f'{label}必须带时区偏移')

def as_text(value):return value.astimezone(timezone.utc).isoformat()

def default_cutoff(bundle):
    """Period boundary: first Shanghai midnight after the latest receipt in this run."""
    received=[moment(r['received']) for r in bundle['calculate']['rows']]
    if not received:raise RuleError('CUTOFF','没有可纳入的标本，请提供统计截止时点')
    day=max(received).astimezone(ZONE).date()+timedelta(days=1)
    return datetime.combine(day,datetime.min.time(),ZONE).astimezone(timezone.utc)

def backfill_hours(value):
    try:h=Decimal(str(value if value not in (None,'') else '24'))
    except Exception:raise RuleError('WINDOW','补录窗口必须为数字小时')
    if not h.is_finite() or h<0 or h>168:raise RuleError('WINDOW','补录窗口应为0至168小时')
    return h

def _frozen(row,arrival):
    out={'specimen':row['specimen'],'received':row['received'],'released':row['released'],'line':row['line']}
    for key in BASIS_FIELDS:out[key]=row[key]
    out['arrival']=arrival.get('at');out['arrival_seq']=arrival.get('seq')
    return out

def build(bundle,cutoff=None,window='24',arrivals=None,allow_empty=False):
    """Freeze a self-contained, reproducible basis for one formal conclusion.

    ``arrivals`` maps specimen -> {'at','seq'} provenance so that a specimen
    entering the ledger after this revision was locked can be explained even
    when its receipt time falls inside the closed period.
    """
    arrivals=arrivals or {}
    boundary=moment(cutoff)
    if boundary is None:boundary=default_cutoff(bundle)
    hours=backfill_hours(window)
    rows=bundle['calculate']['rows']
    inside=sorted([r for r in rows if moment(r['received'])<boundary],key=lambda r:r['specimen'])
    outside=sorted([r for r in rows if moment(r['received'])>=boundary],key=lambda r:r['specimen'])
    frozen=[_frozen(r,arrivals.get(r['specimen'],{})) for r in inside]
    if not frozen and not allow_empty:raise RuleError('SCOPE_EMPTY','统计截止前没有可纳入的标本，请调整截止时点')
    isolated=[{'line':i['line'],'code':i['code'],
               'specimen':i['raw'].get('specimen') if isinstance(i['raw'],dict) else None}
              for i in bundle['quarantine']['rows']]
    counts={'input':bundle['reconcile']['input'],'total':len(inside),
            'pass':sum(r['state']=='达标' for r in inside),'late':sum(r['state']=='超时' for r in inside),
            'isolated':len(isolated),'blank':bundle['intake']['blank'],
            'out_of_scope':len(outside),'run_total':len(rows)}
    # Scope identity: every input row is in scope, rejected, blank, or deferred to
    # the next period. This is what lets one batch explain the backfill quantity.
    counts['scope_balanced']=(counts['input']==counts['total']+counts['isolated']+counts['blank']+counts['out_of_scope'])
    evidence={'cutoff':as_text(boundary),'backfill_hours':str(hours),
              'run_id':bundle['manifest']['run_id'],'run_created_at':bundle['manifest']['created_at'],
              'rule_version':bundle['manifest']['rule_version'],
              'parameters':bundle['manifest']['parameters'],'references':bundle['manifest']['references'],
              'counts':counts,'rows':frozen,
              'out_of_scope':[r['specimen'] for r in outside],
              'timeouts':[r['specimen'] for r in inside if r['state']=='超时'],
              'isolated':isolated}
    # The digest identifies the calculation basis; arrival provenance changes when
    # the ledger is re-imported, so it is excluded to keep same-calculation retries
    # on the same digest.
    hashed=[{k:v for k,v in row.items() if k not in ('arrival','arrival_seq')} for row in frozen]
    digest_input={k:evidence[k] for k in ('cutoff','backfill_hours','run_id','rule_version','parameters',
                                          'references','out_of_scope','isolated')}
    digest_input['rows']=hashed
    evidence['digest']=hashlib.sha256(json.dumps(digest_input,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return evidence

def _index(evidence):return {r['specimen']:r for r in evidence['rows']}

def compare(active,current,lock_time):
    """Explain every count, timeout name and basis field between two revisions."""
    before=_index(active);after=_index(current)
    # The backfill window runs from the moment the revision was locked: records the
    # department supplies shortly after review are auto-included in the next lock,
    # while anything later needs an explicit human decision before it moves a
    # closed figure.
    lock_time=moment(lock_time,label='定版时点')
    deadline=lock_time+timedelta(hours=float(active['backfill_hours']))
    floor=active.get('arrival_floor') or 0
    added=[after[s] for s in sorted(set(after)-set(before))]
    removed=[before[s] for s in sorted(set(before)-set(after))]
    changed=[]
    for specimen in sorted(set(before)&set(after)):
        a,b=before[specimen],after[specimen]
        fields={k:{'before':a[k],'after':b[k]} for k in COMPARE_FIELDS if a[k]!=b[k]}
        if not a.get('arrival') or not b.get('arrival'):
            fields.setdefault('arrival',{'before':a.get('arrival'),'after':b.get('arrival')})
        if fields:changed.append({'specimen':specimen,'fields':fields})

    late_added=[];overdue_added=[];recovered=[]
    for row in added:
        arrival=moment(row.get('arrival'),label='标本到达时点') if row.get('arrival') else None
        if arrival is None:
            # No provenance: treat conservatively as a backfill needing a decision,
            # never silently expand a closed figure.
            overdue_added.append(row['specimen']);continue
        is_new=(row.get('arrival_seq') or 0)>floor or arrival>lock_time
        if not is_new:recovered.append(row['specimen']);continue
        # Half-open window [lock, lock+hours): a zero-hour window tolerates nothing after lock.
        (late_added if arrival<deadline else overdue_added).append(row['specimen'])

    states={}
    for row in current['rows']:states[row['specimen']]='included'
    for item in changed:states[item['specimen']]='adjusted'
    for specimen in recovered:states[specimen]='recovered'
    for specimen in late_added:states[specimen]='late_backfill'
    for specimen in overdue_added:states[specimen]='overdue_backfill'
    for specimen in current['out_of_scope']:states[specimen]='next_period'
    for row in removed:states[row['specimen']]='withdrawn'

    shared=set(before)&set(after)
    pass_to_late=sum(1 for s in shared if before[s]['state']=='达标' and after[s]['state']=='超时')
    late_to_pass=sum(1 for s in shared if before[s]['state']=='超时' and after[s]['state']=='达标')
    added_pass=sum(r['state']=='达标' for r in added);added_late=len(added)-added_pass
    removed_pass=sum(r['state']=='达标' for r in removed);removed_late=len(removed)-removed_pass
    bc,ac=active['counts'],current['counts']
    bridge={'before':{'total':bc['total'],'pass':bc['pass'],'late':bc['late']},
            'after':{'total':ac['total'],'pass':ac['pass'],'late':ac['late']},
            'added':{'total':len(added),'pass':added_pass,'late':added_late,
                     'late_backfill':len(late_added),'overdue_backfill':len(overdue_added)},
            'removed':{'total':len(removed),'pass':removed_pass,'late':removed_late},
            'changed':len(changed),'pass_to_late':pass_to_late,'late_to_pass':late_to_pass}
    bridge['total_balanced']=bc['total']+len(added)-len(removed)==ac['total']
    bridge['pass_balanced']=bc['pass']+added_pass-removed_pass-pass_to_late+late_to_pass==ac['pass']
    bridge['late_balanced']=bc['late']+added_late-removed_late+pass_to_late-late_to_pass==ac['late']

    basis=[]
    for key,label in (('rule_version','规则版本'),('parameters','核算参数'),('references','规则文件摘要'),
                      ('cutoff','统计截止'),('backfill_hours','补录窗口')):
        if active.get(key)!=current.get(key):basis.append({'key':key,'label':label,'before':active.get(key),'after':current.get(key)})
    reasons=[]
    if late_added:reasons.append({'code':'LATE_BACKFILL','message':f'{len(late_added)} 条截止前接收的标本在补录窗口内后到（定版后 {active["backfill_hours"]} 小时内）',
                                  'specimens':late_added})
    if overdue_added:reasons.append({'code':'OVERDUE_BACKFILL','message':f'{len(overdue_added)} 条截止前接收的标本超出补录窗口后到，需人工裁定',
                                     'specimens':overdue_added})
    if recovered:reasons.append({'code':'RECOVERED','message':f'{len(recovered)} 条标本经重新采信回到核算内',
                                 'specimens':recovered})
    if removed:reasons.append({'code':'WITHDRAWN','message':f'{len(removed)} 条正式结论内标本已不在最新核算中',
                               'specimens':[r['specimen'] for r in removed]})
    if changed:reasons.append({'code':'BASIS_CHANGED','message':f'{len(changed)} 条标本的时效或计算依据发生变化',
                               'specimens':[r['specimen'] for r in changed]})
    if basis:reasons.append({'code':'RULE_CHANGED','message':'规则、参数或统计口径与定版时不同','specimens':[]})

    timeout_before=set(active.get('timeouts') or []);timeout_after=set(current.get('timeouts') or [])
    return {'added':added,'removed':removed,'changed':changed,'late_added':late_added,'overdue_added':overdue_added,
            'recovered':recovered,'states':states,'reasons':reasons,'basis':basis,'bridge':bridge,
            'timeouts':{'before':sorted(timeout_before),'after':sorted(timeout_after),
                        'new':sorted(timeout_after-timeout_before),'cleared':sorted(timeout_before-timeout_after)},
            'window':{'starts':as_text(lock_time),'ends':as_text(deadline),'hours':str(active['backfill_hours'])}}

def state(bundle,active,arrivals=None):
    """Status of the active formal conclusion against the latest calculation."""
    if not active:
        return {'status':'none','label':'未定版','reasons':[],'active':None,'current':None,'diff':None,'states':{}}
    evidence=active['evidence']
    arrivals=dict(arrivals or {})
    for row in bundle['calculate']['rows']:
        arrivals.setdefault(row['specimen'],{'at':bundle['manifest']['created_at'],'seq':0})
    arrivals={specimen:{'at':v['at'],'seq':v['seq']} if isinstance(v,dict) else {'at':v,'seq':0}
              for specimen,v in arrivals.items()}
    # A persisted calculation can legitimately fall entirely outside the closed
    # period; that is a pending-difference state, not an error.
    current=build(bundle,evidence['cutoff'],evidence['backfill_hours'],arrivals,allow_empty=True)
    diff=compare(evidence,current,active['created_at'])
    codes={r['code'] for r in diff['reasons']}
    if 'OVERDUE_BACKFILL' in codes:status,label=STATUS_LABELS['pending_decision']
    elif codes:status,label=STATUS_LABELS['pending_relock']
    else:status,label=STATUS_LABELS['current']
    scoped={'cutoff':current['cutoff'],'digest':current['digest'],'counts':current['counts'],
            'timeouts':current['timeouts'],'out_of_scope':current['out_of_scope']}
    return {'status':status,'label':label,'reasons':diff['reasons'],'active':active,'current':scoped,
            'diff':diff,'states':diff['states']}

def decorate(calculation,formal):
    states=formal.get('states') or {}
    active=formal.get('active')
    out=dict(calculation)
    out['formal']={'status':formal['status'],'label':formal['label'],
                   'revision':active['revision'] if active else None,
                   'active':active,
                   'cutoff':active['evidence']['cutoff'] if active else None,
                   'digest':active['evidence']['digest'] if active else None,
                   'counts':active['evidence']['counts'] if active else None,
                   'reasons':formal['reasons'],'diff':formal.get('diff'),
                   'current':formal.get('current'),'labels':FORMAL_LABELS}
    out['rows']=[dict(r,formal_state=states.get(r['specimen'],'unlocked'),
                      formal_label=FORMAL_LABELS.get(states.get(r['specimen'],'unlocked'),'未纳入'))
                 for r in calculation['rows']]
    return out
