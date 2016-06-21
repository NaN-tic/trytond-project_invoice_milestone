# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import datetime
from decimal import Decimal

from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

__all__ = ['Work', 'WorkInvoicedProgress']


class Work:
    __name__ = 'project.work'
    __metaclass__ = PoolMeta
    milestones = fields.One2Many('project.invoice_milestone', 'project',
        'Milestones', states={
            'invisible': ((Eval('type') != 'project') |
                (Eval('project_invoice_method') != 'milestone')),
            },
        depends=['type', 'project_invoice_method'])

    @classmethod
    def __setup__(cls):
        super(Work, cls).__setup__()
        invoice_method = ('milestone', 'Milestones')
        for field_name in ['invoice_method', 'project_invoice_method']:
            field = getattr(cls, field_name)
            if invoice_method not in field.selection:
                field.selection.append(invoice_method)
        if 'invoice' in cls._buttons:
            cls._buttons['invoice']['invisible'] = (
                cls._buttons['invoice']['invisible']
                | (Eval('project_invoice_method', 'milestone') == 'milestone'))

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
    def copy(cls, works, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['milestones'] = None
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
