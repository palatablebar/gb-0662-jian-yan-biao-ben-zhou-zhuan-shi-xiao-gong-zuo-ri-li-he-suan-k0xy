import pytest
from copy import deepcopy
from app.modules.contract.versions import instant,select
from app.modules.contract.service import normalize
from app.errors import RuleError

def test_leading_zero(clean):
    """TRAP-08"""
    assert clean['contract']['rows'][0]['specimen']=='000001'

def test_missing_isolated(dirty):
    """TRAP-07"""
    assert sum(i['code']=='MISSING' for i in dirty['contract']['issues'])==1

def test_timezone():
    """TRAP-11"""
    assert instant('2026-11-02T09:00:00+08:00')==instant('2026-11-02T01:00:00Z')

def test_conflict(dirty):
    """TRAP-14"""
    assert sum(i['code']=='CONFLICT' for i in dirty['contract']['issues'])==2

def test_version_overlap(clean):
    """TRAP-25"""
    versions=deepcopy(clean['contract']['versions']);versions.append(versions[0].copy())
    with pytest.raises(RuleError) as e:select('BIO',instant('2026-11-02T09:00:00+08:00'),versions)
    assert e.value.code=='VERSION'

def test_sample_urgent_rule(clean):
    row=next(r for r in clean['contract']['rows'] if r['specimen']=='000005');assert row['urgent'];assert row['sla']=='60'

def test_reversed_evidence(dirty):
    assert any(i['code']=='REVERSED' for i in dirty['contract']['issues'])
