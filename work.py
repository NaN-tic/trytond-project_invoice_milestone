# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import datetime
from decimal import Decimal

from trytond.model import fields, ModelView
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Eval, Or

__all__ = ['Work', 'WorkInvoicedProgress']


DRAFT_STATES = {
    'readonly': Eval('state') != 'draft',
    }
OPENED_STATES = {
    'readonly': Eval('state') != 'opened',
    }
DEPENDS = ['state']


def update_states(field, new_states, key):
    assert key in new_states
    if field.states and key in field.states:
        field.states[key] = Or(
            field.states[key], new_states[key])
    elif field.states:
        field.states[key] = new_states[key]
    else:
        field.states = new_states


class Work:
    __name__ = 'project.work'
    __metaclass__ = PoolMeta
    milestone_group_type = fields.Many2One(
        'project.invoice_milestone.type.group', 'Milestone Group Type',
        states={
            'invisible': ((Eval('type') != 'project') |
                (Eval('project_invoice_method') != 'milestone')),
            'readonly': ((Eval('state') != 'draft')
                | Bool(Eval('milestones'))),
            },
        depends=['type', 'state', 'milestones'])
    milestones = fields.One2Many('project.invoice_milestone', 'project',
        'Milestones', states={
            'invisible': ((Eval('type') != 'project') |
                (Eval('project_invoice_method') != 'milestone')),
            'readonly': Eval('state') == 'done',
            },
        depends=['type', 'project_invoice_method', 'state'])

    @classmethod
    def __setup__(cls):
        super(Work, cls).__setup__()
        draft = ('draft', 'Draft')
        if draft not in cls.state.selection:
            cls.state.selection.insert(0, draft)

        update_states(cls.type, {
                'readonly': Eval('id', -1) > 0,
                }, 'readonly')
        cls.type.depends.append('id')

        for field_name in (
                'project_invoice_method',  # project_invoice
                ):
            field = getattr(cls, field_name)
            update_states(field, DRAFT_STATES, 'readonly')
            if 'state' not in field.depends:
                field.depends += DEPENDS
        for field_name in (
                'effort_duration', #'progress',  # project
                # project_product
                #'quantity', 'progress_quantity', 'progress_quantity_func',
                ):
            field = getattr(cls, field_name)
            update_states(field, OPENED_STATES, 'readonly')
            if 'state' not in field.depends:
                field.depends += DEPENDS

        invoice_method = ('milestone', 'Milestones')
        for field_name in ['invoice_method', 'project_invoice_method']:
            field = getattr(cls, field_name)
            if invoice_method not in field.selection:
                field.selection.append(invoice_method)

        update_states(cls.duration_to_invoice._field, {
                'invisible': Eval('invoice_method') == 'milestone',
                }, 'invisible')

        cls._buttons['invoice']['invisible'] = (
            cls._buttons['invoice']['invisible']
            | (Eval('project_invoice_method', 'milestone') == 'milestone'))

        cls._buttons.update({
                'draft': {
                    'invisible': ((Eval('state') == 'draft')
                        | (Eval('type') != 'project')),
                    },
                'create_milestone': {
                    'invisible': ((Eval('type') != 'project')
                        | (Eval('project_invoice_method') != 'milestone')
                        | Eval('milestones')),
                    },
                })
        cls._error_messages.update({
                'draft_task': ('You cannot set to draft the task "%s". '
                    'Only projects have "Draft" state.'),
                'draft_project_invoiced_milestones': (
                    'You cannot set to draft the Project "%s" because'
                    ' almost its milestone "%s" is invoiced.'),
                'done_project_draft_milestones': (
                    'You cannot set to done the Project "%(project)s" because'
                    ' almost its milestone "%(milestone)s" is in Draft '
                    'state.'),
                'invoice_method_product_type': ('Can not select the Invoice Method'
                    ' "%s" and Invoice Product Type "%s"'),
                })

    @classmethod
    def validate(cls, works):
        super(Work, cls).validate(works)
        for work in works:
            work.check_invoice_method_product_type()

    def check_invoice_method_product_type(self):
        if self.project_invoice_method == 'milestone' \
                and not self.invoice_product_type == 'goods':
            self.raise_user_error('invoice_method_product_type',
                (self.invoice_method, self.invoice_product_type))

    @fields.depends('type', 'state')
    def on_change_with_state(self):
        if self.id < 0:
            if self.type == 'project':
                return 'draft'
            else:
                return 'opened'
        return self.state

    @classmethod
    @ModelView.button
    def draft(cls, works):
        for work in works:
            if work.type != 'project':
                cls.raise_user_error('draft_task', (work.rec_name,))
            for milestone in work.milestones:
                if milestone.state == 'invoiced':
                    cls.raise_user_error('draft_project_invoiced_milestones',
                            (work.rec_name, milestone.rec_name, ))
            work.state = 'draft'
        cls.save(works)

    @classmethod
    @ModelView.button
    def open(cls, works):
        pool = Pool()
        Milestone = pool.get('project.invoice_milestone')
        super(Work, cls).open(works)
        milestones = []
        for work in works:
            milestones += work.milestones
        Milestone.check_trigger(milestones)

    @classmethod
    @ModelView.button
    def done(cls, works):
        pool = Pool()
        Milestone = pool.get('project.invoice_milestone')
        super(Work, cls).done(works)
        milestones = []
        for work in works:
            for milestone in work.milestones:
                if milestone.state == 'draft':
                    cls.raise_user_error('done_project_draft_milestones', {
                            'project': work.rec_name,
                            'milestone': milestone.rec_name,
                            })
            milestones += work.milestones
        Milestone.check_trigger(milestones)

    @classmethod
    @ModelView.button
    def create_milestone(cls, works):
        pool = Pool()
        Milestone = pool.get('project.invoice_milestone')
        milestones = []
        for work in works:
            if not work.milestone_group_type or work.milestones:
                continue
            milestones += work.milestone_group_type.compute(work)
        Milestone.save(milestones)

    @property
    def pending_to_compensate_advanced_amount(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        advanced_amount = Decimal(0)
        invoice_ids = []
        milestone_ids = []
        for milestone in self.milestones:
            if not milestone.invoice or milestone.invoice.state == 'cancel':
                continue
            if milestone.invoice_method == 'fixed':
                if milestone.is_credit:
                    # If it's necessary to get the invoice line amount, save
                    # relation to inv line on Milestone._credit()
                    advanced_amount += milestone.advancement_amount
                else:
                    advanced_amount += milestone.invoice.untaxed_amount
            else:
                invoice_ids.append(milestone.invoice.id)
                milestone_ids.append(milestone.id)

        if advanced_amount == Decimal(0) or not milestone_ids:
            return advanced_amount

        # Get all compensation lines (origin is project's milestones)
        compensation_inv_lines = InvoiceLine.search([
                ('invoice', 'in', invoice_ids),
                ('origin.id', 'in', milestone_ids,
                    'project.invoice_milestone'),
                ])
        if not compensation_inv_lines:
            return advanced_amount
        return (advanced_amount
            + sum(il.amount for il in compensation_inv_lines))

    def get_invoice_method(self, name):
        """Milestone invoice method is like progress but invoicing triggered
        from milestones and with advancements and remainder features."""
        if self.type == 'project':
            return ('progress' if self.project_invoice_method == 'milestone'
                else self.project_invoice_method)
        else:
            return super(Work, self).get_invoice_method(name)

    def _get_lines_to_invoice_remainder(self):
        pool = Pool()
        InvoicedProgress = pool.get('project.work.invoiced_progress')

        if self.invoice_line:
            return []

        if self.invoice_product_type == 'service':
            invoiced_progress = sum(x.effort_hours
                for x in self.invoiced_progress)
            quantity = self.effort_hours - invoiced_progress
            product = self.product
            invoiced_progress = InvoicedProgress(work=self,
                effort_duration=datetime.timedelta(hours=quantity))
        elif self.invoice_product_type == 'goods':
            invoiced_quantity = sum(x.quantity for x in self.invoiced_progress)
            quantity = self.quantity - invoiced_quantity
            product = self.product_goods
            invoiced_progress = InvoicedProgress(work=self,
                quantity=quantity)
        else:
            return []

        if quantity > 0:
            if not product:
                self.raise_user_error('missing_product',
                    (self.rec_name,))
            elif self.list_price is None:
                self.raise_user_error('missing_list_price', (self.rec_name,))
            vals = {
                'product': product,
                'quantity': quantity,
                'unit_price': self.list_price,
                'origin': invoiced_progress,
                'description': self.name,
                }
            if self.invoice_product_type == 'goods':
                vals['unit'] = self.uom
            return [vals]
        return []

    @classmethod
    def create(cls, vlist):
        for vals in vlist:
            if not vals.get('state') and vals.get('type', '') == 'project':
                vals['state'] = 'draft'
            elif not vals.get('state'):
                vals['state'] = 'opened'
        return super(Work, cls).create(vlist)

    @classmethod
    def copy(cls, works, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['milestones'] = None
        if default.get('type', '') == 'project':
            default['state'] = 'draft'
        else:
            default['state'] = 'opened'
        return super(Work, cls).copy(works, default=default)


class WorkInvoicedProgress:
    __name__ = 'project.work.invoiced_progress'
    __metaclass__ = PoolMeta

    def _credit(self):
        '''
        Return values to credit invoiced progress.
        '''
        invoiced_progress = self.__class__()
        invoiced_progress.work = self.work
        if self.effort_duration is not None:
            invoiced_progress.effort_duration = self.effort_duration * -1
        if self.quantity is not None:
            invoiced_progress.quantity = -self.quantity
        # invoiced_progress.invoice_line'] = credit invoice line
        return invoiced_progress
