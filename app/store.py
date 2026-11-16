import os,sqlite3,json,time
from pathlib import Path
from app.errors import RuleError

SCHEMA='''
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, payload TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, reviewed INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS specimens(specimen TEXT PRIMARY KEY, first_seen TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conclusions(
    revision INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    run_version INTEGER NOT NULL,
    cutoff TEXT NOT NULL,
    created_at TEXT NOT NULL,
    digest TEXT NOT NULL,
    arrival_floor INTEGER NOT NULL DEFAULT 0,
    evidence TEXT NOT NULL,
    superseded_by INTEGER,
    active INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS conclusions_one_active ON conclusions(active) WHERE active=1;
CREATE TABLE IF NOT EXISTS reviews(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    version INTEGER,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);
'''

def connect():
    path=os.environ.get('DB_PATH','/tmp/labclock.sqlite3')
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(path,timeout=15);con.row_factory=sqlite3.Row
    con.executescript(SCHEMA)
    return con

def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())

def _run(row):
    out=json.loads(row['payload']);out['version']=row['version'];out['reviewed']=bool(row['reviewed']);return out

def save(bundle):
    rid=bundle['manifest']['run_id']
    con=connect()
    try:
        con.execute('INSERT OR IGNORE INTO runs(id,payload,created) VALUES(?,?,?)',(rid,json.dumps(bundle,ensure_ascii=False),bundle['manifest']['created_at']))
        for row in bundle['calculate']['rows']:
            con.execute('INSERT OR IGNORE INTO specimens(specimen,first_seen) VALUES(?,?)',(row['specimen'],bundle['manifest']['created_at']))
        con.commit()
        row=con.execute('SELECT * FROM runs WHERE id=?',(rid,)).fetchone()
    finally:con.close()
    return _run(row)

def get(rid):
    con=connect()
    try:row=con.execute('SELECT * FROM runs WHERE id=?',(rid,)).fetchone()
    finally:con.close()
    return _run(row) if row else None

def latest():
    con=connect()
    try:row=con.execute('SELECT * FROM runs ORDER BY rowid DESC LIMIT 1').fetchone()
    finally:con.close()
    return _run(row) if row else None

def history():
    con=connect()
    try:rows=con.execute('SELECT id,version,reviewed,created FROM runs ORDER BY rowid DESC').fetchall()
    finally:con.close()
    return [dict(r) for r in rows]

def arrivals():
    """Provenance of every specimen ever accepted: when it first arrived and its order."""
    con=connect()
    try:rows=con.execute('SELECT specimen,first_seen,rowid AS seq FROM specimens').fetchall()
    finally:con.close()
    return {r['specimen']:{'at':r['first_seen'],'seq':r['seq']} for r in rows}

def floor():
    con=connect()
    try:row=con.execute('SELECT COALESCE(MAX(rowid),0) AS seq FROM specimens').fetchone()
    finally:con.close()
    return row['seq']

def _audit(con,rid,version,action,outcome,detail):
    con.execute('INSERT INTO reviews(run_id,version,action,outcome,detail,created_at) VALUES(?,?,?,?,?,?)',
                (rid,version,action,outcome,json.dumps(detail,ensure_ascii=False) if detail is not None else None,now()))

def audit(rid,version,action,outcome,detail=None):
    con=connect()
    try:
        _audit(con,rid,version,action,outcome,detail);con.commit()
    finally:con.close()

def review(rid,version,detail=None):
    con=connect()
    try:
        con.execute('BEGIN IMMEDIATE')
        cur=con.execute('UPDATE runs SET version=version+1,reviewed=1 WHERE id=? AND version=?',(rid,version))
        if cur.rowcount!=1:
            _audit(con,rid,version,'review','stale',detail)
            con.commit()
            raise RuleError('STALE','记录已变更，请刷新后复核',409)
        _audit(con,rid,version+1,'review','approved',detail)
        con.commit()
    except Exception:
        if con.in_transaction:con.rollback()
        raise
    finally:con.close()
    return {'run_id':rid,'version':version+1,'reviewed':True}

def _evidence_row(row):
    return {'revision':row['revision'],'run_id':row['run_id'],'run_version':row['run_version'],
            'cutoff':row['cutoff'],'created_at':row['created_at'],'digest':row['digest'],
            'arrival_floor':row['arrival_floor'],'superseded_by':row['superseded_by'],
            'active':bool(row['active']),'evidence':json.loads(row['evidence'])}

def active():
    con=connect()
    try:row=con.execute('SELECT * FROM conclusions WHERE active=1').fetchone()
    finally:con.close()
    return _evidence_row(row) if row else None

def conclusion(revision):
    con=connect()
    try:row=con.execute('SELECT * FROM conclusions WHERE revision=?',(revision,)).fetchone()
    finally:con.close()
    return _evidence_row(row) if row else None

def conclusions():
    con=connect()
    try:rows=con.execute('SELECT * FROM conclusions ORDER BY revision DESC').fetchall()
    finally:con.close()
    out=[]
    for row in rows:
        evidence=json.loads(row['evidence']);counts=evidence.get('counts',{})
        out.append({'revision':row['revision'],'run_id':row['run_id'],'run_version':row['run_version'],
                    'cutoff':row['cutoff'],'created_at':row['created_at'],'digest':row['digest'],
                    'superseded_by':row['superseded_by'],'active':bool(row['active']),
                    'input':counts.get('input'),'total':counts.get('total'),'pass':counts.get('pass'),
                    'late':counts.get('late'),'isolated':counts.get('isolated'),'blank':counts.get('blank'),
                    'out_of_scope':counts.get('out_of_scope'),'backfill_hours':evidence.get('backfill_hours')})
    return out

