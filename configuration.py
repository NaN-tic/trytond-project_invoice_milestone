# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields

__all_ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Project Invoice Milestone Configuration'
    __name__ = 'project.invoice_milestone.configuration'
    _table = 'project_invoice_milestone_config'
    milestone_sequence = fields.Property(fields.Many2One('ir.sequence',
        'Milestone Sequence', domain=[
            ('code', '=', 'project.invoice_milestone'),
            ]))
    advancement_product = fields.Many2One('product.product',
        'Default Advancement Product')
    compensation_product = fields.Many2One('product.product',
        'Default Compensation Product')
