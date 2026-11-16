import pytest
from app.pipeline import sample_bytes
from app.modules.intake.reader import read
from app.errors import RuleError

def test_bom_header():
    """TRAP-02"""
    r=read(sample_bytes());assert r['rows'][0]['specimen']=='000001';assert r['input']==51

def test_gb18030():
    """TRAP-01"""
    r=read(sample_bytes('gb18030'));assert r['encoding']=='gb18030';assert r['rows'][0]['department']=='门诊'

def test_column_evidence(dirty):
    assert dirty['intake']['issues'][0]['code']=='COLUMN_COUNT';assert dirty['intake']['issues'][0]['line']==51

def test_blank_counts(dirty):
    assert dirty['intake']['blank']==1;assert dirty['intake']['state']=='READY'

def test_empty_tristate():
    """TRAP-18"""
    header=b'specimen,project,department,received,released,urgent\n'
    assert read(b'')['state']=='EMPTY_FILE';assert read(header)['state']=='HEADER_ONLY';assert read(header+b'\n')['state']=='BLANK_ROWS'

def test_truncated():
    with pytest.raises(RuleError):read(b'specimen,project,department,received,released,urgent\n"unfinished')

def test_source_lines(dirty):
    assert dirty['intake']['rows'][0]['line']==2;assert dirty['intake']['rows'][4]['line']==6