def reviews(rid=None):
    con=connect()
    try:
        if rid is None:rows=con.execute('SELECT * FROM reviews ORDER BY id').fetchall()
        else:rows=con.execute('SELECT * FROM reviews WHERE run_id=? ORDER BY id',(rid,)).fetchall()
    finally:con.close()
    out=[]
    for row in rows:
        item=dict(row)
        item['detail']=json.loads(item['detail']) if item['detail'] else None
        out.append(item)
    return out

def lock(rid,expected_version,evidence,detail=None):
    """Atomically make ``evidence`` the active formal conclusion.

    The previous active revision is superseded inside the same transaction. Any
    failure rolls back, so the old conclusion stays in force; review audit rows
    committed earlier are untouched and remain the review evidence.
    """
    created_at=now()
    con=connect()
    try:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM runs WHERE id=?',(rid,)).fetchone()
        if not row:raise RuleError('NOT_FOUND','当前批次不存在',404)
        if not row['reviewed']:raise RuleError('REVIEW_REQUIRED','批次尚未复核，不能形成正式结论',409)
        if row['version']!=expected_version:raise RuleError('STALE','记录已变更，请刷新后定版',409)

        existing=con.execute('SELECT * FROM conclusions WHERE run_id=? AND digest=? ORDER BY revision DESC LIMIT 1',(rid,evidence['digest'])).fetchone()
        if existing and existing['active']:
            # Retrying the same calculation reuses the revision instead of appending a batch.
            _audit(con,rid,expected_version,'lock','idempotent',
                   dict(detail or {},revision=existing['revision'],digest=evidence['digest']))
            con.commit()
            con.close();con=None
            out=_evidence_row(existing);out.update({'created':False,'idempotent':True,'replaced':None})
            return out
        if existing:
            # The same frozen basis was locked before and then superseded or rolled
            # back: revive that revision rather than appending a duplicate batch.
            current=con.execute('SELECT * FROM conclusions WHERE active=1').fetchone()
            if current:
                con.execute('UPDATE conclusions SET active=0,superseded_by=? WHERE revision=?',(existing['revision'],current['revision']))
            con.execute('UPDATE conclusions SET active=1,superseded_by=NULL WHERE revision=?',(existing['revision'],))
            _audit(con,rid,expected_version,'lock','reactivated',
                   dict(detail or {},revision=existing['revision'],digest=evidence['digest'],
                        replaced=current['revision'] if current else None))
            con.commit()
            con.close();con=None
            out=_evidence_row(existing);out.update({'created':False,'idempotent':True,
                                                   'replaced':current['revision'] if current else None})
            return out

        previous=con.execute('SELECT * FROM conclusions WHERE active=1').fetchone()
        arrival_floor=con.execute('SELECT COALESCE(MAX(rowid),0) AS seq FROM specimens').fetchone()['seq']
        cur=con.execute('INSERT INTO conclusions(run_id,run_version,cutoff,created_at,digest,arrival_floor,evidence) VALUES(?,?,?,?,?,?,?)',
                        (rid,expected_version,evidence['cutoff'],created_at,evidence['digest'],arrival_floor,
                         json.dumps(evidence,ensure_ascii=False)))
        revision=cur.lastrowid
        if previous:con.execute('UPDATE conclusions SET active=0,superseded_by=? WHERE revision=?',(revision,previous['revision']))
        con.execute('UPDATE conclusions SET active=1 WHERE revision=?',(revision,))
        _audit(con,rid,expected_version,'lock','activated',
               dict(detail or {},revision=revision,digest=evidence['digest'],cutoff=evidence['cutoff'],
                    replaced=previous['revision'] if previous else None,counts=evidence.get('counts')))
        con.commit()
    except Exception:
        if con.in_transaction:con.rollback()
        raise
    finally:
        if con is not None:con.close()
    out=conclusion(revision)
    out.update({'created':True,'idempotent':False,'replaced':previous['revision'] if previous else None})
    return out

def restore(revision,expected_active,detail=None):
    """Restore a superseded revision as active, keeping both audit trails."""
    con=connect()
    try:
        con.execute('BEGIN IMMEDIATE')
        current=con.execute('SELECT * FROM conclusions WHERE active=1').fetchone()
        if not current or current['revision']!=expected_active:
            raise RuleError('STALE','正式结论已变更，请刷新后重试',409)
        target=con.execute('SELECT * FROM conclusions WHERE revision=?',(revision,)).fetchone()
        if not target:raise RuleError('NOT_FOUND','目标修订不存在',404)
        if target['revision']==current['revision']:raise RuleError('SAME','目标修订已是当前正式结论',409)
        con.execute('UPDATE conclusions SET active=0,superseded_by=? WHERE revision=?',(revision,current['revision']))
        con.execute('UPDATE conclusions SET active=1,superseded_by=NULL WHERE revision=?',(revision,))
        _audit(con,target['run_id'],target['run_version'],'restore','activated',
               dict(detail or {},restored=revision,replaced=current['revision']))
        con.commit()
    except Exception:
        if con.in_transaction:con.rollback()
        raise
    finally:con.close()
    return conclusion(revision)
