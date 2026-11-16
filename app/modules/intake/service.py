from app.modules.intake.reader import read
def ingest(raw):
    result=read(raw);result['accepted']=len(result['rows']);return result
