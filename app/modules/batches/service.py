from app import store
from app.errors import RuleError
from app.modules.batches.review import check
from app.modules.batches import formal

def persist(bundle):return store.save(bundle)

def _latest(rid):
    bundle=store.latest()
    if not bundle or bundle['manifest']['run_id']!=rid:raise RuleError('STALE','该批次已不是最新核算，请先复核最新核算',409)
    return bundle

def approve(rid,version):
    bundle=_latest(rid)
    check(bundle)
    basis={'run_id':rid,'digest':bundle['manifest']['sha256'],
           'counts':{'input':bundle['reconcile']['input'],'total':bundle['calculate']['total'],
                     'late':bundle['calculate']['late']},
           'references':bundle['manifest']['references']}
    # The review and its evidence are written in one transaction.
    return store.review(rid,version,basis)

def status():
    return formal.state(store.latest(),store.active(),store.arrivals())

def trial(bundle):
    return formal.decorate(bundle['calculate'],formal.state(bundle,store.active(),store.arrivals()))

def lock(rid,version,cutoff=None,window=None,confirm_overdue=False):
    bundle=_latest(rid)
    if bundle['version']!=version:raise RuleError('STALE','记录已变更，请刷新后定版',409)
    check(bundle)
    arrivals=store.arrivals()
    previous=store.active()
    # Re-locking a period inherits the locked cutoff and window unless overridden,
    # so a backfill decision only extends the same scope instead of silently
    # shifting the period boundary.
    if previous:
        evidence=previous['evidence']
        cutoff=cutoff if cutoff not in (None,'') else evidence['cutoff']
        window=window if window not in (None,'') else evidence['backfill_hours']
    current=formal.state(bundle,previous,arrivals)
    evidence=formal.build(bundle,cutoff,window,arrivals)
    diff=current.get('diff')
    if diff and diff['overdue_added'] and not confirm_overdue:
        raise RuleError('OVERDUE_BACKFILL',f"{len(diff['overdue_added'])} 条标本超出补录窗口后到，确认纳入后才能定版",409)
    detail={}
    if diff:
        detail={'reasons':diff['reasons'],'bridge':diff['bridge'],'timeouts':diff['timeouts'],
                'late_backfill':diff['late_added'],'overdue_backfill':diff['overdue_added'],
                'confirm_overdue':bool(confirm_overdue)}
    result=store.lock(rid,version,evidence,detail)
    result['formal']=formal.state(store.latest(),store.active(),store.arrivals())
    return result

def restore(revision,expected_active):
    if not isinstance(revision,int) or not isinstance(expected_active,int):
        raise RuleError('VERSION','修订号必须为整数')
    bundle=store.latest()
    result=store.restore(revision,expected_active,{'run_id':bundle['manifest']['run_id'] if bundle else None})
    result['formal']=formal.state(bundle,store.active(),store.arrivals())
    return result
