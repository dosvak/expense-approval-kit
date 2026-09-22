# How to build a process with user tasks (BPD + task coaches) that imports, runs and looks right in the designer

Scope: a business process (BPD) with lanes, user tasks implemented by client-side human services, system tasks calling service
flows, decision gateways and a rejection loop - built without a base export with the served `twxkit.py` (`build_kit`), verified
by import, REST drive, Process Portal coach drive and a designer screenshot on BPM 8.6.2 / BAW 20 and BAW 26. The worked example is
the package "Expense Approval Kit" (`get_package('Expense Approval Kit')`, generator `build_expkit.py`, test `pc_expkit_test.py`).

## 0. The rules that decide whether the result is usable (read first)

1. **A BPD carries three representations of the same diagram and all three must agree**: `bpmn2Data` (BPMN 2.0 with the WLE
   extensions: nodes, sequence flows, lanes, data objects, io specification), `jsonData` (the same model as JSON; the designer reads
   the variables from it) and the legacy `BusinessProcessDiagram` block (what the importer reads: lanes with their flow objects, ports,
   parameter mappings, private variables). Hand-writing one of them from memory produces a package that imports and then shows an
   empty or half-drawn process. `twxkit.App.bpd()` renders all three from one description.
2. **Node y is measured from the top of the node's lane, in every representation.** The designer draws a node at
   (x, lane.y + y). An "absolute" y (lane offset already added) puts every node outside the first lane below the pool: the diagram
   shows only the links, the nodes sit under the last lane. Vendor exports prove the convention (a Start in a System lane at y=201
   is stored with y=56). Lanes are stacked with 1 px gaps (`y` 0, 151, 302 ... for 150 px lanes). twxkit takes lane-relative y,
   rejects a node outside its lane at build time and lays nodes out automatically when x / y are omitted.
3. **Node boxes have fixed sizes** the designer expects in `nodeVisualInfo`: events 24x24, gateways 32x32, activities 95x70. Keep
   ~150 px between columns and centre small nodes vertically in the lane (y = (lane height - node height) / 2) so links are straight.
