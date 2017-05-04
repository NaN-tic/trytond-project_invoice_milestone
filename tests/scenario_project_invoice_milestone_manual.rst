=============================================
Project Invoice Milestone - Manual Milestones
=============================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install project_invoice_milestone::

    >>> Module = Model.get('ir.module')
    >>> module, = Module.find([
    ...         ('name', '=', 'project_invoice_milestone'),
    ...     ])
    >>> module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.customer_payment_term = payment_term
    >>> customer.save()

Create employee::

    >>> Employee = Model.get('company.employee')
    >>> employee = Employee()
    >>> party = Party(name='Employee')
    >>> party.save()
    >>> employee.party = party
    >>> employee.company = company
    >>> employee.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> hour, = ProductUom.find([('name', '=', 'Hour')])
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> Product = Model.get('product.product')
    >>> ProductTemplate = Model.get('product.template')
    >>> template = ProductTemplate()
    >>> template.name = 'Service'
    >>> template.default_uom = hour
    >>> template.type = 'service'
    >>> template.list_price = Decimal('20')
    >>> template.cost_price = Decimal('5')
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> service_product, = template.products

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('40')
    >>> template.cost_price = Decimal('15')
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> goods_product, = template.products

    >>> template = ProductTemplate()
    >>> template.name = 'Advancement'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('0')
    >>> template.cost_price = Decimal('0')
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> advancement_product, = template.products

Use advancement product for advancement invoices::

    >>> Sequence = Model.get('ir.sequence')
    >>> AccountConfiguration = Model.get('project.invoice_milestone.configuration')
    >>> milestone_sequence, = Sequence.find([
    ...     ('code', '=', 'project.invoice_milestone'),
    ...     ], limit=1)
    >>> account_config = AccountConfiguration(1)
    >>> account_config.advancement_product = advancement_product
    >>> account_config.compensation_product = advancement_product
    >>> account_config.milestone_sequence = milestone_sequence
    >>> account_config.save()

Create Milestone Group Type::

    >>> MileStoneType = Model.get('project.invoice_milestone.type')
    >>> MileStoneGroupType = Model.get('project.invoice_milestone.type.group')
    >>> group_type = MileStoneGroupType(name='Test')
    >>> fixed_type = group_type.lines.new()
    >>> fixed_type.kind = 'system'
    >>> fixed_type.invoice_method = 'fixed'
    >>> fixed_type.advancement_amount = Decimal('100.0')
    >>> fixed_type.currency = get_currency('EUR')
    >>> fixed_type.days = 0
    >>> fixed_type.description = 'Advancement'
    >>> fixed_type.trigger = 'start_project'
    >>> remainder = group_type.lines.new()
    >>> remainder.invoice_method = 'remainder'
    >>> remainder.kind = 'system'
    >>> remainder.trigger = 'finish_project'
    >>> remainder.months = 0
    >>> remainder.description = 'Once finished'
    >>> group_type.save()

System Amount based Milestones
==============================

One Advancement One Remainder Milestone
---------------------------------------

Create a Project::

    >>> ProjectWork = Model.get('project.work')
    >>> TimesheetWork = Model.get('timesheet.work')
    >>> time_work = TimesheetWork()
    >>> time_work.name = 'Task 2 - Service'
    >>> time_work.company = company
    >>> time_work.save()

    >>> project = ProjectWork()
    >>> project.name = 'Advancement and Final remainder milestones'
    >>> project.type = 'project'
    >>> project.party = customer
    >>> project.project_invoice_method = 'milestone'
    >>> project.invoice_product_type = 'goods'
    >>> project.milestone_group_type = group_type
    >>> project.progress_quantity = 0.0
    >>> project.product_goods = goods_product
    >>> project.save()
    >>> project.reload()

    >>> task = ProjectWork()
    >>> task.name = 'Task 1 - Goods'
    >>> task.type = 'task'
    >>> task.invoice_product_type = 'goods'
    >>> task.product_goods = goods_product
    >>> task.quantity = 5.0
    >>> task.progress_quantity = 0.0
    >>> project.children.append(task)
    >>> project.save()
    >>> goods_task = project.children[-1]

    >>> task = ProjectWork()
    >>> task.name = 'Task 2 - Service'
    >>> task.work = time_work
    >>> task.type = 'task'
    >>> task.invoice_product_type = 'service'
    >>> task.product = service_product
    >>> task.effort_duration = datetime.timedelta(hours=10)
    >>> project.children.append(task)
    >>> project.save()
    >>> service_task = project.children[-1]

Assign MilestoneGroup::

    >>> project.milestone_group_type
    proteus.Model.get('project.invoice_milestone.type.group')(1)
    >>> project.click('create_milestone')
    >>> project.reload()
    >>> len(project.milestones)
    2

Confirm Milestones::
    >>> for milestone in project.milestones:
    ...     milestone.click('confirm')

Start Project::

    >>> project.click('open')
    >>> project.reload()
    >>> project.state
    u'opened'

Check Fixed Amount Milestone::

    >>> fixed_milestone = project.milestones[0]
    >>> fixed_milestone.state
    u'invoiced'
    >>> fixed_milestone.invoice.untaxed_amount
    Decimal('100.00')
    >>> fixed_milestone.invoice.click('post')

Finish Project::

    >>> for task in project.children:
    ...     task.click('done')
    >>> project.click('done')
    >>> project.reload()
    >>> project.state
    u'done'

Check Reminder Project::

    >>> reminder_milestone = project.milestones[-1]
    >>> reminder_milestone.state
    u'invoiced'
    >>> reminder_milestone.invoice.untaxed_amount
    Decimal('340.00')
    >>> project.cost
    Decimal('0.00')
    >>> project.revenue
    Decimal('200.00000')
    >>> project.invoiced_amount
    Decimal('440.00')
    >>> reminder_milestone.invoice.click('post')
    >>> invoice = reminder_milestone.invoice
    >>> invoice.untaxed_amount
    Decimal('340.00')

Make a credit::

    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.form.with_refund = True
    >>> credit.execute('credit')
    >>> project.reload()
    >>> project.invoiced_amount
    Decimal('0.00')
