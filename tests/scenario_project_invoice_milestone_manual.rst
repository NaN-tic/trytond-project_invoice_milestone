=============================================
Project Invoice Milestone - Manual Milestones
=============================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
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

.. TODO
.. Create project user::
..
..     >>> project_user = User()
..     >>> project_user.name = 'Project'
..     >>> project_user.login = 'project'
..     >>> project_user.main_company = company
..     >>> project_group, = Group.find([('name', '=', 'Project Administration')])
..     >>> timesheet_group, = Group.find([('name', '=', 'Timesheet Administration')])
..     >>> project_user.groups.extend([project_group, timesheet_group])
..     >>> project_user.save()
..
.. Create project invoice user::
..
..     >>> project_invoice_user = User()
..     >>> project_invoice_user.name = 'Project Invoice'
..     >>> project_invoice_user.login = 'project_invoice'
..     >>> project_invoice_user.main_company = company
..     >>> project_invoice_group, = Group.find([('name', '=', 'Project Invoice')])
..     >>> project_group, = Group.find([('name', '=', 'Project Administration')])
..     >>> project_invoice_user.groups.extend(
..     ...     [project_invoice_group, project_group])
..     >>> project_invoice_user.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']

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

.. Use advancement product for advancement invoices::
..
..     >>> AccountConfiguration = Model.get('account.configuration')
..     >>> milestone_sequence, = Sequence.find([
..     ...     ('code', '=', 'account.invoice.milestone'),
..     ...     ], limit=1)
..     >>> milestone_group_sequence, = Sequence.find([
..     ...     ('code', '=', 'account.invoice.milestone.group'),
..     ...     ], limit=1)
..     >>> account_config = AccountConfiguration(1)
..     >>> account_config.milestone_advancement_product = advancement
..     >>> account_config.milestone_sequence = milestone_sequence
..     >>> account_config.milestone_group_sequence = milestone_group_sequence
..     >>> account_config.save()

.. Create Milestone Group Type::
..
..     >>> MileStoneType = Model.get('account.invoice.milestone.type')
..     >>> MileStoneGroupType = Model.get('account.invoice.milestone.group.type')
..     >>> group_type = MileStoneGroupType(name='Test')
..     >>> fixed_type = group_type.lines.new()
..     >>> fixed_type.kind = 'manual'
..     >>> fixed_type.invoice_method = 'fixed'
..     >>> fixed_type.amount = Decimal('100.0')
..     >>> fixed_type.currency = currency
..     >>> fixed_type.days = 5
..     >>> fixed_type.description = 'Advancement'
..     >>> remainder = group_type.lines.new()
..     >>> remainder.invoice_method = 'remainder'
..     >>> remainder.kind = 'manual'
..     >>> remainder.months = 1
..     >>> remainder.description = 'Once finished'
..     >>> group_type.save()


Manual Amount based Milestones
==============================

One Advancement One Remainder Milestone
---------------------------------------

Create a Project::

..    >>> config.user = project_user.id
    >>> ProjectWork = Model.get('project.work')
    >>> TimesheetWork = Model.get('timesheet.work')
    >>> project = ProjectWork()
    >>> project.name = 'Advancement and Final remainder milestones'
    >>> project.type = 'project'
    >>> project.party = customer
    >>> project.project_invoice_method = 'milestone'
    >>> project.invoice_product_type = 'service'
    >>> project.product = service_product
    >>> project.product_goods = goods_product
    >>> project.effort_duration = datetime.timedelta(hours=1)

    >>> task = ProjectWork()
    >>> task.name = 'Task 1 - Goods'
    >>> task.type = 'task'
    >>> task.invoice_product_type = 'goods'
    >>> task.product_goods = goods_product
    >>> task.quantity = 5.0
    >>> project.children.append(task)
    >>> project.save()
    >>> goods_task = project.children[-1]

    >>> task = ProjectWork()
    >>> task.name = 'Task 2 - Service'
    >>> task.type = 'task'
    >>> task.invoice_product_type = 'service'
    >>> task.product = service_product
    >>> project.effort_duration = datetime.timedelta(hours=10)
    >>> project.children.append(task)
    >>> project.save()
    >>> service_task = project.children[-1]

