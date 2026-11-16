from fastapi import APIRouter,Request,Body
from app.web import page
from app import store
from app.errors import RuleError
from app.modules.batches import service
router=APIRouter()

def _int(payload,key,label):
    value=payload.get(key)
    if not isinstance(value,int) or isinstance(value,bool):raise RuleError('VERSION',f'{label}必须为整数')
    return value

@router.get('/batches')
def view(request:Request):return page(request,'batches')

@router.get('/api/batches')
def result():return store.history()

@router.get('/api/batches/formal')
def formal_view():return {'status':service.status(),'conclusions':store.conclusions(),'reviews':store.reviews()}

@router.post('/api/batches/review')
def review(payload:dict=Body(...)):return service.approve(payload.get('run_id',''),_int(payload,'version','版本'))

@router.post('/api/batches/lock')
def lock(payload:dict=Body(default={})):
    return service.lock(payload.get('run_id',''),_int(payload,'version','版本'),
                        payload.get('cutoff'),payload.get('window'),bool(payload.get('confirm_overdue')))

@router.post('/api/batches/restore')
def restore(payload:dict=Body(...)):
    return service.restore(_int(payload,'revision','修订号'),_int(payload,'expected_active','当前修订号'))
