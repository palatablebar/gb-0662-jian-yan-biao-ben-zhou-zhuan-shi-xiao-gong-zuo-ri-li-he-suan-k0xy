def test_pages(client):
    for key in ['intake','contract','model','calculate','quarantine','reconcile','batches']:
        r=client.get('/'+key);assert r.status_code==200;assert 'stage-track' in r.text

def test_module_trials(client):
    for key in ['intake','contract','model','calculate','quarantine','reconcile']:
        assert client.post('/api/'+key,json={'sample':'dirty'}).status_code==200

def test_export(client):
    r=client.get('/api/quarantine/export');assert r.status_code==200;assert r.text.count('\n')==10

def test_fail_recover(client):
    assert client.post('/api/runs',json={'grace':'bad'}).status_code==422;assert client.post('/api/runs',json={'sample':'clean'}).json()['reconcile']['balanced']
