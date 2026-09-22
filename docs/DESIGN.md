# Expense Approval Kit (EXPKIT) - process application

The worked example of a **business process with user tasks built entirely with twxkit** (no base export, no toolkit zips):
`tools/build_expkit.py` -> `Expense-Approval-Kit-<snapshot>.twx` + `.ids.json`. It exists to prove and document what an agent
needs to build an approval process that imports, runs and looks right in the web designer; it is also the reference that the
BAW Knowledge MCP hands out (topic "How to build a process with user tasks", package "Expense Approval Kit").

## The process

Lanes (top to bottom): Expense Managers (team), Requesters (All Users), Expense Finance (team), System.

```
Start -> Validate (system task, EXP Validate) -> Review expense (manager) -> Approved? -> [tw.local.decision == "approve"] Confirm payment (finance) -> Paid
                                                                                       -> [default] Revise expense (requester) -> back to Validate
```

* Start parameter `request` (business object ExpenseRequest: requestId, employee, amount (Decimal), category, purpose) = the REST start payload.
* Private variables `note`, `decision`, `managerComment`, `paymentReference`; searchable business data Employee (`request.employee`) and Amount.
* Instance name `"Expense " + tw.local.request.requestId`; exposed to All Users.

## Task human services (client-side, one coach each)

| Service | Team | In | Out | Coach |
|---|---|---|---|---|
| Review Expense | Expense Managers | request, note | decision, comment | request summary, policy note, comment, **Approve** / **Reject** (exits set `tw.local.decision`) |
| Revise Expense | All Users | request, managerComment | request | feedback, editable amount / category / purpose, **Resubmit** |
| Confirm Payment | Expense Finance | request | paymentReference | request summary, payment reference, **Payment done** |

`exits={'BtnApprove': 'tw.local.decision = "approve";', ...}` renders, per button, a sequence flow from the coach with a
`coachEventBinding` naming the button, an optional script task and the link to End - the verified shape of a task coach that
completes the task from Process Portal. The same parameter name may be an input and an output (`request` in / out in Revise Expense).

## What was verified (2026-09-22)

| Check | 8.6.2 lab (BAW 20.0.0.1) | BAW 26.0.0.0 lab |
|---|---|---|
| Import (console wizard, `pc_import.py`) | 1.0, 1.1, 1.3 | 1.0, 1.1, 1.3 |
| REST drive (`pc_expkit_test.py`): start with the `request` payload, reject -> Revise (All Users) -> resubmit -> Review again -> approve -> Confirm payment -> Completed, final variables, instance name, searchable data | pass | pass |
| Coach drive: Review task opened through `/ProcessPortal/launchTaskCompletion?taskId=`, fields and note shown, Approve completes the task, Confirm payment coach, Payment done -> instance Completed, no page errors | pass (25/25) | pass (25/25; the portal shows a "Claim Task" dialog for an unclaimed team task - the test claims over REST first) |
| Designer (`design_sweep.py --types bpd,process`): every node inside its lane, links attached; human service Diagram tab shows Start -> Coach -> exit scripts -> End | pass | - |

Run: `python3 tools/pc_expkit_test.py <ids.json> [--no-ui]` (`BAW_HOST` for another server; screenshots in `EXPKIT_SHOTS`).

## Findings recorded while building it (see docs/TWX-AUTHORING-NOTES.md "Process diagrams: lane-relative coordinates ...")

* A BPD node's `y` is relative to the top of its lane in all three representations (BPMN `nodeVisualInfo`, jsonData, legacy
  `<location>`). Copilot's Expense Approval Demo and our older generators (headless sample, triage sample, TDG processes) used
  absolute values: the designer drew every node except those of the first lane below the pool. `bpd_builder.py` now converts absolute
  y (default) or takes lane-relative values (`lane_relative=True`); twxkit takes lane-relative values and lays out automatically.
* The kit's coach flow nodes carried negative coordinates copied from an export: the human service Diagram tab was blank except one
  node at the top edge. Now Start (50, 200), call (200, 177), Coach (220/380, 177), exits (400/560, 100 + 90 n), End.
* `parts=tasks` alone on `GET /process/{id}` returns no tasks; `parts=all` does. Process start on a Process Center needs `branchId`
  (`snapshotId` answers CWTBG0586E).
* Copilot's build carried the base export's project settings (administrators team "TDSH Admin", namespace `http://TDSH`) - a
  template-bound generator inherits them; a from-scratch build does not.
