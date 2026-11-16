import json,hashlib,time
from app.config import SAMPLES
from app.errors import RuleError
from app.manifest import make_manifest
from app.modules.intake.service import ingest
from app.modules.contract.service import normalize
from app.modules.model.service import build
from app.modules.calculate.service import calculate
from app.modules.quarantine.service import quarantine
from app.modules.reconcile.service import reconcile

def execute(raw,grace='0'):
    start=time.perf_counter();refs={};objects={}
    for name in ('versions','calendar','pauses'):
        data=(SAMPLES/(name+'.json')).read_bytes();refs[name]=hashlib.sha256(data).hexdigest();objects[name]=json.loads(data)
    intake=ingest(raw);contract=normalize(intake['rows'],objects['versions']);model=build(contract['rows'],objects['calendar'],objects['pauses']);calc=calculate(model['rows'],grace)
    isolated=quarantine(intake['issues'],contract['issues'],model['issues']);checked=reconcile(intake,calc,isolated)
    manifest=make_manifest(raw,{'grace':str(grace)},refs);manifest['elapsed_ms']=round((time.perf_counter()-start)*1000,3)
    return {'manifest':manifest,'intake':intake,'contract':contract,'model':model,'calculate':calc,'quarantine':isolated,'reconcile':checked}

def sample_bytes(name='dirty'):
    if name not in ('dirty','clean','gb18030'):raise RuleError('SAMPLE','标本样例不存在',404)
    return (SAMPLES/(name+'.csv')).read_bytes()
