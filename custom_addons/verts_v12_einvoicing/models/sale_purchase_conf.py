# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)
import time
import datetime
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import odoo.addons.decimal_precision as dp
import requests
import json
import base64


class GstSalePurchaseConf(models.Model):
    _name = 'gst.sale.purchase'
    _description = 'GST Sale Purchase Conf'

    name = fields.Char('GSTIN',required=True,track_visibility='onchange', copy=False)
    gstrobo_user = fields.Char('GSTrobo User',track_visibility='onchange', copy=False)
    client_id = fields.Char('ClientID', track_visibility='onchange', copy=False)
    client_secret = fields.Char('Client Secret', track_visibility='onchange', copy=False)
    whitelisted_ip = fields.Char('Whitelisted IP')
    auth_url = fields.Char('Authentication URL')
    invoice_url = fields.Char('Invoice URL')
    token_expiry = fields.Char("Expiry Date")
    auth_token = fields.Char('Auth Token')
    notes = fields.Text('Notes')
    state = fields.Selection([
            ('draft','New'),
            ('auth', 'Authenticated'),
            ('expired', 'Expired'),
        ], string='Status', readonly=True, default='draft',track_visibility='onchange',copy=False)
    company_id = fields.Many2one('res.company', string='Company', change_default=True,
        required=True, default=lambda self: self.env['res.company']._company_default_get('account.move'))

    _sql_constraints = [
        ('api_gstin_sale_purchase_unique', 'UNIQUE (name)', 'GSTIN must be unique.'),
    ]

    def set_to_draft(self):
        return self.write({'state':'draft'})

    def authenticate(self):
        url = self.auth_url

        # Adding empty header as parameters are being sent in payload
        payload = {
            "action": "INITAUTH",
            "UserName": self.gstrobo_user or '',
            "GstinNo": self.name or '',
            }
        current_date = (fields.datetime.now() + datetime.timedelta(hours=5, minutes=30))
        current_date1 = current_date.strftime("%Y-%m-%d %H:%M:%S")
        headers = {
            "Accept": "application/json",
            "ClientId": self.client_id or '',
            "ClientSecret": self.client_secret or '',
            "IP": self.whitelisted_ip or '',
            "AuthDateTime": current_date1 or '',
            "Content-Type": "application/json;charset=utf-8"
        }
        try:
            r = requests.post(url, data=json.dumps(payload), headers=headers)
            _logger.info("Auth API Response : %s " % str(r.content))
            #         self.notes  = r.content
            j = json.loads(r.text)
        except Exception as e:
            msg = "API Error: %s" % e
            raise UserError(msg)
        status_code = j.get('MessageId')
        message = j.get('Message')
        self.notes = message
        if status_code == 1:
            self.state = 'auth'
            self.token_expiry = j.get('Data', {}).get('ExpiryDatetime')
            self.auth_token = j.get('Data', {}).get('AuthToken')
        else:
            self.state = 'expired'
            self.token_expiry = False
        return True