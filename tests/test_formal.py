from app import store
from app.pipeline import sample_bytes
import pytest

BACKFILL='000099,BIO,门诊,2026-11-02T15:00:00+08:00,2026-11-04T09:00:00+08:00,0\n'

def later_dirty():
    """The same dirty corpus plus one late backfill so isolation counts stay fixed."""
    return (sample_bytes().decode('utf-8-sig')+BACKFILL).encode('utf-8')

def run(client,raw,grace='0'):
    return client.post('/api/runs',json={'csv_text':raw.decode('utf-8'),'grace':grace}).json()

def reviewed(client):
    b=store.latest()
    assert client.post('/api/batches/review',json={'run_id':b['manifest']['run_id'],'version':b['version']}).status_code==200
    return store.latest()

def test_lock_requires_review(client):
    b=store.latest()
    r=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']})
    assert r.status_code==409;assert r.json()['code']=='REVIEW_REQUIRED'

def test_lock_freezes_scope_and_excludes_next_period(client):
    b=reviewed(client)
    r=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version'],'cutoff':'2026-11-03T00:00:00+08:00'})
    assert r.status_code==200, r.text
    body=r.json();assert body['active'] and body['revision']==1
    counts=body['evidence']['counts']
    # 000006 / 000012 / 000018 / 000024 / 000030 / 000036 / 000042 are released on 11-04.
    assert counts['total']==41;assert counts['pass']+counts['late']==counts['total']
    assert counts['input']==counts['total']+counts['isolated']+counts['blank']

def test_same_calculation_retry_does_not_append(client):
    b=reviewed(client)
    first=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']}).json()
    second=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']}).json()
    assert second['idempotent'] and second['revision']==first['revision']
    assert len(store.conclusions())==1

def test_late_backfill_is_explained_against_locked_revision(client):
    b=reviewed(client)
    client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version'],
                                          'cutoff':'2026-11-03T00:00:00+08:00'})
    run(client,later_dirty())
    formal=client.get('/api/calculate').json()['formal']
    assert formal['status']=='pending_relock'
    reasons={r['code']:r for r in formal['reasons']}
    assert '000099' in reasons['LATE_BACKFILL']['specimens']
    bridge=formal['diff']['bridge']
    assert bridge['added']['total']==1
    assert bridge['before']['total']+1==bridge['after']['total']
    assert all(bridge[k] for k in ('total_balanced','pass_balanced','late_balanced'))
    row=next(r for r in client.get('/api/calculate').json()['rows'] if r['specimen']=='000099')
    assert row['formal_state']=='late_backfill';assert row['formal_label']=='补录已纳入'

def test_overdue_backfill_needs_explicit_confirmation(client):
    b=reviewed(client)
    # Zero-hour window: any specimen arriving after the lock is outside it.
    client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version'],'window':'0'})
    run(client,later_dirty())
    b=reviewed(client)
    blocked=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']})
    assert blocked.status_code==409;assert blocked.json()['code']=='OVERDUE_BACKFILL'
    accepted=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version'],'confirm_overdue':True})
    assert accepted.status_code==200
    assert accepted.json()['revision']==2
    assert accepted.json()['evidence']['counts']['total']==42

def test_new_revision_supersedes_but_keeps_evidence(client):
    b=reviewed(client)
    first=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']}).json()
    run(client,later_dirty());b=reviewed(client)
    second=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version'],
                                                 'confirm_overdue':True}).json()
    assert second['revision']==2 and second['replaced']==1
    revisions={c['revision']:c for c in client.get('/api/batches/formal').json()['conclusions']}
    assert revisions[1]['active'] is False and revisions[1]['superseded_by']==2
    assert revisions[2]['active'] is True
    assert revisions[1]['isolated']==revisions[2]['isolated']==9
    actions=[r['action']+'/'+r['outcome'] for r in client.get('/api/batches/formal').json()['reviews']]
    assert 'lock/activated' in actions and 'review/approved' in actions

def test_restore_old_revision_keeps_review_basis(client):
    b=reviewed(client)
    client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']})
    run(client,later_dirty());b=reviewed(client)
    client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version'],'confirm_overdue':True})
    restored=client.post('/api/batches/restore',json={'revision':1,'expected_active':2})
    assert restored.status_code==200
    assert restored.json()['active'] and restored.json()['revision']==1
    listing={c['revision']:c for c in client.get('/api/batches/formal').json()['conclusions']}
    assert listing[1]['active'] is True and listing[1]['superseded_by'] is None
    assert listing[2]['active'] is False
    audits=client.get('/api/batches/formal').json()['reviews']
    assert any(a['action']=='restore' and a['outcome']=='activated' for a in audits)
    # The superseded revision's evidence is still readable and explains its numbers.
    assert listing[2]['total'] is not None and listing[2]['digest']

