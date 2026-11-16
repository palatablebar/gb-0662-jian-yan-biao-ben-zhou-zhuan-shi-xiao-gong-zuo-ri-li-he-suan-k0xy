from app import store

def test_idempotent_seed(client):
    a=client.post('/api/runs',json={}).json();b=client.post('/api/runs',json={}).json();assert a['manifest']['run_id']==b['manifest']['run_id'];assert len(store.history())==1

def test_grace_changes_manifest(client):
    a=store.latest();b=client.post('/api/runs',json={'grace':'10'}).json();assert a['manifest']['run_id']!=b['manifest']['run_id']

def test_stale_version(client):
    """TRAP-26"""
    b=store.latest();p={'run_id':b['manifest']['run_id'],'version':b['version']};assert client.post('/api/batches/review',json=p).status_code==200;assert client.post('/api/batches/review',json=p).status_code==409

def test_atomic_error(client):
    n=len(store.history());assert client.post('/api/runs',json={'csv_text':'bad'}).status_code==422;assert len(store.history())==n

def test_reopen_persistent(client):
    rid=store.latest()['manifest']['run_id'];store.connect().close();assert store.latest()['manifest']['run_id']==rid

def test_all_reference_digests(dirty):
    assert set(dirty['manifest']['references'])=={'versions','calendar','pauses'};assert all(len(s)==64 for s in dirty['manifest']['references'].values())

def test_unknown_sample(client):
    assert client.post('/api/runs',json={'sample':'missing'}).status_code==404
