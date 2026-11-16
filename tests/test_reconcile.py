from decimal import Decimal
from copy import deepcopy
from app.modules.reconcile.metrics import percentile,compare

def test_row_balance(dirty):
    r=dirty['reconcile'];assert r['input']==r['output']+r['isolated']+r['blank'];assert r['balanced']

def test_department_total(clean):
    assert sum(d['total'] for d in clean['reconcile']['departments'])==42

def test_department_late(clean):
    assert sum(d['late'] for d in clean['reconcile']['departments'])==clean['calculate']['late']

def test_p95_nearest_rank():
    assert percentile(['1','2','3','4'],'.95')=='4';assert percentile([],'.95') is None

def test_median_rank():
    assert percentile(['2','1','4','3'],'.5')=='2'

def test_inconsistent_input(dirty):
    x=deepcopy(dirty['intake']);x['input']+=1;r=compare(x,dirty['calculate'],dirty['quarantine']);assert not r['balanced'];assert r['row_delta']==1

def test_sample_department_identity(clean):
    assert {d['department'] for d in clean['reconcile']['departments']}=={'门诊','住院'}
