# Expense Approval Kit (EXPKIT)

A small, complete **business process with user tasks** for IBM BAW, built entirely by a generator: a lane per team, a system task,
a manager review with Approve / Reject buttons, a rejection loop to a requester revision task, a finance payment task, searchable
business data and a REST start payload. It is the worked example of building processes with the twxkit generator (`App.bpd()`,
task coaches from `cshs(inputs=, outputs=, exits=)`), verified on IBM BPM 8.6.2 / BAW 20 and BAW 26: import, REST drive with the
rejection loop, task coaches in Process Portal, diagram rendering in the web designer.

**Target:** IBM BPM 8.6.2, IBM BAW 20-26 (traditional) and CP4BA (Workflow Authoring / Studio import). Out-of-the-box building blocks
only (System Data, UI Toolkit, client-side human services, one service flow) - no third-party toolkit, no custom Java.

## Install

1. Import `packages/Expense-Approval-Kit-1.3.twx` (Process Center / Workflow Center console: *Import Process App*; CP4BA: Business Automation Studio > *Import*).
2. Put your managers and finance users into the teams *Expense Managers* and *Expense Finance* (the package's members are the lab administrator).
3. Start *Expense Approval* from Process Portal, or over REST:
   `POST /rest/bpm/wle/v1/process?action=start&bpdId=<bpd id>&branchId=<branch id>&params={"request":{"requestId":"EXP-1","employee":"Sam Lee","amount":250,"category":"Travel","purpose":"Site visit"}}`
   (the ids are in the exposed items: `GET /rest/bpm/wle/v1/exposed/process`).

## The process

```
Start -> Validate (system task) -> Review expense (managers) -> Approved? -> [approve] Confirm payment (finance) -> Paid
                                                                          -> [default] Revise expense (requester) -> back to Validate
```

| Task | Team | Coach |
|---|---|---|
| Review expense | Expense Managers | request summary, policy note, comment, **Approve** / **Reject** |
| Revise expense | All Users | manager feedback, editable amount / category / purpose, **Resubmit** |
| Confirm payment | Expense Finance | request summary, payment reference, **Payment done** |

## Documents

* [docs/DESIGN.md](docs/DESIGN.md) - the process, the task services, what was verified and the findings recorded while building it.
* [docs/BUILD-A-PROCESS-WITH-USER-TASKS.md](docs/BUILD-A-PROCESS-WITH-USER-TASKS.md) - the rules that decide whether a generated
  process is usable (lane-relative node coordinates, coach exits, parameter mapping, REST start / complete) and the generator API.

## Rebuilding and testing

`tools/build_expkit.py [--snapshot 1.3]` renders the package with `tools/twxkit.py` (standard library only, no base export);
`tools/pc_expkit_test.py <ids.json>` drives an instance over REST (reject, revise, approve, pay) and then through the task coaches
in Process Portal (Playwright). The generator and the kit are also served to AI agents by the **BAW Knowledge MCP server**
(`https://bawmcp.dosvak.com/mcp`, see [dosvak/baw-mcp](https://github.com/dosvak/baw-mcp)): `get_package('expense approval kit')`,
`get_tool('build_expkit.py')`, `get_topic('howto-build-a-process-with-user-tasks')`.
