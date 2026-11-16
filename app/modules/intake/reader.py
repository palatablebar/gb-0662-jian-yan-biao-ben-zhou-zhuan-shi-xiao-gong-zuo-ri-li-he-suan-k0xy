import csv,io
from app.config import MAX_BYTES,MAX_ROWS
from app.errors import RuleError
COLUMNS=['specimen','project','department','received','released','urgent']
def read(raw):
    if len(raw)>MAX_BYTES:raise RuleError('LIMIT','文件超过2MB')
    for encoding in ('utf-8-sig','gb18030'):
        try:text=raw.decode(encoding);break
        except UnicodeDecodeError:continue
    else:raise RuleError('ENCODING','文件编码无法识别')
    if not text:return {'rows':[],'issues':[],'blank':0,'input':0,'state':'EMPTY_FILE','encoding':encoding,'headers':0}
    reader=csv.reader(io.StringIO(text,newline=''),strict=True)
    try:header=next(reader)
    except (csv.Error,StopIteration):raise RuleError('HEADER','表头缺失')
    if header!=COLUMNS:raise RuleError('HEADER','标本表头不匹配')
    rows=[];issues=[];blank=0;total=0;headers=0
    try:
        for fields in reader:
            total+=1
            if total>MAX_ROWS:raise RuleError('LIMIT','最多接收10000条记录')
            if not fields or all(not x.strip() for x in fields):blank+=1;continue
            if fields==header:headers+=1;total-=1;continue
            if len(fields)!=6:issues.append({'line':reader.line_num,'code':'COLUMN_COUNT','raw':fields});continue
            rows.append(dict(zip(COLUMNS,fields),line=reader.line_num))
    except csv.Error:raise RuleError('TRUNCATED','引号未闭合，请重新导出')
    return {'rows':rows,'issues':issues,'blank':blank,'input':total,'state':'READY' if rows or issues else ('BLANK_ROWS' if blank else 'HEADER_ONLY'),'encoding':encoding,'headers':headers}
