from app.modules.calculate.service import calculate
from app.modules.calculate.sla import judge
from copy import deepcopy
import pytest
from app.errors import RuleError

def test_boundary_pass():
    assert judge({'elapsed_minutes':'180','sla':'180','urgent':False})['state']=='达标'

def test_one_second_late():
    r=judge({'elapsed_minutes':'180.01','sla':'180','urgent':False});assert r['state']=='超时';assert r['overdue_minutes']=='0.01'

def test_grace(dirty):
    r=calculate(dirty['model']['rows'],'60');assert r['pass']>=dirty['calculate']['pass'];assert r['late']<=dirty['calculate']['late']

def test_sample_conservation(clean):
    assert clean['calculate']['total']==42;assert clean['calculate']['pass']+clean['calculate']['late']==42

def test_regular_clock(clean):
    row=next(r for r in clean['calculate']['rows'] if r['specimen']=='000006');assert row['state']=='达标';assert row['clock']=='工作分钟'

def test_urgent_overdue(clean):
    row=next(r for r in clean['calculate']['rows'] if r['specimen']=='000030');assert row['state']=='超时';assert row['overdue_minutes']=='2430.0'

def test_invalid_grace():
    with pytest.raises(RuleError):calculate([],'NaN')