4. **A user task calls a library human service** (`callActivity calledElement="1.<cshs id>"`, legacy `attachedActivityId="/1.<id>"`),
   with the lane's team as the performer and the parameter mappings by parameter id (2055.) of the callee. The human service declares
   its parameters (`processParameter` blocks with `parameterType` 1 = input, 2 = output, plus `dataInput` / `dataOutput` in the coach
   flow's `ioSpecification`), is not exposed (`exposedAs NotExposed`) and completes when its coach flow reaches End.
5. **A button completes a task through a coach boundary event, not through a click script**: a `sequenceFlow` from the coach
   (`formTask`) to a script task or End with `<ns3:coachEventBinding><ns3:coachEventPath>BtnApprove</ns3:coachEventPath>` names the
   button (its layout item id). The button itself carries no `eventON_CLICK`. A script task on that path sets the decision
   (`tw.local.decision = "approve";`). A coach without an exit is a task that can only be completed over REST (the shape of the
   headless samples) - a manager opening it in Process Portal sees a form without a way to finish it.
6. **Coach flow and service flow diagrams need positive coordinates too.** Start (50, 200) -> [call 200, 177] -> Coach (220/380, 177)
   -> script exits (400/560, 100 + 90 n) -> End (400/560/720, 200) is what an exported human service looks like; negative or huge
   values copied from a different canvas draw the flow off-screen (the designer shows a blank Diagram tab with one node at the top edge).
   Service flows: Start (25, 80), steps every 190 px at y=55, End 230 px after the last step (twxkit `linear()`).
7. **A gateway needs exactly one flow without a condition** (the default, evaluated last); every other outgoing flow carries a
   JavaScript condition (`tw.local.decision == "approve"`). Loops (Revise -> Review) are ordinary flows back to an earlier node; the
   target node then has two `incoming` entries in every representation.
8. **Process start parameters need a default expression** (`hasDefault true`), the REST start passes them as
   `params={"request": {...}}` (a business object is a JSON object). Start over `POST /rest/bpm/wle/v1/process?action=start&bpdId=<25.>&branchId=<2063.>`
   (the exposed start URL - `snapshotId` answers CWTBG0586E "wrong state" on a Process Center); `GET /process/{id}?parts=all` lists the
   tasks (`parts=tasks` alone returns none), `PUT /task/{id}?action=complete&params={...}` completes a task with its output parameters.
9. **Do not inherit settings from a base export.** A generator that clones another application's package keeps that application's
   administrators team, namespace (`http://<acronym>`), environment variables and project defaults: the "Process App Settings" of the
   new app show the old acronym. A from-scratch build renders its own project defaults.
10. **The same parameter name may be an input and an output** (`request` in / `request` out, the in-out idiom): they are two
   parameters with two ids. A builder keyed by name alone gives both the same id and the BPD mapping targets the wrong one.

## 1. Building it with twxkit (served generator)

```python
import twxkit as k
app = k.App('Expense Approval Kit', 'EXPKIT', '1.0', 'what it does')
app.bo('ExpenseRequest', [('requestId', 'String'), ('employee', 'String'), ('amount', 'Decimal'), ('category', 'String'), ('purpose', 'String')])
app.team('Expense Managers', users=['celladmin']); app.team('Expense Finance', users=['celladmin'])
app.flow('EXP Validate', inputs=[('amount', 'Decimal')], outputs=[('note', 'String')], script=VALIDATE_JS, ajax=False)   # system task
app.cshs('Review Expense', exposed=None, team='Expense Managers',
         inputs=[('request', 'ExpenseRequest'), ('note', 'String')], outputs=[('decision', 'String'), ('comment', 'String')],
         layout=lambda L: [L.output('Emp', 'Employee', 'tw.local.request.employee'), L.output('Note', 'Policy note', 'tw.local.note'),
                           L.text_area('Comment', 'Comment', 'tw.local.comment'),
                           L.hlayout('Buttons', [L.button('BtnApprove', 'Approve', style='P'), L.button('BtnReject', 'Reject', style='G')])],
         exits={'BtnApprove': 'tw.local.decision = "approve";', 'BtnReject': 'tw.local.decision = "reject";'})
app.cshs('Revise Expense', exposed=None, inputs=[('request', 'ExpenseRequest'), ('managerComment', 'String')], outputs=[('request', 'ExpenseRequest')],
         layout=lambda L: [..., L.button('BtnResubmit', 'Resubmit', style='P')], exits={'BtnResubmit': None})
app.bpd('Expense Approval',
        lanes=[('Expense Managers', 'Expense Managers'), ('Requesters', 'All Users'), ('Expense Finance', 'Expense Finance'), ('System', 'System')],
        nodes=[dict(key='start', kind='start', name='Start', lane='System'),
               dict(key='validate', kind='service', name='Validate', lane='System', callee='EXP Validate', inputs={'amount': 'tw.local.request.amount'}, outputs={'note': 'note'}),
               dict(key='review', kind='user', name='Review expense', lane='Expense Managers', callee='Review Expense', due_hours=24,
                    subject='Expense <#= tw.local.request.requestId #> needs review', inputs={'request': 'tw.local.request', 'note': 'tw.local.note'},
                    outputs={'decision': 'decision', 'comment': 'managerComment'}),
               dict(key='approved', kind='gateway', name='Approved?', lane='System'),
               dict(key='revise', kind='user', name='Revise expense', lane='Requesters', callee='Revise Expense', inputs={'request': 'tw.local.request', 'managerComment': 'tw.local.managerComment'}, outputs={'request': 'request'}),
               dict(key='pay', kind='user', name='Confirm payment', lane='Expense Finance', callee='Confirm Payment', inputs={'request': 'tw.local.request'}, outputs={'paymentReference': 'paymentReference'}),
               dict(key='paid', kind='end', name='Paid', lane='System')],
        flows=[('start', 'validate'), ('validate', 'review'), ('review', 'approved'), ('approved', 'pay', 'Approved', 'tw.local.decision == "approve"'),
               ('approved', 'revise', 'Revise'), ('revise', 'review', 'Resubmit'), ('pay', 'paid')],
        inputs=[('request', 'ExpenseRequest')], variables=[('note', 'String'), ('decision', 'String'), ('managerComment', 'String'), ('paymentReference', 'String')],
        searchable=[('Employee', 'request', '.employee', 'String')], exposed_team='All Users', instance_name='"Expense " + tw.local.request.requestId')
app.write('Expense-Approval-Kit-1.0.twx')     # .ids.json: start_urls (REST start), cshs ids of the tasks, branch
```

Node kinds: `start`, `end`, `timer` (`hours=` / `minutes=` after arrival, or `custom='tw.local.at'`), `script` (`script=`), `service`
(`callee=` flow name, `inputs=` / `outputs=` by parameter name), `user` (`callee=` human service name, `priority=`, `due_hours=`,
`subject=` / `narrative=` with `<#= tw.local.x #>` placeholders), `gateway` (exclusive), `parallel`. Flows are `(src, dst[, name[, condition]])`.
Coordinates: omit them (auto layout: 150 px columns in list order, centred in the lane) or give lane-relative `x`, `y`.
Types: System Data names (`String`, `Integer`, `Decimal`, `Boolean`, `Date`) or business objects declared with `bo()`.
Undercover agents / message events and inline (engine-generated) task UIs are not part of the kit; build them in the designer.

## 2. Verify

1. Import (console wizard / `pc_import.py`; Studio on CP4BA). The exposed start URL appears in `GET /rest/bpm/wle/v1/exposed/process`.
2. REST drive (`pc_expkit_test.py <ids.json> --no-ui`): start with the payload, complete each task with its output parameters,
   check the loop and the final variables. Task data: `GET /task/{id}?parts=data` shows the mapped inputs.
3. Coach drive: `/ProcessPortal/launchTaskCompletion?taskId=<tkiid>` opens the task coach; the coach lives in an iframe (search
   `page.frames` for the button text); click the exit button; the task closes and the next task appears.
4. Designer: open the BPD (Processes) - every node inside its lane, links attached to the nodes; open each human service
   (Diagram tab: Start -> Coach -> exits -> End visible) and its Coach tab. `design_sweep.py --types bpd,process` screenshots them.

## 3. Verification record

Expense Approval Kit 1.3 (`build_expkit.py`, twxkit 1.4), the same package on both targets:

| Check | BPM 8.6.2 / BAW 20 | BAW 26.0.0.0 |
|---|---|---|
| Console import (`pc_import.py`), snapshot appears with the exposed start URL | pass | pass |
| REST drive: start with `{"request": {...}}`, Review -> reject -> Revise (All Users) -> resubmit with a new amount -> Validate again -> Review -> approve -> Confirm payment -> Completed; task data, final variables, instance name, searchable field | 14/14 | 14/14 |
| Coach drive in Process Portal: Review coach shows the request and the note, Approve completes the task, Confirm payment coach, Payment done completes the instance, no page errors / 5xx | 11/11 | 11/11 |
| Designer: BPD nodes inside their lanes with attached links; human service Diagram tab Start -> Coach -> exit scripts -> End; Coach tab renders | pass | not swept |

Differences seen: Process Portal on BAW 24+ opens an **unclaimed team task with a "Claim Task" dialog** (`launchTaskCompletion`
lands on the portal home until the task is claimed) - claim over REST first (`PUT /task/{id}?action=assign&toMe=true`) or click the
dialog; the 8.6.2 portal claims silently. The Workflow Center login form of BAW 24+ has `#username` / `j_password` / `#log_in`.
