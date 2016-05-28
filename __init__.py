# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .configuration import *
from .milestone import *
from .work import *
from .invoice import *

def register():
    Pool.register(
        Configuration,
        Invoice,
        InvoiceMilestoneRelation,
        MilestoneTypeGroup,
        MilestoneType,
        Milestone,
        Work,
        module='project_invoice_term', type_='model')
