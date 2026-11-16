from app.modules.quarantine.service import evidence_csv
from app.modules.quarantine.diagnose import classify

def test_reason_count(dirty):
    assert dirty['quarantine']['total']==9;assert dirty['quarantine']['counts']['CONFLICT']==2

def test_reason_text(dirty):
    assert any(r['reason']=='签发早于接收' for r in dirty['quarantine']['rows'])

def test_filtered(dirty):
    r=classify(dirty['quarantine']['rows'],'CONFLICT');assert len(r['rows'])==2

def test_csv_evidence(dirty):
    s=evidence_csv(dirty['quarantine']['rows']);assert s.startswith('\ufeffline,code,reason,raw');assert s.count('\n')==10

def test_clean_no_reject(clean):
    assert clean['quarantine']['total']==0;assert clean['quarantine']['rows']==[]

def test_counts_equal(dirty):
    assert sum(dirty['quarantine']['counts'].values())==len(dirty['quarantine']['rows'])

def test_raw_retained(dirty):
    r=next(i for i in dirty['quarantine']['rows'] if i['code']=='MISSING');assert r['raw']['received']=='N/A'
