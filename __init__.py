# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .configuration import *
from .milestone import *
from .work import *
from .invoice import *


def register():
    Pool.register(
#    Certification,
        Configuration,
        MilestoneTypeGroup,
        MilestoneType,
        Milestone,
        Work,
        WorkInvoicedProgress,
        Invoice,
        InvoiceMilestoneRelation,
        InvoiceLine,
        module='project_invoice_milestone', type_='model')
