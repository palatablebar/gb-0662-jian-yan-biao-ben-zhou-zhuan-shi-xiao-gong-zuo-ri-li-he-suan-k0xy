from datetime import datetime
from decimal import Decimal
from copy import deepcopy
from app.modules.model.calendar import merge,windows,minutes
from app.modules.model.service import build

def test_holiday_sample(clean):
    row=next(r for r in clean['model']['rows'] if r['specimen']=='000006');assert row['working_minutes']=='120.0';assert row['elapsed_minutes']=='90.0'

def test_pause_union_counterexample(clean):
    row=next(r for r in clean['model']['rows'] if r['specimen']=='000006');assert row['pause_count']==1;assert row['pause_minutes']=='30.0'

def test_urgent_natural(clean):
    row=next(r for r in clean['model']['rows'] if r['specimen']=='000030');assert row['natural_minutes']=='2520.0';assert row['elapsed_minutes']=='2490.0'

def test_half_open_intersection():
    """TRAP-23"""
    from app.modules.model.calendar import intersection
    a=datetime.fromisoformat('2026-01-01T09:00:00+08:00');b=datetime.fromisoformat('2026-01-01T10:00:00+08:00');c=datetime.fromisoformat('2026-01-01T11:00:00+08:00')
    assert intersection((a,b),(b,c)) is None

def test_lunch_deducted(clean):
    row=next(r for r in clean['model']['rows'] if r['specimen']=='000004');assert row['natural_minutes']=='300.0';assert row['working_minutes']=='240.0'

def test_unapproved_ignored(clean):
    rows=[next(r for r in clean['contract']['rows'] if r['specimen']=='000006')]
    pauses={'000006':[{'start':'2026-11-02T16:00:00+08:00','end':'2026-11-02T17:00:00+08:00','approved':False}]}
    r=build(rows,clean['model']['calendar'],pauses);assert r['rows'][0]['pause_minutes']=='0'

def test_invalid_pause_isolated(clean):
    row=clean['contract']['rows'][0];p={row['specimen']:[{'start':'2026-11-02T11:00:00+08:00','end':'2026-11-02T10:00:00+08:00','approved':True}]}
    r=build([row],clean['model']['calendar'],p);assert r['issues'][0]['code']=='PAUSE';assert r['rows']==[]