def test_restore_rejects_stale_active(client):
    b=reviewed(client)
    client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']})
    assert client.post('/api/batches/restore',json={'revision':1,'expected_active':99}).status_code==409

def test_failed_lock_keeps_old_conclusion(client):
    b=reviewed(client)
    first=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']}).json()
    run(client,later_dirty());b=reviewed(client)
    # Wrong version -> stale, nothing changes.
    assert client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':999}).status_code==409
    active=store.active()
    assert active['revision']==first['revision']
    assert len(store.conclusions())==1

def test_page_shows_backfill_difference(client):
    b=reviewed(client)
    client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']})
    run(client,later_dirty())
    html=client.get('/calculate').text
    assert '补录前后差异' in html and '000099' in html
    batches=client.get('/batches').text
    assert '正式结论修订' in batches and '定版裁决' in batches

def test_scope_identity_holds_for_locked_revisions(client):
    b=reviewed(client)
    body=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']}).json()
    counts=body['evidence']['counts']
    assert counts['scope_balanced'] is True
    assert counts['isolated']==b['quarantine']['total']
    assert counts['input']==counts['total']+counts['isolated']+counts['blank']+counts['out_of_scope']

def test_timeout_list_and_counts_agree(client):
    b=reviewed(client)
    body=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']}).json()
    evidence=body['evidence']
    late={r['specimen'] for r in evidence['rows'] if r['state']=='超时'}
    assert set(evidence['timeouts'])==late
    assert len(evidence['timeouts'])==evidence['counts']['late']
    for row in evidence['rows']:
        # Every frozen row carries its own arithmetic, so a name on the timeout
        # list can be re-derived from the stored basis.
        assert row['elapsed_minutes']==str(float(row['elapsed_minutes']))
        assert float(row['overdue_minutes'])==max(0.0,float(row['elapsed_minutes'])-float(row['limit_minutes']))

def test_basis_change_is_reported(client):
    b=reviewed(client)
    client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']})
    run(client,later_dirty(),grace='10')
    formal=client.get('/api/calculate').json()['formal']
    codes={r['code'] for r in formal['reasons']}
    assert 'RULE_CHANGED' in codes or 'BASIS_CHANGED' in codes
    assert any(item['key']=='parameters' for item in formal['diff']['basis'])

def test_calculate_trial_is_decorated_but_not_persisted(client):
    b=reviewed(client)
    client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']})
    before=len(store.history())
    trial=client.post('/api/calculate',json={'csv_text':later_dirty().decode('utf-8')}).json()
    assert trial['formal']['status']=='pending_relock'
    assert len(store.history())==before

def test_review_audit_records_basis(client):
    b=store.latest()
    client.post('/api/batches/review',json={'run_id':b['manifest']['run_id'],'version':b['version']})
    review=next(r for r in store.reviews() if r['action']=='review' and r['outcome']=='approved')
    assert review['detail']['counts']['total']==b['calculate']['total']
    assert set(review['detail']['references'])=={'versions','calendar','pauses'}

def test_relock_after_restore_revives_revision(client):
    b=reviewed(client)
    client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']})
    run(client,later_dirty());b=reviewed(client)
    client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version'],'confirm_overdue':True})
    client.post('/api/batches/restore',json={'revision':1,'expected_active':2})
    revived=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version'],'confirm_overdue':True})
    assert revived.status_code==200
    assert revived.json()['revision']==2 and revived.json()['created'] is False
    assert len(store.conclusions())==2
    assert store.active()['revision']==2

def test_out_of_period_receipt_goes_to_next_period(client):
    b=reviewed(client)
    body=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version'],
                                               'cutoff':'2026-11-02T12:00:00+08:00'}).json()
    evidence=body['evidence']
    assert evidence['counts']['out_of_scope']>0
    assert all(s not in evidence['timeouts'] for s in evidence['out_of_scope'])
    assert evidence['counts']['scope_balanced'] is True

def test_switch_failure_keeps_old_revision_and_audit(client,monkeypatch):
    from app import store as store_module
    b=reviewed(client)
    first=client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version']}).json()
    run(client,later_dirty());b=reviewed(client)
    audits_before=len(store_module.reviews())

    def boom(*args,**kwargs):raise RuntimeError('switch failed')
    original=store_module._audit
    monkeypatch.setattr(store_module,'_audit',boom)
    with pytest.raises(RuntimeError):
        client.post('/api/batches/lock',json={'run_id':b['manifest']['run_id'],'version':b['version'],'confirm_overdue':True})
    store_module._audit=original

    # The old conclusion is still active and the new basis never landed.
    active=store_module.active()
    assert active['revision']==first['revision'] and active['evidence']['counts']['total']==41
    assert len(store_module.conclusions())==1
    # Review evidence written before the failed switch is still readable.
    audits=store_module.reviews()
    assert len(audits)>=audits_before
    assert any(a['action']=='review' and a['outcome']=='approved' for a in audits)
