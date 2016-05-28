# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.pool import Pool


__all__ = ['Work']


class Work:
    __metaclass__ = PoolMeta
    __name__ = 'project.work'

    milestones = fields.One2Many('project.work.milestone', 'project',
        'Milestones',
        states={
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

    @staticmethod
    def _get_invoiced_duration_milestone(works):
        # TODO:
        return {}

    @staticmethod
    def _get_duration_to_invoice_milestone(works):
        # TODO:
        return {}

    def get_lines_to_invoice_milestone(self):
        pass

    @staticmethod
    def _get_invoiced_amount_milestone(works):
        pool = Pool()
        Currency = pool.get('currency.currency')
        amounts = {}
        for work in works:
            amounts[work.id] = Decimal(0)
            currency = work.company.currency
            for milestone in work.milestones:
                if milestone.invoice and milestone.state != 'failed':
                    amounts[work.id] += Currency.compute(
                        milestone.invoice.currency,
                        milestone.invoice.untaxed_amount, currency)
        return amounts

    def get_lines_to_invoice_progress(self, test=None):
        ''' Needed to invoce project with progress method althought it's
        defined as milestone '''
        lines = []
        if test is None:
            test = self._test_group_invoice()
        lines += self._get_lines_to_invoice_progress()
        for children in self.children:
            if children.type == 'project':
                if test != children._test_group_invoice():
                    continue
            lines += children.get_lines_to_invoice_progress(test=test)
        print "res:", lines
        return lines


