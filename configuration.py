# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields

__all_ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Milestone Configuration'
    __name__ = 'project.milestone.configuration'

    # advancement_product = fields.Many2One(
    #     'product.product', 'Default Advancement Product'),
    milestone_sequence = fields.Property(fields.Many2One('ir.sequence',
        'Milestone Sequence', domain=[
            ('code', '=', 'project.work.milestone'),
            ]))
