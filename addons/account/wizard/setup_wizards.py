# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class FinancialYearOpeningWizard(models.TransientModel):
    _name = 'account.financial.year.op'

    company_id = fields.Many2one(comodel_name='res.company', required=True)
    opening_move_posted = fields.Boolean(string='Opening Move Posted', compute='_compute_opening_move_posted')
    opening_date = fields.Date(string='Opening Date', required=True, related='company_id.account_opening_date', help="Date from which the accounting is managed in Odoo. It is the date of the opening entry.")
    fiscalyear_last_day = fields.Integer(related="company_id.fiscalyear_last_day", required=True,
                                         help="The last day of the month will be taken if the chosen day doesn't exist.")
    fiscalyear_last_month = fields.Selection(selection=[(1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'), (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'), (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')],
                                             related="company_id.fiscalyear_last_month",
                                             required=True,
                                             help="The last day of the month will be taken if the chosen day doesn't exist.")
    account_setup_fy_data_done = fields.Boolean(string='Financial year setup marked as done', compute="_compute_setup_marked_done")

    @api.depends('company_id.account_setup_fy_data_done')
    def _compute_setup_marked_done(self):
        for record in self:
            record.account_setup_fy_data_done = record.company_id.account_setup_fy_data_done

    @api.depends('company_id.account_opening_move_id')
    def _compute_opening_move_posted(self):
        for record in self:
            record.opening_move_posted = record.company_id.opening_move_posted()

    @api.multi
    def write(self, vals):
        if 'fiscalyear_last_day' in vals or 'fiscalyear_last_month' in vals:
            for wizard in self:
                company = wizard.company_id
                vals['fiscalyear_last_day'] = company._verify_fiscalyear_last_day(
                    company.id,
                    vals.get('fiscalyear_last_day'),
                    vals.get('fiscalyear_last_month'))
        return super(FinancialYearOpeningWizard, self).write(vals)

    @api.multi
    def action_save_onboarding_fiscal_year(self):
        self.env.user.company_id.account_setup_fy_data_done = True


class SetupBarBankConfigWizard(models.TransientModel):
    _inherits = {'res.partner.bank': 'res_partner_bank_id'}
    _name = 'account.setup.bank.manual.config'

    create_or_link_option = fields.Selection(selection=[('new', 'Create new journal'), ('link', 'Link to an existing journal')], default='new')
    new_journal_name = fields.Char(compute='compute_new_journal_related_data', inverse='set_linked_journal_id', required=True, help='Will be used to name the Journal related to this bank account')
    linked_journal_id = fields.Many2one(string="Journal", comodel_name='account.journal', compute='compute_linked_journal_id', inverse='set_linked_journal_id')
    new_journal_code = fields.Char(string="Code", required=True, default=lambda self: self.env['account.journal'].get_next_bank_cash_default_code('bank', self.env['res.company']._company_default_get('account.journal').id))

    # field computing the type of the res.patrner.bank. It's behaves the same as a related res_part_bank_id.acc_type
    # except we want to display  this information while the record isn't yet saved.
    related_acc_type = fields.Selection(string="Account Type", selection=lambda x: x.env['res.partner.bank'].get_supported_account_types(), compute='_compute_related_acc_type')

    @api.depends('acc_number')
    def _compute_related_acc_type(self):
        for record in self:
            record.related_acc_type = self.env['res.partner.bank'].retrieve_acc_type(record.acc_number)

    @api.model
    def create(self, vals):
        """ This wizard is only used to setup an account for the current active
        company, so we always inject the corresponding partner when creating
        the model.
        """
        vals['partner_id'] = self.env.user.company_id.partner_id.id
        return super(SetupBarBankConfigWizard, self).create(vals)

    @api.depends('linked_journal_id')
    def compute_new_journal_related_data(self):
        for record in self:
            if record.linked_journal_id:
                record.new_journal_name = record.linked_journal_id.name

    @api.depends('journal_id')  # Despite its name, journal_id is actually a One2many field
    def compute_linked_journal_id(self):
        for record in self:
            record.linked_journal_id = record.journal_id and record.journal_id[0] or None

    def set_linked_journal_id(self):
        """ Called when saving the wizard.
        """
        for record in self:
            selected_journal = record.linked_journal_id
            if record.create_or_link_option == 'new':
                company = self.env['res.company']._company_default_get('account.journal')
                selected_journal = self.env['account.journal'].create({
                    'name': record.new_journal_name,
                    'code': record.new_journal_code,
                    'type': 'bank',
                    'company_id': company.id,
                    'bank_account_id': record.res_partner_bank_id.id,
                })
            else:
                selected_journal.bank_account_id = record.res_partner_bank_id.id

    def validate(self):
        """ Called by the validation button of this wizard. Serves as an
        extension hook in account_bank_statement_import.
        """
        pass
