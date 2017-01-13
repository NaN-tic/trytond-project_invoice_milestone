# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import configuration
from . import milestone
from . import work
from . import invoice


def register():
    Pool.register(
        configuration.Configuration,
        milestone.MilestoneTypeGroup,
        milestone.MilestoneType,
        milestone.Milestone,
        work.Work,
        work.WorkInvoicedProgress,
        invoice.Invoice,
        invoice.InvoiceMilestoneRelation,
        invoice.InvoiceLine,
        module='project_invoice_milestone', type_='model')
