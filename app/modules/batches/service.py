from app import store
from app.errors import RuleError
from app.modules.batches.review import check

def persist(bundle):return store.save(bundle)
def approve(rid,version):
    bundle=store.latest()
    if not bundle or bundle['manifest']['run_id']!=rid:raise RuleError('NOT_FOUND','当前批次不存在',404)
    check(bundle);return store.review(rid,version)
