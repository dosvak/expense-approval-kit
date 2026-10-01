#!/usr/bin/env python3
"""pc_expkit_test.py - end-to-end test of the Expense Approval Kit (EXPKIT) sample: the process built with twxkit's bpd() and the task
human services built with cshs(inputs=, outputs=, exits=).

    python3 tools/pc_expkit_test.py <ids.json> [--no-ui]        (host / user / password from BAW_HOST / BAW_USER / BAW_PASSWORD)

1. REST drive: start an instance with the `request` payload, reject in Review (-> Revise task for All Users), resubmit with a changed
   amount (-> Review again), approve (-> Confirm payment for Expense Finance), record the payment -> instance Completed, variables checked.
2. Coach drive (Playwright): start a second instance, open the Review task coach in Process Portal (launchTaskCompletion), check that the
   request fields and the policy note are shown, click Approve (boundary event -> End), open Confirm payment, fill the reference and click
   Payment done -> instance Completed.
Prints PASS / FAIL lines; exit code 1 when a check failed."""
import json, os, re, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import bawenv
import requests, urllib3; urllib3.disable_warnings()
ids = json.load(open(sys.argv[1])); NO_UI = '--no-ui' in sys.argv
H = bawenv.HOST; V1 = H + '/rest/bpm/wle/v1'; results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  <- ' + str(detail)[:400]), flush=True)
def rest(m, path, **kw):
    r = requests.request(m, V1 + path, headers=bawenv.HEADERS, verify=False, **kw)
    try: return r.status_code, r.json()
    except Exception: return r.status_code, r.text
def start(req):
    url = ids['start_urls']['Expense Approval'].replace('/rest/bpm/wle/v1', '')
    if os.environ.get('BAW_SNAPSHOT'): url = re.sub(r'branchId=[^&]*', 'snapshotId=' + os.environ['BAW_SNAPSHOT'], url)   # Process Server: installed snapshot
    st, j = rest('POST', url + '&params=' + urllib.parse.quote(json.dumps({'request': req})))
    check('process start over REST (' + req['requestId'] + ')', st == 200, (st, str(j)[:300]))
    return j['data']['piid'] if st == 200 else None
def instance(pid): return rest('GET', f'/process/{pid}?parts=all')[1]['data']
def open_tasks(pid): return [(t['tkiid'], t['name'], t['assignedToDisplayName']) for t in (instance(pid).get('tasks') or []) if t['status'] in ('Received', 'New')]
def complete(tk, params):
    st, j = rest('PUT', f'/task/{tk}?action=complete&params=' + urllib.parse.quote(json.dumps(params))); return st, j
def wait_open(pid, name, tries=20):
    for _ in range(tries):
        t = [x for x in open_tasks(pid) if x[1] == name]
        if t: return t[0]
        time.sleep(1.5)
    return None
REQ = {'requestId': 'EXP-K1', 'employee': 'Sam Lee', 'amount': 1250.5, 'category': 'Travel', 'purpose': 'Customer visit'}
# ---------------------------------------------------------------------------------------------------------------- 1. REST drive
pid = start(REQ)
if pid:
    t = wait_open(pid, 'Review expense'); check('Review task created for Expense Managers', t and t[2] == 'Expense Managers', open_tasks(pid))
    st, j = rest('GET', f'/task/{t[0]}?parts=data') if t else (0, {})
    data = (j.get('data') or {}).get('data', {}).get('variables', {}) if st == 200 else {}
    check('task data carries the request and the policy note from the system task', data.get('request', {}).get('employee') == 'Sam Lee' and 'director' in str(data.get('note')), data)
    if t: st, j = complete(t[0], {'decision': 'reject', 'comment': 'Please split the hotel nights'}); check('complete Review (reject)', st == 200, (st, str(j)[:200]))
    t = wait_open(pid, 'Revise expense'); check('Revise task created for All Users after the rejection', t and t[2] == 'All Users', open_tasks(pid))
    if t:
        st, j = rest('GET', f'/task/{t[0]}?parts=data'); v = j['data']['data']['variables'] if st == 200 else {}
        check('Revise task shows the manager comment', v.get('managerComment') == 'Please split the hotel nights', v)
        st, j = complete(t[0], {'request': dict(REQ, amount=980)}); check('complete Revise (resubmit with amount 980)', st == 200, (st, str(j)[:200]))
    t = wait_open(pid, 'Review expense'); check('Review task created again after the resubmission', bool(t), open_tasks(pid))
    if t:
        st, j = rest('GET', f'/task/{t[0]}?parts=data'); v = j['data']['data']['variables'] if st == 200 else {}
        check('second review sees the revised amount and note', str(v.get('request', {}).get('amount')) in ('980', '980.0') and v.get('note') == 'Within policy', v)
        st, j = complete(t[0], {'decision': 'approve', 'comment': 'ok'}); check('complete Review (approve)', st == 200, (st, str(j)[:200]))
    t = wait_open(pid, 'Confirm payment'); check('Confirm payment task created for Expense Finance', t and t[2] == 'Expense Finance', open_tasks(pid))
    if t: st, j = complete(t[0], {'paymentReference': 'PAY-K1'}); check('complete Confirm payment', st == 200, (st, str(j)[:200]))
    d = None
    for _ in range(20):
        d = instance(pid)
        if d.get('executionState') != 'Active': break
        time.sleep(1.5)
    check('instance completed', d and d.get('executionState') == 'Completed', d and d.get('executionState'))
    v = d.get('variables') or {}
    check('final variables: decision approve, payment reference, revised amount', v.get('decision') == 'approve' and v.get('paymentReference') == 'PAY-K1' and str((v.get('request') or {}).get('amount')) in ('980', '980.0'), v)
    check('instance name from the instance name expression', d.get('name', '').startswith('Expense EXP-K1'), d.get('name'))
    st, j = rest('PUT', '/search/query?organization=byInstance', json={'organization': 'byInstance', 'condition': [{'field': 'taskCompanyName', 'operator': 'Equals', 'value': ''}]})
    st, j = rest('GET', f'/process/{pid}?parts=data'); check('searchable business data Employee visible on the instance', 'Sam Lee' in json.dumps(j.get('data', {}).get('businessData', j.get('data', {}).get('variables'))), str(j)[:200])
