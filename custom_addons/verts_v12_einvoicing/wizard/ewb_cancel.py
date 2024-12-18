# -*- coding: utf-8 -*-
import json
import requests
from odoo import models, fields, api
from odoo.exceptions import UserError, _logger


class EwbCancel(models.TransientModel):
    _name = 'ewb.cancel.wiz'

    ewb_cancel_remark = fields.Char('EWB Cancellation Remarks', copy=False, required=True)
    ewb_cancellation_reason = fields.Selection(
        [('1', 'Duplicate'), ('2', 'Data Entry Mistake'), ('3', 'Order Cancelled'), ('4', 'Others')],
        string="EWB Cancellation Reason", required=True)

    def cancel_ewb(self):
        self.ensure_one()
        context = dict(self._context or {})
        active_ids = context.get('active_ids', [])
        invoice_id = self.env['account.move'].browse(active_ids)
        invoice_id.update({
            'ewb_cancel_remark': self.ewb_cancel_remark,
            'ewb_cancellation_reason': self.ewb_cancellation_reason,
        })
        invoice_id.cancel_ewb()



class EinvIrnCancel(models.TransientModel):
    _name = 'einv.irn.cancel.wiz'

    einv_cancel_remark = fields.Char('Einv Cancellation Remarks', copy=False, )
    einv_cancellation_reason = fields.Selection([('1', 'Duplicate'), ('2', 'Data Entry Mistake')],
                                                string="Cancellation Reason",)
    cancel_remark = fields.Text('Cancel Remark', required=True)

    def cancel_irn(self):
        self.ensure_one()
        context = dict(self._context or {})
        active_ids = context.get('active_ids', [])
        einv_id = self.env['account.move'].browse(active_ids)
        print('==============================', einv_id)

        einv_id.update({
            'einv_cancel_remark':self.cancel_remark,
            'cancel_remark':self.cancel_remark
        })
        return einv_id.cancel_irn()