Create milestone::

    >>> Milestone = Model.get('project.invoice_milestone')
    >>> advancement_milestone = Milestone()
    >>> advancement_milestone.project = project
    >>> advancement_milestone.kind = 'manual'
    >>> advancement_milestone.invoice_method = 'fixed'
    >>> advancement_milestone.advancement_product = advancement_product
    >>> advancement_milestone.advancement_amount = Decimal(1000)
    >>> advancement_milestone.save()

    >>> remainder_milestone = Milestone()
    >>> remainder_milestone.project = project
    >>> remainder_milestone.kind = 'manual'
    >>> remainder_milestone.invoice_method = 'remainder'
    >>> remainder_milestone.save()

.. Increase goods task progress::
..
..     >>> goods_task.progress_quantity = 3.0
..     >>> goods_task.save()

.. Create timesheets::
..
..     >>> TimesheetLine = Model.get('timesheet.line')
..     >>> line = TimesheetLine()
..     >>> line.employee = employee
..     >>> line.duration = datetime.timedelta(hours=3)
..     >>> line.work = task.work
..     >>> line.save()
..     >>> line = TimesheetLine()
..     >>> line.employee = employee
..     >>> line.duration = datetime.timedelta(hours=2)
..     >>> line.work = project.work
..     >>> line.save()

Check project duration::

    >>> project.reload()
    >>> project.invoiced_duration
    datetime.timedelta(0)
    >>> project.duration_to_invoice
    datetime.timedelta(0, 18000)
    >>> project.invoiced_amount
    Decimal('0.00')

Create a Sale with lines with service products and goods products::

    >>> Sale = Model.get('sale.sale')
    >>> SaleLine = Model.get('sale.line')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.milestone_group_type = group_type
    >>> sale.payment_term = payment_term
    >>> consumable_line = sale.lines.new()
    >>> consumable_line.product = consumable
    >>> consumable_line.quantity = 6.0
    >>> consumable_line.amount
    Decimal('180.00')
    >>> goods_line = sale.lines.new()
    >>> goods_line.product = product
    >>> goods_line.quantity = 20.0
    >>> goods_line.amount
    Decimal('200.00')
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')

    >>> group = sale.milestone_group
    >>> group.reload()
    >>> reminder, = [x for x in group.milestones if x.invoice_method == 'remainder']
    >>> fixed_milestone, = [x for x in group.milestones if x.invoice_method == 'amount']
    >>> fixed_milestone.invoice_method
    u'amount'
    >>> fixed_milestone.description
    u'Advancement'
    >>> fixed_milestone.amount
    Decimal('100.00')
    >>> fixed_milestone.click('confirm')
    >>> remainder.description
    'Once finished'
    >>> reminder.click('confirm')
    >>> group.reload()
    >>> group.total_amount
    Decimal('380.00')
    >>> group.amount_to_assign
    Decimal('0.00')
    >>> group.assigned_amount
    Decimal('380.00')
    >>> group.invoiced_amount
    Decimal('0.00')
    >>> group.merited_amount
    Decimal('0.00')
    >>> group.state
    'pending'

Create a Invoice for the milestone::

    >>> fixed_milestone.click('do_invoice')
    >>> fixed_milestone.state
    u'processing'
    >>> invoice = fixed_milestone.invoice
    >>> invoice.untaxed_amount
    Decimal('100.00')
    >>> invoice_line, = invoice.lines
    >>> invoice_line.description
    u'Advancement'
    >>> group.reload()
    >>> group.invoiced_amount
    Decimal('100.00')
    >>> group.merited_amount
    Decimal('0.00')
    >>> group.state
    'pending'

Test that invoice_amount can not be modified::

    >>> invoice_line, = invoice.lines
    >>> invoice_line.unit_price = Decimal('110.0')
    >>> invoice.save()
    Traceback (most recent call last):
        ...
    UserError: ('UserError', (u'Amount of invoice "1 Customer" must be equal than its milestone "1" amount', ''))
    >>> invoice.reload()

Pay the invoice and check that the milestone is marked as succeeded::

    >>> invoice.click('post')
    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.journal = cash_journal
    >>> pay.execute('choice')
    >>> invoice.reload()
    >>> invoice.state
    u'paid'
    >>> fixed_milestone.reload()
    >>> fixed_milestone.state
    u'succeeded'
