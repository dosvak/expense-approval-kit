#!/usr/bin/env python3
"""build_expkit.py - worked example of a business process on twxkit: the process application "Expense Approval Kit" (EXPKIT).

    python3 build_expkit.py [--snapshot 1.0] [--out Expense-Approval-Kit-1.0.twx]

What the app contains (the smallest realistic approval process, every object rendered by twxkit, no base export, no toolkit zips):
  * business object ExpenseRequest (requestId, employee, amount, category, purpose)
  * teams Expense Managers and Expense Finance (lab member celladmin)
  * service flow EXP Validate (system task: a note about the amount)
  * three task human services built with cshs(inputs=, outputs=, exits=): Review Expense (Approve / Reject buttons set the
    decision), Revise Expense (the requester edits the request), Confirm Payment (payment reference)
  * the process Expense Approval: Start -> Validate -> Review -> Approved? -> [yes] Confirm payment -> Paid
                                                                  -> [no]  Revise -> back to Validate (re-validated, then reviewed again)
    with a lane per team, a system lane, the start parameter `request` (also the REST start payload), private variables and a
    searchable business data field (Employee)
Node coordinates are omitted on purpose: the kit lays the nodes out left to right and centres them in their lanes.
The ids file (<out>.ids.json) lists the REST start URL of the process and the ids of the task services.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import twxkit as k

VALIDATE_JS = r'''// EXP Validate: a note for the manager (system task of the process; inputs amount, outputs note)
var amount = (tw.local.amount == null) ? 0 : Number(tw.local.amount);
tw.local.note = (amount > 1000) ? "Amount above 1000: director approval policy applies" : (amount <= 0) ? "Amount missing" : "Within policy";
'''

def request_summary(L, prefix='Req'):
    """Read-only summary of the request (Output Text controls bound to the ExpenseRequest fields)."""
    return L.panel(prefix + 'Panel', 'Expense request', [
        L.hlayout(prefix + 'Row1', [L.output(prefix + 'Id', 'Request', 'tw.local.request.requestId', show=True), L.output(prefix + 'Emp', 'Employee', 'tw.local.request.employee', show=True),
                                    L.output(prefix + 'Amt', 'Amount', 'tw.local.request.amount', show=True)]),
        L.hlayout(prefix + 'Row2', [L.output(prefix + 'Cat', 'Category', 'tw.local.request.category', show=True), L.output(prefix + 'Pur', 'Purpose', 'tw.local.request.purpose', show=True)])])

def build(snapshot, out):
    app = k.App('Expense Approval Kit', 'EXPKIT', snapshot=snapshot,
                description='Worked example of a business process built with twxkit: manager review, requester revision loop, finance payment.')
    app.bo('ExpenseRequest', [('requestId', 'String'), ('employee', 'String'), ('amount', 'Decimal'), ('category', 'String'), ('purpose', 'String')],
           description='One expense request (start parameter of the process, edited by the requester on revision).')
    app.team('Expense Managers', users=['celladmin'])
    app.team('Expense Finance', users=['celladmin'])
    app.flow('EXP Validate', inputs=[('amount', 'Decimal')], outputs=[('note', 'String')], script=VALIDATE_JS, ajax=False,
             description='System task of the process: policy note for the manager.')
    # ---- task human services (one coach each; the buttons named in exits complete the task through a boundary event)
    app.cshs('Review Expense', exposed=None, team='Expense Managers',
             inputs=[('request', 'ExpenseRequest'), ('note', 'String')], outputs=[('decision', 'String'), ('comment', 'String')],
             layout=lambda L: [request_summary(L), L.output('Note', 'Policy note', 'tw.local.note', show=True),
                               L.text_area('Comment', 'Comment for the requester', 'tw.local.comment', height='120px'),
                               L.hlayout('Buttons', [L.button('BtnApprove', 'Approve', style='P'), L.button('BtnReject', 'Reject', style='G')])],
             exits={'BtnApprove': 'tw.local.decision = "approve";', 'BtnReject': 'tw.local.decision = "reject";'},
             description='Manager task: approve the request or reject it back to the requester.')
    app.cshs('Revise Expense', exposed=None, team='All Users',
             inputs=[('request', 'ExpenseRequest'), ('managerComment', 'String')], outputs=[('request', 'ExpenseRequest')],
             layout=lambda L: [L.output('Feedback', 'Manager feedback', 'tw.local.managerComment', show=True),
                               L.panel('Edit', 'Revise the request', [
                                   L.hlayout('Row1', [L.output('Id', 'Request', 'tw.local.request.requestId', show=True), L.output('Emp', 'Employee', 'tw.local.request.employee', show=True)]),
                                   L.hlayout('Row2', [L.custom('Amt', 'Decimal', 'Amount', 'tw.local.request.amount'), L.text('Cat', 'Category', 'tw.local.request.category')]),
                                   L.text_area('Pur', 'Purpose', 'tw.local.request.purpose', height='90px')]),
                               L.button('BtnResubmit', 'Resubmit', style='P')],
             exits={'BtnResubmit': None},
             description='Requester task: change the request after a rejection and resubmit it.')
    app.cshs('Confirm Payment', exposed=None, team='Expense Finance',
             inputs=[('request', 'ExpenseRequest')], outputs=[('paymentReference', 'String')],
             layout=lambda L: [request_summary(L), L.text('Ref', 'Payment reference', 'tw.local.paymentReference'),
                               L.button('BtnPaid', 'Payment done', style='P')],
             exits={'BtnPaid': None},
             description='Finance task: record the payment reference of the approved expense.')
    # ---- the process
    app.bpd('Expense Approval',
            lanes=[('Expense Managers', 'Expense Managers'), ('Requesters', 'All Users'), ('Expense Finance', 'Expense Finance'), ('System', 'System')],
            nodes=[dict(key='start', kind='start', name='Start', lane='System'),
                   dict(key='validate', kind='service', name='Validate', lane='System', callee='EXP Validate',
                        inputs={'amount': 'tw.local.request.amount'}, outputs={'note': 'note'}),
                   dict(key='review', kind='user', name='Review expense', lane='Expense Managers', callee='Review Expense', priority='Normal', due_hours=24,
                        subject='Expense <#= tw.local.request.requestId #> needs review', narrative='<#= tw.local.request.employee #>: <#= tw.local.request.amount #> for <#= tw.local.request.purpose #>',
                        inputs={'request': 'tw.local.request', 'note': 'tw.local.note'}, outputs={'decision': 'decision', 'comment': 'managerComment'}),
                   dict(key='approved', kind='gateway', name='Approved?', lane='System'),
                   dict(key='revise', kind='user', name='Revise expense', lane='Requesters', callee='Revise Expense', due_hours=72,
                        subject='Revise expense <#= tw.local.request.requestId #>', narrative='Manager feedback: <#= tw.local.managerComment #>',
                        inputs={'request': 'tw.local.request', 'managerComment': 'tw.local.managerComment'}, outputs={'request': 'request'}),
                   dict(key='pay', kind='user', name='Confirm payment', lane='Expense Finance', callee='Confirm Payment', due_hours=48,
                        subject='Pay approved expense <#= tw.local.request.requestId #>',
                        inputs={'request': 'tw.local.request'}, outputs={'paymentReference': 'paymentReference'}),
                   dict(key='paid', kind='end', name='Paid', lane='System')],
            flows=[('start', 'validate'), ('validate', 'review', 'To review'), ('review', 'approved', 'To decision'),
                   ('approved', 'pay', 'Approved', 'tw.local.decision == "approve"'), ('approved', 'revise', 'Revise'),
                   ('revise', 'validate', 'Resubmit'), ('pay', 'paid', 'Payment confirmed')],
            inputs=[('request', 'ExpenseRequest')], variables=[('note', 'String'), ('decision', 'String'), ('managerComment', 'String'), ('paymentReference', 'String')],
            searchable=[('Employee', 'request', '.employee', 'String'), ('Amount', 'request', '.amount', 'Decimal')],
            exposed_team='All Users', instance_name='"Expense " + tw.local.request.requestId',
            description='Manager review -> payment, or requester revision -> resubmission.')
    app.write(out)
    print('\n'.join(app.log)); print('written', out)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--snapshot', default='1.0'); ap.add_argument('--out')
    a = ap.parse_args(); build(a.snapshot, a.out or f'Expense-Approval-Kit-{a.snapshot}.twx')
