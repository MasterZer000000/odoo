# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import odoo.addons.decimal_precision as dp
import requests
import json
import base64

class GSTroboAPI(models.Model):
    _name = 'gstrobo.apiconfig'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']

    name = fields.Char('TIN Number',required=True,track_visibility='onchange', copy=False)
    gstrobo_user = fields.Char('User Name',track_visibility='onchange', copy=False)
    gstrobo_pwd = fields.Char('Password',track_visibility='onchange', copy=False)
    client_id = fields.Char('ClientID',track_visibility='onchange', copy=False)
    client_secret = fields.Char('Client Secret',track_visibility='onchange', copy=False)
    pvt_key = fields.Char('PRIVATEKEY',track_visibility='onchange', copy=False)
    pvt_value = fields.Char('PRIVATEVALUE',track_visibility='onchange', copy=False)
    whitelisted_ip = fields.Char('Whitelisted IP')
    client_ip = fields.Char('Client IP')
    auth_url = fields.Char('Authentication URL')
    einvoice_url = fields.Char('EInvoice URL')
    ewb_url = fields.Char('Ewaybill URL')
    company_id = fields.Many2one('res.company', string='Company', change_default=True,
        required=True, default=lambda self: self.env['res.company']._company_default_get('account.move'))
    notes = fields.Text('Notes')
    state = fields.Selection([
            ('draft','New'),
            ('auth', 'Authenticated'),
            ('expired', 'Expired'),
        ], string='Status', readonly=True, default='draft',track_visibility='onchange',copy=False)
    token_expiry = fields.Char("Expiry Date")
    inv_ids = fields.One2many('account.move','einvoice_api', string="Invoices")
    token_no = fields.Text('Token')
    token_no_expiry = fields.Text('Token Expiry Date')

    _sql_constraints = [
        ('api_gstin_unique', 'UNIQUE (name)', 'GSTIN must be unique.'),
    ]
    
    def set_to_draft(self):
        return self.write({'state':'draft'})
    
    def unlink(self):
        for api in self:
            if self.inv_ids:
                raise UserError(_('You cannot delete this API Record because invoices are already associated.'))
        return super(GSTroboAPI, self).unlink()
    
    def authenticate(self):
        url = self.auth_url
        
        # Adding empty header as parameters are being sent in payload
        payload = {
            "grantType": "client_credentials",
            "mysClientId": self.client_id or '',
            "mysClientSecret": self.client_secret or '',
            "scope": "InvoicingAPI",
            "password": "Default@123",
            }


        headers = {
            "Accept": "application/json",
            "client-id": self.client_id or '',
            "client-secret": self.client_secret or '',
            "User-name": self.gstrobo_user or '',
            "Tin-no": self.name or '',
            "Setting-Configured": "false",
            "Content-Type": "application/json;charset=utf-8"
          }
        print("APAYLOALHDHSHHSSSSSSSSSSSS",payload,headers)
        try:
            r = requests.post(url, data=json.dumps(payload), headers=headers)
            _logger.info("Auth API Response : %s " % str(r.content))
    #         self.notes  = r.content
            j = json.loads(r.text)
        except Exception as e:
            msg = "API Error: %s" %e
            raise UserError(msg)
        print("CHHHHHJJJJJJJJJJJJJJJJJJK",j,r)
        status_code = j.get('MessageId')
        message = j.get('Message')
        print(status_code)
        self.notes = message
        if not status_code:
            self.state = 'auth'
            self.token_expiry = j.get('data',{}).get('TokenExpiry')
            self.token_no = j.get('data',{}).get('authToken')
            self.token_no_expiry = j.get('data',{}).get('expiryDate')
        else:
            self.state = 'expired'
            self.token_expiry = False
        return True
    
    
    def upload_einvoice(self):
        # Adding empty header as parameters are being sent in payload
        headers = {
            "Accept": "application/json",
            "client_id": self.client_id or '',
            "client_secret": self.client_secret or '',
            "IPAddress": self.whitelisted_ip or '',
            "Content-Type": "application/json;charset=utf-8"
          }
        
        invoices = self.env['account.move'].search([('type','in',('out_invoice','out_refund')),('company_id','=',self.company_id.id),
                                                        ('is_einvoice','=',False),('state','in',('open','paid'))])
        
        for inv in invoices:
            vals = inv._prepare_einvoice_json()
            print(json.dumps(vals))
    
            headers.update({'user_name':self.gstrobo_user or '',"Gstin": self.name or '',})
            try:
                r = requests.post(self.einvoice_url, data=json.dumps(vals), headers=headers)
                _logger.info("IRN API Response : %s " % str(r.content))
                j = json.loads(r.text)
            except Exception as e:
                msg = "API Error: %s" %e
                raise UserError(msg)
            status_code = j.get('MessageId')
            message = j.get('Message')
            rdata = j.get('Data',{})
            if status_code==1:
                inv.write({
                        'is_einvoice':True,
                        'einvoice_irn':rdata.get('Irn'),
                        'einvoice_api':self.id,
                        'einv_ack':rdata.get('AckNo'),
                        'einv_date':rdata.get('AckDt'),
                        'einv_signedinvoice':rdata.get('SignedInvoice'),
                        'einv_signed_qrcode':rdata.get('SignedQRCode'),
                        'einv_base64_qrcode':rdata.get('Base64QRCode'),
                        'einvoice_message':message,
                        'einv_qrcode_name':str(inv.number) + '_QRcode.png',
                    })
            if status_code==0:
                inv.write({
                        'is_einvoice':False,
                        'einvoice_api':self.id,
                        'einvoice_message':message,
                    })
            elif status_code==1005:
                self.state = 'expired'
                self.token_expiry = False
                self.authenticate()
                self.upload_einvoice()
                return True
        return self._get_inv_action(domain=[('id', 'in', invoices.ids)])        

    
    def _get_inv_action(self,domain=[]):
        view_id = self.env.ref('verts_v12_einvoicing.view_einvoice_api_tree').id
        form_view_id = self.env.ref('verts_v12_einvoicing.view_einvoice_api_form').id
        if self.env.context.get('failed_inv'):
            view_id = self.env.ref('verts_v12_einvoicing.view_failed_einvoice_api_tree').id
        return {
            'name': _('E-Invoices Status'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': view_id,
            'views': [(view_id, 'tree'), (form_view_id, 'form')],
            'type': 'ir.actions.act_window',
            'domain': domain,
        }
    
    def button_open_einvoices(self):
        return self._get_inv_action(domain=[('einvoice_api', 'in', self.ids),('is_einvoice','=',True)])
        
    def button_failed_einvoices(self):
        return self.with_context(failed_inv=True)._get_inv_action(domain=[('einvoice_api', 'in', self.ids),('is_einvoice','=',False)])
    