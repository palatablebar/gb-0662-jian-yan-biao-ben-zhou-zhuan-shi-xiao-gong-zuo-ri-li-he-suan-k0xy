from fastapi import APIRouter,Request,Body
from app.web import page
from app import store
from app.pipeline import execute,sample_bytes
from app.modules.batches import service as batches
router=APIRouter()
@router.get('/calculate')
def view(request:Request):return page(request,'calculate')
@router.get('/api/calculate')
def result():return batches.trial(store.latest())
@router.post('/api/calculate')
def trial(payload:dict=Body(default={})):
    raw=payload.get('csv_text');data=execute(raw.encode() if isinstance(raw,str) else sample_bytes(payload.get('sample','dirty')),payload.get('grace','0'))
    return batches.trial(data)
