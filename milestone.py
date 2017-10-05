# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If
from trytond.transaction import Transaction
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from itertools import groupby
from jinja2 import Template as Jinja2Template

__all__ = ['MilestoneTypeGroup', 'MilestoneType', 'Milestone']

_KIND = [
    ('manual', 'Manual'),
    ('system', 'System'),
    ]
_TRIGGER = [
    ('', ''),
    ('start_project', 'On Project Start'),
    ('progress', 'On % Progress'),
    ('finish_project', 'On Project Finish'),
    ]
_ZERO = Decimal('0.0')


class MilestoneMixin:
    kind = fields.Selection(_KIND, 'Kind', required=True, select=True)
    trigger = fields.Selection(_TRIGGER, 'Trigger', sort=False,
        states={
            'required': Eval('kind') == 'system',
            'invisible': Eval('kind') != 'system',
            }, depends=['kind'],
        help='Defines when the Milestone will be confirmed and its Invoice '
        'Date calculated.')
    trigger_progress = fields.Numeric('On Progress',
        digits=(16, 8),
        domain=[
            ['OR',
                ('trigger_progress', '=', None),
                [
                    ('trigger_progress', '>=', 0),
                    ('trigger_progress', '<=', 1),
                    ],
                ],
            ],
        states={
            'required': ((Eval('kind') == 'system') &
                (Eval('trigger') == 'progress')),
            'invisible': ((Eval('kind') != 'system') |
                (Eval('trigger') != 'progress')),
            }, depends=['kind', 'trigger'],
        help="The percentage of progress over the total amount of Project.")
    invoice_method = fields.Selection([
            ('fixed', 'Fixed'),
            ('percent', 'Percent'),
            ('progress', 'Progress'),
            ('remainder', 'Remainder'),
            ], 'Invoice Method', required=True, sort=False)
    advancement_product = fields.Many2One('product.product',
        'Advancement Product', states={
            'required': Eval('invoice_method') == 'fixed',
            'invisible': Eval('invoice_method') != 'fixed',
            }, depends=['invoice_method'])
    invoice_percent = fields.Numeric('Invoice Percent',
        digits=(16, 8),
        states={
            'required': Eval('invoice_method') == 'percent',
            'invisible': Eval('invoice_method') != 'percent',
            },
        depends=['invoice_method', 'currency_digits'])
    advancement_amount = fields.Numeric('Advancement Amount',
        digits=(16, Eval('currency_digits', 2)),
        states={
            'required': Eval('invoice_method') == 'fixed',
            'invisible': Eval('invoice_method') != 'fixed',
            },
        depends=['invoice_method', 'currency_digits'])
    compensation_product = fields.Many2One('product.product',
        'Compensation Product', states={
            'required': Eval('invoice_method').in_(['progress', 'remainder']),
            'invisible': ~Eval('invoice_method').in_(
                ['percent', 'progress', 'remainder']),
            }, depends=['invoice_method'])
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'required': Eval('invoice_method') == 'fixed',
            'invisible': Eval('invoice_method') != 'fixed',
            },
        depends=['invoice_method'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    months = fields.Integer('Number of Months', required=True)
    month = fields.Selection([
            (None, ''),
            ('1', 'January'),
            ('2', 'February'),
            ('3', 'March'),
            ('4', 'April'),
            ('5', 'May'),
            ('6', 'June'),
            ('7', 'July'),
            ('8', 'August'),
            ('9', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December'),
            ], 'Month', sort=False)
    weeks = fields.Integer('Number of Weeks', required=True)
    weekday = fields.Selection([
            (None, ''),
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
            ], 'Day of Week', sort=False)
    days = fields.Integer('Number of Days', required=True)
    day = fields.Integer('Day of Month', domain=[
            ['OR', [
                ('day', '=', None),
                ], [
                ('day', '>=', 1),
                ('day', '<=', 31),
                ]],
            ])
    description = fields.Text('Description',
        help='It will be used to prepare the description field of invoice '
        'lines.\nYou can use tags and they will be replaced by these '
        'fields from the record related to milestone: {{ record.rec_name }}.')

    @staticmethod
    def default_kind():
        return 'manual'

    @staticmethod
    def default_invoice_method():
        return 'fixed'

    @staticmethod
    def default_advancement_product():
        pool = Pool()
        Config = pool.get('project.invoice_milestone.configuration')
        config = Config.get_singleton()
        if getattr(config, 'advancement_product', None):
            return config.advancement_product.id

    @staticmethod
    def default_compensation_product():
        pool = Pool()
        Config = pool.get('project.invoice_milestone.configuration')
        config = Config.get_singleton()
        if config and config.compensation_product:
            return config.compensation_product.id

    @staticmethod
    def default_currency():
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            return Company(company_id).currency.id

    @staticmethod
    def default_currency_digits():
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            return Company(company_id).currency.digits
        return 2

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @staticmethod
    def default_months():
        return 0

    @staticmethod
    def default_weeks():
        return 0

    @staticmethod
    def default_days():
        return 0


class MilestoneTypeGroup(ModelSQL, ModelView):
    'Project Invoice Milestone Type Group'
    __name__ = 'project.invoice_milestone.type.group'
    name = fields.Char('Name', required=True, translate=True)
    active = fields.Boolean('Active')
    description = fields.Char('Description', translate=True)
    lines = fields.One2Many('project.invoice_milestone.type', 'group', 'Lines')

    @staticmethod
    def default_active():
        return True

    def compute(self, project):
        milestones = []
        for line in self.lines:
            milestone = line.compute_milestone(project)
            milestones.append(milestone)
        return milestones


class MilestoneType(ModelSQL, ModelView, MilestoneMixin):
    'Milestone Type'
    __name__ = 'project.invoice_milestone.type'
    group = fields.Many2One('project.invoice_milestone.type.group',
        'Group', required=True, select=True, ondelete='CASCADE')
    sequence = fields.Integer('Sequence',
        help='Use to order lines in ascending order')

    @classmethod
    def __setup__(cls):
        super(MilestoneType, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == None, table.sequence]

    def compute_milestone(self, project):
        pool = Pool()
        Milestone = pool.get('project.invoice_milestone')

        milestone = Milestone()
        milestone.project = project
        milestone.kind = self.kind
        milestone.invoice_percent = self.invoice_percent
        if self.kind == 'system':
            milestone.trigger = self.trigger
            milestone.trigger_progress = self.trigger_progress
        milestone.invoice_method = self.invoice_method
        if self.invoice_method == 'fixed':
            milestone.advancement_product = self.advancement_product
            milestone.advancement_amount = self.advancement_amount
            milestone.currency = self.currency
        else:
            milestone.compensation_product = self.compensation_product
        for fname in ('months', 'month', 'weeks', 'weekday', 'days', 'day',
                'description'):
            setattr(milestone, fname, getattr(self, fname))
        # invoice_date, planned_invoice_date
        return milestone


class Milestone(Workflow, ModelSQL, ModelView, MilestoneMixin):
    'Milestone'
    __name__ = 'project.invoice_milestone'
    _rec_name = 'number'

    number = fields.Char('Number', readonly=True, select=True)
    project = fields.Many2One('project.work', 'Project', required=True,
        ondelete='CASCADE', select=True, domain=[
            ('type', '=', 'project'),
            ('project_invoice_method', '=', 'milestone'),
            ('company', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    project_company = fields.Function(fields.Many2One('company.company',
            'Project Company'),
        'on_change_with_project_company', searcher='search_project_field')
    project_party = fields.Function(fields.Many2One('party.party',
            'Project Party'),
        'on_change_with_project_party', searcher='search_project_field')

    is_credit = fields.Boolean('Is Credit?', readonly=True)
    invoice_date = fields.Date('Invoice Date', states={
            'readonly': ~Eval('state', '').in_(['draft', 'confirmed']),
            'required': Eval('state', '') == 'invoiced',
            }, depends=['state'])
    planned_invoice_date = fields.Date('Planned Invoice Date',
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    invoice = fields.One2One('account.invoice-project.invoice_milestone',
        'milestone', 'invoice', 'Invoice', domain=[
            ('company', '=', Eval('project_company', -1)),
            ('party', '=', Eval('project_party', -1)),
            ], readonly=True, depends=['project_company', 'project_party'])
    # Selection items set in __setup__
    invoice_state = fields.Function(fields.Selection([], 'Invoice State'),
        'get_invoice_state', searcher='search_invoice_state')
    invoiced_amount = fields.Function(fields.Numeric('Invoiced Amount'),
        'get_invoiced_amount')
    state = fields.Selection([
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('invoiced', 'Invoiced'),
            ('cancel', 'Cancelled'),
            ], 'State', readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        Invoice = Pool().get('account.invoice')
        super(Milestone, cls).__setup__()
        for field_name in ['kind', 'trigger', 'trigger_progress',
                'invoice_method', 'advancement_product', 'advancement_amount',
                'compensation_product', 'currency', 'months', 'month', 'weeks',
                'weekday', 'days', 'day', 'description']:
            field = getattr(cls, field_name)
            if not field.states.get('readonly'):
                field.states['readonly'] = Eval('state') != 'draft'
            else:
                field.states['readonly'] = (field.states['readonly']
                    | (Eval('state') != 'draft'))
            field.depends.append('state')
        cls.invoice_state.selection = Invoice.state.selection[:]
        cls._transitions |= set((
                ('draft', 'confirmed'),
                ('confirmed', 'invoiced'),
                ('draft', 'cancel'),
                ('confirmed', 'cancel'),
                ('invoiced', 'cancel'),
                ('cancel', 'draft'),
                ))
        cls.invoice_state.selection += [(None, '')]
        cls._buttons.update({
                'draft': {
                    'invisible': ((Eval('state') != 'cancel')
                        | Bool(Eval('invoice'))),
                    'icon': 'tryton-clear',
                    },
                'confirm': {
                    'invisible': Eval('state') != 'draft',
                    'icon': 'tryton-ok',
                    },
                'check_trigger': {
                    'invisible': ((Eval('state') != 'confirmed')
                        | (Eval('kind') == 'manual')),
                    'icon': 'tryton-executable',
                    },
                'do_invoice': {
                    'invisible': (
                        (Eval('state') != 'confirmed') |
                        (Eval('kind') != 'manual') |
                        Eval('invoice')),
                    'icon': 'tryton-ok',
                    },
                'cancel': {
                    'invisible': Eval('state').in_(['invoiced', 'cancel']),
                    'icon': 'tryton-cancel',
                    },

                })
        cls._error_messages.update({
                'missing_project_invoice_milestone_sequence': (
                    'The "Milestone Sequence" configuration param is empty in '
                    'Project\'s "Invoice Milestones Configuration".'),
                'reset_milestone_with_invoice': (
                    'You cannot reset to draft the Milestone "%s" because it '
                    'has an invoice. Duplicate it to reinvoice.'),
                'reset_milestone_done_project': (
                    'You cannot reset to draft the Milestone "%s" because its '
                    'project is already done.'),
                'reset_credit_milestone': (
                    'You cannot reset to draft the Milestone "%s" because it '
                    'is a credit milestone.'),
                })

    @classmethod
    def view_attributes(cls):
        return [
            ('/form//group[@id="invoice_date_calculator"]', 'states',
                {'invisible': Eval('kind') != 'system'}),
            ]

    @fields.depends('project')
    def on_change_with_project_company(self, name=None):
        return self.project.company.id if self.project else None

    @fields.depends('project')
    def on_change_with_project_party(self, name=None):
        return (self.project.party.id
            if self.project and self.project.party else None)

    @classmethod
    def search_project_field(cls, name, clause):
        project_fname = name.replace('project_', '')
        return [
            ('project.%s' % project_fname,) + tuple(clause[1:]),
            ]

    @fields.depends('project', 'invoice_method')
    def on_change_with_currency(self):
        if self.invoice_method == 'fixed' and self.project:
            return self.project.company.currency.id

    @classmethod
    def search_invoice_state(cls, name, clause):
        return [('invoice.state',) + tuple(clause[1:])]

    def get_invoice_state(self, name):
        return self.invoice.state if self.invoice else None

    def get_invoiced_amount(self, name):
        return self.invoice.untaxed_amount if self.invoice else Decimal(0)

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def set_number(cls, milestones):
        '''
        Fill the number field with the milestone sequence
        '''
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('project.invoice_milestone.configuration')

        config = Config(1)
        if not config.milestone_sequence:
            cls.raise_user_error('missing_project_invoice_milestone_sequence')

        for milestone in milestones:
            if milestone.number:
                continue
            milestone.number = Sequence.get_id(config.milestone_sequence.id)

    def _credit(self, credit_invoice):
        pool = Pool()
        Config = pool.get('project.invoice_milestone.configuration')
        Date = pool.get('ir.date')

        config = Config(1)
        milestone = self.__class__()

        for fname in ('project', 'advancement_product', 'compensation_product',
                'currency', 'description'):
            setattr(milestone, fname, getattr(self, fname))

        milestone.kind = 'manual'
        milestone.invoice_method = 'fixed'
        milestone.is_credit = True

        if self.invoice_method == 'fixed':
            milestone.advancement_amount = -self.advancement_amount
        else:
            milestone.currency = self.invoice.currency
            compensation_amount = Decimal(0)
            for inv_line in self.invoice.lines:
                if inv_line.origin == self:
                    compensation_amount = -inv_line.amount
                    break
            milestone.advancement_amount = compensation_amount
        milestone.advancement_product = config.advancement_product

        milestone.project = self.project
        milestone.invoice_date = credit_invoice.invoice_date or Date.today()
        milestone.invoice = credit_invoice
        return milestone

    @classmethod
    def cron_check_triggers(cls):
        'Cron Check Triggers'
        milestones = cls.search([
            ('state', '=', 'confirm'),
            ('kind', '=', 'system'),
            ('invoice', '=', None),
            ])
        if milestones:
            cls.check_trigger(milestones)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, milestones):
        for milestone in milestones:
            if milestone.invoice:
                cls.raise_user_error('reset_milestone_with_invoice',
                    (milestone.rec_name,))
            if milestone.project.state == 'done':
                cls.raise_user_error('reset_milestone_done_project',
                    (milestone.rec_name,))
            if milestone.is_credit:
                cls.raise_user_error('reset_credit_milestone',
                    (milestone.rec_name,))

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, milestones):
        cls.set_number(milestones)
        cls.save(milestones)

    @classmethod
    @Workflow.transition('invoiced')
    def invoiced(cls, milestones):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, milestones):
        assert all(m.invoice == None for m in milestones)
        # TODO
        pass

    @classmethod
    @ModelView.button
    def check_trigger(cls, milestones):
        triggered_milestones = cls.check_trigger_condition(milestones)
        cls.do_invoice(triggered_milestones)

    @classmethod
    def check_trigger_condition(cls, milestones):
        triggered_milestones = []
        for milestone in milestones:
            if (milestone.state != 'confirmed' or milestone.kind == 'manual' or
                    milestone.invoice):
                continue
            method = getattr(milestone, 'check_trigger_%s'
                    % milestone.trigger)
            triggered = method()
            if not triggered:
                continue
            triggered_milestones.append(milestone)
        return triggered_milestones

    def check_trigger_start_project(self):
        if self.project.state == 'opened':
            return True
        return False

    def check_trigger_finish_project(self):
        if self.project.state == 'done':
            return True
        return False

    def check_trigger_progress(self):
        if self.project.percent_progress_amount >= self.trigger_progress:
            return True
        return False

    @classmethod
    @ModelView.button
    def do_invoice(cls, milestones):
        """
        It's a replica of project.work.invoice()
        """
        pool = Pool()
        Date = pool.get('ir.date')
        Invoice = pool.get('account.invoice')

        today = Date.today()
        invoices = []
        to_invoice = []
        for milestone in milestones:
            if not milestone.invoice_date:
                milestone.invoice_date = milestone._calc_invoice_date()
                milestone.save()
            if(milestone.kind == 'system' and milestone.invoice_date > today):
                continue
            if milestone.invoice:
                to_invoice.append(milestone)
                continue

            inv_line_vals = milestone._get_line_vals_to_invoice()
            if not inv_line_vals and milestone.invoice_method != 'remainder':
                continue

            invoice = milestone._get_invoice()
            invoice.project_milestone = milestone
            invoice.lines = []
            if inv_line_vals:
                invoice.save()
            elif milestone.invoice_method not in ('percent', 'progress',
                    'remainder'):
                continue

            invoice_amount = Decimal(0)
            for key, grouped_inv_line_vals in groupby(inv_line_vals,
                    key=milestone.project._group_lines_to_invoice_key):
                grouped_inv_line_vals = list(grouped_inv_line_vals)
                key = dict(key)
                invoice_line = milestone.project._get_invoice_line(
                    key, invoice, grouped_inv_line_vals)
                invoice_line.invoice = invoice
                invoice_line.origin = milestone
                invoice_line.save()
                invoice_amount += invoice_line.amount

                origins = {}
                for line_vals in grouped_inv_line_vals:
                    origin = line_vals.get('origin', None)

                    if origin:
                        origin.invoice_line = invoice_line
                        origins.setdefault(origin.__class__, []).append(origin)
                for klass, records in origins.iteritems():
                    klass.save(records)  # Store first new origins

            if milestone.invoice_method in ('percent', 'progress', 'remainder'):
                invoice_line = milestone._get_compensation_invoice_line(
                    invoice_amount)
                if invoice_line:
                    if not inv_line_vals:
                        invoice.save()
                    invoice_line.invoice = invoice
                    invoice_line.save()
                elif not inv_line_vals:
                    # not progress/remainder lines nor compensation
                    continue

            invoices.append(invoice)
            to_invoice.append(milestone)

        if invoices:
            Invoice.update_taxes(Invoice.browse([i.id for i in invoices]))
        if to_invoice:
            cls.invoiced(to_invoice)

    def _calc_invoice_date(self):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        return today + relativedelta(**self._calc_delta())

    def _calc_delta(self):
        return {
            'day': self.day,
            'month': int(self.month) if self.month else None,
            'days': self.days,
            'weeks': self.weeks,
            'months': self.months,
            'weekday': int(self.weekday) if self.weekday else None,
            }

    def _get_invoice(self):
        invoice = self.project._get_invoice()
        if hasattr(self.project.party, 'agent'):
            # Compatibility with commission_party
            invoice.agent = self.project.party.agent
        return invoice

    def _get_line_vals_to_invoice(self, work=None, test=False):
        """Return line vals for work and children.
        If work is not supplied, it use milestone's project"""
        if self.invoice_method == 'fixed':
            return self._get_line_vals_to_invoice_fixed()

        if self.invoice_method == 'percent':
            return self._get_line_vals_to_invoice_percent()

        lines = []
        if work is None:
            work = self.project
        if test is None:
            test = work._test_group_invoice()

        lines += getattr(
            work, '_get_lines_to_invoice_%s' % self.invoice_method)()
        for children in work.children:
            if children.type == 'project':
                if test != children._test_group_invoice():
                    continue
            lines += self._get_line_vals_to_invoice(work=children, test=test)
        return lines

    def _get_line_vals_to_invoice_fixed(self):
        if self.state != 'confirmed' or self.invoice:
            return []
        amount = self.advancement_amount
        return [{
                'product': self.advancement_product,
                'quantity': 1.0 if amount > _ZERO else -1.0,
                'unit': self.advancement_product.default_uom,
                'unit_price': abs(amount),
                'description': self._calc_invoice_line_description(),
                }]

    def _get_line_vals_to_invoice_percent(self):
        InvoicedProgress = Pool().get('project.work.invoiced_progress')

        if self.state != 'confirmed' or self.invoice:
            return []
        quantity = self.project.quantity * float(self.invoice_percent)
        invoiced_progress = InvoicedProgress(work=self.project,
            quantity=quantity)
        return [{
                'product': self.project.product_goods,
                'quantity': quantity,
                'unit': self.project.product_goods.default_uom,
                'unit_price': abs(self.project.list_price),
                'origin': invoiced_progress,
                'description': self._calc_invoice_line_description(),
                }]

    def _get_compensation_invoice_line(self, current_invoice_amount):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        amount = self.project.pending_to_compensate_advanced_amount
        # TODO: review
        # if self.invoice_method == 'remainder':
        #     if (self.group.merited_amount == self.group.total_amount
        #             and (self.group.invoiced_amount - amount + current_invoice_amount)
        #                 == self.group.merited_amount):
        #         # It closes the milestone group
        #         current_invoice_amount = None

        if (current_invoice_amount is not None
                and self.invoice_method != 'remainder'
                and current_invoice_amount < amount):
            # If it is remainder => if compensates all, generating a negative invoice if it corresponds
            # Otherwise, it never generates a negative invoice
            amount = current_invoice_amount
        if amount == _ZERO:
            return

        with Transaction().set_user(0, set_context=True):
            invoice_line = InvoiceLine()
        invoice_line.invoice_type = 'out'
        invoice_line.type = 'line'
        invoice_line.sequence = 1
        invoice_line.origin = self
        invoice_line.party = self.project.party
        invoice_line.product = self.compensation_product
        invoice_line.unit = self.compensation_product.default_uom
        invoice_line.on_change_product()
        invoice_line.quantity = -1.0
        invoice_line.unit_price = amount
        return invoice_line

    @staticmethod
    def template_context(record):
        """Generate the tempalte context"""
        return {
            'record': record,
            }

    def _calc_invoice_line_description(self):
        if self.description:
            template = Jinja2Template(self.description)
            template_context = self.template_context(self)
            return template.render(template_context)
        return self.number

    @classmethod
    def copy(cls, milestones, default=None):
        if default is None:
            default = {}
        default.setdefault('code', None)
        default.setdefault('invoice_date', None)
        default.setdefault('invoice', None)
        return super(Milestone, cls).copy(milestones, default)
