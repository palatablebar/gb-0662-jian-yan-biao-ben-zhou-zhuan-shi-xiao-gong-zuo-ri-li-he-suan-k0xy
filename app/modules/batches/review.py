from app.errors import RuleError

def check(bundle):
    if not bundle['reconcile']['balanced']:raise RuleError('UNBALANCED','行数不平，请重新采信',409)
    return True