# ---------------------------------------------------------------------------------------------------------------- 2. coach drive
if not NO_UI:
    from playwright.sync_api import sync_playwright
    pid2 = start(dict(REQ, requestId='EXP-K2', amount=300)); shots = os.environ.get('EXPKIT_SHOTS', '.')
    t = wait_open(pid2, 'Review expense'); errs = []; bad = []
    with sync_playwright() as p:
        b = p.chromium.launch(); c = b.new_context(ignore_https_errors=True, viewport={'width': 1400, 'height': 1000}, **({'storage_state': bawenv.STATE} if bawenv.STATE else {})); pg = c.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('response', lambda r: bad.append((r.status, r.url[:120])) if r.status >= 500 else None)
        if not bawenv.STATE:
            pg.goto(H + os.environ.get('BAW_LOGIN', '/ProcessCenter/login.jsp'), wait_until='load', timeout=90000)
            pg.fill('input[name="j_username"], #username', bawenv.USER); pg.fill('input[name="j_password"], #password', bawenv.PASSWORD)
            if pg.locator('#log_in').count(): pg.click('#log_in')      # BAW 24+ Workflow Center login form
            else: pg.keyboard.press('Enter')
            try: pg.wait_for_load_state('networkidle', timeout=60000)
            except Exception: pass
        def open_task(tkiid, text):
            rest('PUT', f'/task/{tkiid}?action=assign&toMe=true')   # claim first: Process Portal on BAW 24+ shows a "Claim Task" dialog for an unclaimed team task
            # Process Portal first; the classic task URL (the one Workplace opens) when the Portal shell stays empty (CP4BA 24 Studio)
            for url in ('/ProcessPortal/launchTaskCompletion?taskId=' + tkiid, '/teamworks/process.lsw?zWorkflowState=1&zResetContext=true&zTaskId=' + tkiid):
                pg.goto(H + url, wait_until='load', timeout=120000)
                if pg.locator('button:has-text("Claim Task")').count(): pg.click('button:has-text("Claim Task")'); pg.wait_for_timeout(3000)
                f = coach_frame(text)
                if f: print('   task coach opened through', url.split('?')[0]); return f
            return None
        def coach_frame(text):
            for _ in range(30):
                for f in pg.frames:
                    try:
                        if f.locator(f'button:has-text("{text}")').count(): return f
                    except Exception: pass
                pg.wait_for_timeout(1000)
            return None
        coach = open_task(t[0], 'Approve'); check('Review task coach opens in Process Portal', coach is not None, pg.url[:150]); pg.screenshot(path=f'{shots}/expkit_review.png', full_page=True)
        if coach:
            body = coach.locator('body').inner_text()
            check('coach shows the request (employee, purpose) and the policy note', 'Sam Lee' in body and 'Customer visit' in body and 'Within policy' in body, body[:300].replace('\n', ' | '))
            check('coach buttons Approve / Reject present', coach.locator('button:has-text("Reject")').count() == 1, coach.locator('button').all_inner_texts())
            coach.locator('textarea').first.fill('approved in the portal'); coach.locator('button:has-text("Approve")').first.click(); pg.wait_for_timeout(6000)
        t2 = wait_open(pid2, 'Confirm payment'); check('Approve button completed the task (Confirm payment created)', bool(t2), open_tasks(pid2))
        if t2:
            coach = open_task(t2[0], 'Payment done'); check('Confirm payment coach opens', coach is not None, pg.url[:150])
            if coach:
                coach.locator('input[type="text"]').last.fill('PAY-K2'); pg.wait_for_timeout(500); coach.locator('button:has-text("Payment done")').first.click(); pg.wait_for_timeout(6000)
                pg.screenshot(path=f'{shots}/expkit_paid.png', full_page=True)
        b.close()
    d = None
    for _ in range(20):
        d = instance(pid2)
        if d.get('executionState') != 'Active': break
        time.sleep(1.5)
    check('second instance completed through the coaches', d and d.get('executionState') == 'Completed', d and d.get('executionState'))
    check('payment reference typed in the coach reached the process', (d.get('variables') or {}).get('paymentReference') == 'PAY-K2', d.get('variables'))
    check('no page errors / 5xx during the coach drive', not errs and not bad, (errs, bad))
n_fail = sum(1 for _, ok in results if not ok); print(f'\n{len(results) - n_fail}/{len(results)} checks passed'); sys.exit(1 if n_fail else 0)
