from decimal import Decimal

def judge(row,grace='0'):
    elapsed=Decimal(row['elapsed_minutes']);limit=Decimal(str(row['sla']))+Decimal(grace)
    return dict(row,limit_minutes=str(limit),overdue_minutes=str(max(Decimal(0),elapsed-limit)),state='超时' if elapsed>limit else '达标',clock='自然分钟' if row['urgent'] else '工作分钟')
