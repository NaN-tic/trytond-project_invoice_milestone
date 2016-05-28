# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from itertools import groupby

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


class MilestoneTypeGroup(ModelSQL, ModelView):
    'Milestone Type Group'
    __name__ = 'project.work.milestone.type.group'
    name = fields.Char('Name', required=True, translate=True)
    active = fields.Boolean('Active')
    description = fields.Char('Description', translate=True)
    lines = fields.One2Many('project.work.milestone.type', 'group', 'Lines')


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
            ['OR', [
                ('trigger_progress', '=', None),
                ], [
                ('trigger_progress', '>=', 0),
                ('trigger_progress', '<=', 1),
                ]],
            ],
        states={
            'required': ((Eval('kind') == 'system') &
                (Eval('trigger') == 'progress')),
            'invisible': ((Eval('kind') != 'system') |
                (Eval('trigger') != 'progress')),
            }, depends=['kind', 'trigger'],
        help="The percentage of progress over the total amount of "
        "Project.")

    progress = fields.Numeric('Progress', digits=(16, 8),
        domain=[
            ('progress', '>=', 0),
            ('progress', '<=', 1),
            ])
    invoice_method = fields.Selection([
            ('fixed', 'Fixed'),
            ('remainder', 'Remainder'),
            ('progress', 'Progress'),
            ], 'Invoice Method', required=True, sort=False)
    advancement_product = fields.Many2One('product.product',
        'Advancement Product', states={
            'required': Eval('invoice_method') == 'fixed',
            'invisible': Eval('invoice_method') != 'fixed',
            }, depends=['invoice_method'])
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        states={
            'required': Eval('invoice_method') == 'fixed',
            'invisible': Eval('invoice_method') != 'fixed',
            },
        depends=['invoice_method', 'currency_digits'])
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'required': Eval('invoice_method') == 'fixed',
            'invisible': Eval('invoice_method') != 'fixed',
            },
        depends=['invoice_method'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    day = fields.Integer('Day of Month', domain=[
            ['OR', [
                ('day', '=', None),
                ], [
                ('day', '>=', 1),
                ('day', '<=', 31),
                ]],
            ])
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
    months = fields.Integer('Number of Months', required=True)
    weeks = fields.Integer('Number of Weeks', required=True)
    days = fields.Integer('Number of Days', required=True)
    description = fields.Text('Description',
        help='It will be used to prepare the description field of invoice '
        'lines.\nYou can use the next tags and they will be replaced by these '
        'fields from the sale\'s related to milestone: {sale_description}, '
        '{sale_reference}.')

    @staticmethod
    def default_currency_digits():
        return 2

    @staticmethod
    def default_invoice_method():
        return 'fixed'

    @staticmethod
    def default_progress():
        return 0

    @staticmethod
    def default_months():
        return 0

    @staticmethod
    def default_weeks():
        return 0

    @staticmethod
    def default_days():
        return 0

    # @staticmethod
    # def default_advancement_product():
    #     pool = Pool()
    #     Config = pool.get('project.milestone.configuration')
    #     config = Config.get_singleton()
    #     if config.milestone_advancement_product:
    #         return config.milestone_advancement_product.id

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2


class MilestoneType(ModelSQL, ModelView, MilestoneMixin):
    'Milestone Type'
    __name__ = 'project.work.milestone.type'
    group = fields.Many2One('project.work.milestone.type.group',
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

    @staticmethod
    def default_currency():
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            return Company(company_id).currency.id

    def compute_milestone(self, project):
        pool = Pool()
        Milestone = pool.get('project.work.milestone')

        milestone = Milestone()
        milestone.project = project
        milestone.progress = self.progress
        milestone.invoice_method = self.invoice_method
        if self.invoice_method == 'fixed':
            milestone.amount = self.amount
            milestone.currency = self.currency
            milestone.advancement_product = self.advancement_product

        for fname in ('day', 'month', 'weekday', 'months', 'weeks', 'days',
                'description'):
            setattr(milestone, fname, getattr(self, fname))

        return milestone


class Milestone(Workflow, ModelSQL, ModelView, MilestoneMixin):
    'Milestone'
    __name__ = 'project.work.milestone'
    _rec_name = 'number'

    number = fields.Char('Number', readonly=True, select=True)
    project = fields.Many2One('project.work', 'Project', required=True,
        ondelete='CASCADE', states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'],
        domain=[
            ('type', '=', 'project'),
            ('project_invoice_method', '=', 'milestone'),
            ])

    invoice_date = fields.Date('Invoice Date', states={
            'readonly': ~Eval('state', '').in_(['draft', 'confirmed']),
            'required': Eval('state', '').in_(['processing', 'succeeded']),
            }, depends=['state'])
    planned_invoice_date = fields.Date('Planned Invoice Date')
    processed_date = fields.Date('Processed Date', readonly=True)


    invoice = fields.One2One(
        'account.invoice-project.work.milestone',
         'milestone', 'invoice', 'Invoice', domain=[
            ('company', '=', Eval('project.company', -1)),
            ('party', '=', Eval('project.party', -1)),
            ], readonly=True, depends=['company', 'party'])
    state = fields.Selection([
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('processing', 'Processing'),
            ('succeeded', 'Succeeded'),
            ('failed', 'Failed'),
            ('cancel', 'Cancelled'),
            ], 'State', readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(Milestone, cls).__setup__()
        states = {
            'readonly': Eval('state') != 'draft',
            }
        depends = ['state']
        for field_name in ['progress', 'invoice_method', 'advancement_product',
                'amount', 'currency', 'weekday', 'day', 'days', 'month',
                'months', 'description']:
            field = getattr(cls, field_name)
            field.states.update(states)
            field.depends += depends

        cls._transitions |= set((
                ('draft', 'confirmed'),
                ('confirmed', 'processing'),
                ('processing', 'succeeded'),
                ('processing', 'failed'),
                ('succeeded', 'failed'),  # If invoice is cancelled after post
                ('succeeded', 'processing'),  # If invoice is draft after post
                ('draft', 'cancel'),
                ('confirmed', 'cancel'),
                ('failed', 'cancel'),
                ('cancel', 'draft'),
                ))
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
                'do_invoice': {
                    'invisible': ((Eval('state') != 'confirmed')
                        | Eval('invoice')),
                    'icon': 'tryton-ok',
                    },
                'cancel': {
                    'invisible': ~Eval('state').in_(
                            ['draft', 'confirmed', 'failed']),
                    'icon': 'tryton-cancel',
                    },
                'check_trigger': {
                    'readonly': Eval('state').in_(
                            ['draft', 'processing', 'succeded', 'failed',
                            'cancel']),
                    'icon': 'tryton-executable',
                    },

                })
        cls._error_messages.update({
                'reset_milestone_with_invoice': (
                    'You cannot reset to draft the Milestone "%s" because it '
                    'has an invoice. Duplicate it to reinvoice.'),
                })

    @classmethod
    def view_attributes(cls):
        return [
            ('/form//separator[@id="trigger"]', 'states',
                {'invisible': Eval('kind') != 'system'}),
            # ('/form//group[@id=[@id="fixed_amount"]', 'states',
                # {'invisible': Eval('invoice_method') != 'fixed'}),
            ('/form//group[@id="invoice_date_calculator"]', 'states',
                {'invisible': Eval('kind') != 'system'}),
            ]

    @staticmethod
    def default_state():
        return 'draft'

    @fields.depends('project', 'invoice_method')
    def on_change_with_currency(self):
        if self.invoice_method == 'fixed' and self.project:
            return self.project.company.currency.id

    @classmethod
    def set_number(cls, milestones):
        '''
        Fill the number field with the milestone sequence
        '''
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('project.milestone.configuration')

        config = Config(1)
        for milestone in milestones:
            if milestone.number:
                continue
            milestone.number = Sequence.get_id(config.milestone_sequence.id)
        cls.save(milestones)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, milestones):
        for milestone in milestones:
            if milestone.invoice:
                cls.raise_user_error('reset_milestone_with_invoice',
                    (milestone.rec_name,))

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, milestones):
        cls.set_number(milestones)

    @classmethod
    @Workflow.transition('processing')
    def proceed(cls, milestones):
        # TODO: Review
        pool = Pool()
        Date = pool.get('ir.date')
        cls.write(milestones, {
                'processed_date': Date.today(),
                })

    @classmethod
    @Workflow.transition('succeeded')
    def succeed(cls, milestones):
        # TODO: Review
        for milestone in milestones:
            if (milestone.invoice and milestone.invoice.invoice_date
                    and milestone.invoice.invoice_date
                    != milestone.invoice_date):
                milestone.invoice_date = milestone.invoice.invoice_date
                milestone.save()

    @classmethod
    def copy(cls, milestones, default=None):
        if default is None:
            default = {}
        default.setdefault('code', None)
        default.setdefault('processed_date', None)
        default.setdefault('invoice_date', None)
        default.setdefault('invoice', None)
        return super(Milestone, cls).copy(milestones, default)

    @classmethod
    @Workflow.transition('failed')
    def fail(cls, milestones):
        # TODO: Review
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, milestones):
        # TODO
        pass

    @classmethod
    @ModelView.button
    def do_invoice(cls, milestones):
        pool = Pool()
        Date = pool.get('ir.date')
        Invoice = pool.get('account.invoice')

        today = Date.today()
        invoices = []
        proceed = []
        for milestone in milestones:
            if not milestone.invoice_date:
                milestone.invoice_date = milestone._calc_invoice_date()
                milestone.save()
            if(milestone.kind == 'system' and milestone.invoice_date > today):
                continue
            if milestone.invoice:
                proceed.append(milestone)
                continue

            invoice = milestone.create_invoice()
            print "-"*20, invoice.company
            invoice.milestone = milestone
            method = getattr(milestone, 'get_invoice_%s' %
                milestone.invoice_method)
            invoice_lines = method()

            if not invoice_lines:
                continue
            work = milestone.project
            for key, lines in groupby(invoice_lines,
                    key=work._group_lines_to_invoice_key):
                lines = list(lines)
                key = dict(key)
                print "company:", work.company
                invoice_line = work._get_invoice_line(key, invoice, lines)
                invoice_line.party = work.party

                invoice_line.invoice = invoice
                invoice_line.company = work.company
                invoice_line.save()
                origins = {}
                for line in lines:
                    origin = line['origin']
                    origins.setdefault(origin.__class__, []).append(origin)
                for klass, records in origins.iteritems():
                    klass.save(records)  # Store first new origins
                    klass.write(records, {
                            'invoice_line': invoice_line.id,
                            })

            if invoice:
                invoices.append(invoice)
                proceed.append(milestone)
        Invoice.save(invoices)
        Invoice.update_taxes(invoices)
        cls.proceed(proceed)

    def _get_advancement_invoice_line(self):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        if self.state != 'confirmed' or self.invoice_method != 'fixed':
            return

        product = self.advancement_product

        res = {
            'product': product,
            'quantity': 1.0 if self.amount > _ZERO else -1.0,
            'unit': product.default_uom,
            'unit_price': abs(self.amount),
            'origin': '',
            'description': self.calc_invoice_line_description(),
        }
        return res

    def create_invoice(self):
        invoice = self.project._get_invoice()
        if hasattr(self.project.party, 'agent'):
            # Compatibility with commission_party
            invoice.agent = self.project.party.agent
        return invoice

    def get_invoice_fixed(self):
        return [self._get_advancement_invoice_line()]

    def get_invoice_progress(self):
        print "holaaaaaaaaaaaaaaaaaaaaa"
        return self.project.get_lines_to_invoice_progress()




    def get_invoice_reminder(self):
        #TODO: Call the invoice method on the work
        # Add the compensation lines for the advancement amount (if any)
        pass

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

    def calc_invoice_line_description(self):
        return self.description or self.number

    @classmethod
    @ModelView.button
    def check_trigger(cls, milestones):
        res = cls.check_trigger_condition(milestones)
        cls.do_invoice(res)

    def check_trigger_start_project(self):
        if self.project.state == 'opened':
            return True
        return False

    def check_trigger_finish_project(self):
        print "hola:", self.project.state
        if self.project.state == 'done':
            return True
        return False

    def check_trigger_progress(self):
        progress = self.project.total_progress / self.project.total_quantity
        print "progress:", self.progress, progress
        if progress > self.trigger_progress:
            return True
        return False

    @classmethod
    def check_trigger_condition(cls, milestones):
        res = []
        for milestone in milestones:
            if (milestone.state != 'confirmed' or milestone.kind == 'manual' or
                    milestone.invoice):
                continue
            method = getattr(milestone, 'check_trigger_%s'
                    % milestone.trigger)
            print method
            triggered = method()
            if not triggered:
                continue
            res.append(milestone)

        return res
