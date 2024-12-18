# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import odoo.addons.decimal_precision as dp
import requests
import json
import base64
from datetime import datetime

class AccountInvoice(models.Model):
    _inherit = 'account.move'
    
    is_einvoice = fields.Boolean('Einvoice Uploaded', copy=False)
    einvoice_irn = fields.Char('Einvoice IRN', copy=False)
    einvoice_message = fields.Text('Message', copy=False)
    
    
    einvoice_api = fields.Many2one('gstrobo.apiconfig',string="E-Invoice API Config", copy=False)
    einv_ack = fields.Char('Einvoice Acknowledgement No', copy=False)
    einv_date = fields.Char('Einvoice Acknowledgement Date', copy=False)
    einv_signedinvoice = fields.Char('Signed EInvoice', copy=False)
    einv_signed_qrcode = fields.Char('Signed QRCode', copy=False)
    einv_base64_qrcode = fields.Binary('Base64 QRCode', copy=False)
    einv_qrcode_name = fields.Char('FileName', copy=False)
    einv_cancel_remark = fields.Char('Cancellation Remarks', copy=False)
    einv_cancel_remark_bool = fields.Boolean('Boolean')
    einv_cancel_date = fields.Char('Cancel Date', copy=False)
    einv_cancelled = fields.Boolean("Einvoice Cancelled", copy=False)
    einv_cancellation_reason=fields.Selection([('1','Duplicate'),('2','Data Entry Mistake')],string="Cancellation Reason")
    #Ewaybill
    einv_eway_bill= fields.Char('EwayBill No', copy=False)
    ewb_date = fields.Char('Ewaybill Date', copy=False)
    ewb_valid = fields.Char('Ewaybill Date', copy=False)
    ewb_cancel_remark = fields.Char('EWB Cancellation Remarks', copy=False)
    ewb_cancel_reason_bool = fields.Boolean('Boolean')
    ewb_cancel_date = fields.Char('EWB Cancel Date', copy=False)
    ewb_cancellation_reason=fields.Selection([('1','Duplicate'),('2','Data Entry Mistake'),('3','Order Cancelled'),('4','Others')],string="EWB Cancellation Reason")
    ewb_cancelled = fields.Boolean("Is EWaybill Cancelled", copy=False)
    ewb_message = fields.Text('Message', copy=False)
    is_export = fields.Boolean(string="Is Export Invoice")
    bool_updated_data =fields.Boolean('Bool For Ewaybill Data Updated')
    gst_sale_status = fields.Char('GST Sale API Status')
    gst_purchase_status = fields.Char('GST Purchase API Status')
    api_remark = fields.Text('Remark')
    number = fields.Char('Number')
    date_invoice = fields.Date('Date')
    gst_invoice_type = fields.Selection([
        ('Regular', 'Regular'),
        ('SEZ supplies with payment', 'SEZ supplies with payment'),
        ('SEZ supplies without payment', 'SEZ supplies without payment'),
        ('Deemed Exp', 'Deemed Exp'), ('EXPWP', 'EXPWP - Export with payment'),
        ('EXPWOP', 'EXPWOP - Export without payment')
    ],
        copy=False,
        string='GST Invoice Type',
        default='Regular'
    )

    invoice_type = fields.Selection([
        ('b2b', 'B2B'),
        ('b2cl', 'B2CL'),
        ('b2cs', 'B2CS'),
        ('b2bur', 'B2BUR'),
        ('import', 'IMPS/IMPG'),
        ('export', 'Export')
    ],
        copy=False,
        string='Invoice Type'
    )
    type = fields.Selection([
        ('sale', 'Sale'),
        ('purchase', 'Purchase'),
        ('cash', 'Cash'),
        ('bank', 'Bank'),
        ('general', 'Miscellaneous'),
    ], required=True,
        help="Select 'Sale' for customer invoices journals.\n" \
             "Select 'Purchase' for vendor bills journals.\n" \
             "Select 'Cash' or 'Bank' for journals that are used in customer or vendor payments.\n" \
             "Select 'General' for miscellaneous operations journals.")
    reverse_charge = fields.Boolean(
        string='Reverse Charge',
        help="Allow reverse charges for b2b invoices")
    submission_uid = fields.Text("Submission Uid")
    uuid = fields.Text("UUid")

    transporeter_line = fields.One2many('transporeter.lines', 'transporter_mode_id_grn', 'Transport Line')
    reason_not_accepted = fields.Text("Einvoice Rejection")
    cancel_remark = fields.Text('Cancel Remark', required=True)

    def show_popup(self, message=''):
        if message == '':
            message = "Invoice Submitted Successfully!"
        message_id = self.env['api.message.wizard'].create({'message': _(message)})
        return {
            'name': _('Message'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'api.message.wizard',
            # pass the id
            'res_id': message_id.id,
            'target': 'new'
        }
    
    def action_invoice_cancel(self):
        if not self._context.get('irn_cancel') and self.is_einvoice:
            raise UserError(_("IRN has been generated already, Please cancel IRN first to cancel it."))
        return super(AccountInvoice, self).action_invoice_cancel()
    
    def cancel_ewb(self):
        if not self.ewb_cancel_remark:
            raise UserError(_("Please enter EWB Cancellation Remarks"))
        if not self.ewb_cancellation_reason:
            raise UserError(_("Please enter EWB Cancellation Reason"))
        reason = {'1':'Duplicate','2':'Data Entry Mistake','3':'Order Cancelled','4':'Others'}
        einvoice_api = self.einvoice_api
        val = reason[self.ewb_cancellation_reason]
        payload = {
                    "action": "CANCEL",
                    "data":
                    [
                        {
                            "Generator_Gstin": self.company_id.vat or '',
                            "EwbNo": self.einv_eway_bill,
                            "CancelReason": val,
                            "cancelRmrk": self.ewb_cancel_remark,
                        }
                    ]
                }

        headers = {
            "Accept": "application/json",
            "PRIVATEKEY": einvoice_api.pvt_key or '',
            "PRIVATEVALUE": einvoice_api.pvt_value or '',
            "IP": einvoice_api.client_ip or '',
            "Content-Type": "application/json;charset=utf-8"
        }
        # headers.update({'user_name':einvoice_api.gstrobo_user or '',"Gstin": self.company_id.vat or '',})
        print(json.dumps(payload), "this is reponse")
        try:
            r = requests.post(einvoice_api.ewb_url, data=json.dumps(payload), headers=headers)
            _logger.info("EWB Cancel API Response : %s " % str(r.content))
            j = json.loads(r.text)

        except Exception as e:
            msg = "API Error: %s" %e
            raise UserError(msg)
        status_code = j.get('MessageId')
        message = j.get('Message')
        rdata = j.get('Data',{})
        if status_code == 0:
            raise UserError(message)
        if status_code == 1:
            for ewbdata in rdata:
                if ewbdata.get('Status') == 'Success':
                    self.write({'ewb_cancel_date': ewbdata.get('CancelDate'), 'ewb_cancelled': True})
                    return self.show_popup(message="EWB is cancelled Successfully.")
                else:
                    self.write({
                        'ewb_cancel_remark': '',
                        'ewb_cancellation_reason': '',
                    })
        elif status_code == 1005:
            einvoice_api.state = 'expired'
            einvoice_api.token_expiry = False
            einvoice_api.authenticate()
            self.cancel_ewb()
        return True
    
    
    def cancel_irn(self):
        if not self.einv_cancel_remark:
            raise UserError(_("Please enter Cancellation Remarks"))
        # if not self.einv_cancellation_reason:
        #     raise UserError(_("Please enter Cancellation Reason"))
        # self.with_context(irn_cancel=True).action_invoice_cancel()
        einvoice_api = self.env['gstrobo.apiconfig'].search([], order='id desc', limit=1)


        # einvoice_api = self.einvoice_api
        authon_date = datetime.strptime(einvoice_api.token_no_expiry, '%d-%b-%Y %I:%M %p')
        authonticate_date = datetime.strptime(authon_date.strftime('%d-%m-%Y %H:%M'), "%d-%m-%Y %H:%M")
        if authonticate_date <= datetime.now():
            einvoice_api.authenticate()
        payload = {
            "uuid": self.uuid,
            "status": "cancelled",
            "reason": self.einv_cancel_remark
        }
        print("PAYload",payload)

        headers = {
            "Accept": "application/json",
            "client-id": einvoice_api.client_id or '',
            "client-secret": einvoice_api.client_secret or '',
            "user-name": einvoice_api.gstrobo_user or '',
            "authtoken": einvoice_api.token_no or '',
            "Tin-no": einvoice_api.name or '',
            "Content-Type": "application/json;charset=utf-8"
        }
        print("HEADESRS",headers)
        # headers.update({'user_name':einvoice_api.gstrobo_user or '',"Gstin": einvoice_api.name or '',})
        cancel_url = "http://182.76.79.246:6001/TpApi/MYS/CancelDocument"
        try:
            r = requests.put(cancel_url, data=json.dumps(payload), headers=headers)
            _logger.info("IRN API Response : %s " % str(r.content))
            j = json.loads(r.text)
        except Exception as e:
            msg = "API Error: %s" %e
            raise UserError(msg)
        print("JJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJ",j)
        if self.einv_cancelled:
            msg = "The document is already cancelled."
            self.show_popup(message=msg)
        elif j.get('status')== "Cancelled":
            msg = "Cancelled"
            self.einv_cancelled = True
            self.einv_cancel_date = datetime.now().strftime('%d-%m-%Y %H:%M')
            self.show_popup(message=msg)

        # self.cancel_irn()
        return True
    
    def action_e_invoice_wizard_open(self):
        view_id = self.env.ref('verts_v12_einvoicing.wizard_eway_bill_view').id
        # return True
        return {
            'name': _('E-Invoice'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'eway.bill.wiz',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
        }
    def get_einv_bydoc(self,einvoice_api=False):
        return self.get_einv_byref(einvoice_api=einvoice_api,type='doc')
    
    def get_einv_byirn(self,einvoice_api=False):
        return self.get_einv_byref(einvoice_api=einvoice_api,type='irn')
    
    def get_einv_byref(self,einvoice_api=False,type='doc'):
        if not einvoice_api:
            raise UserError("Please provide E-Invoice API")
        headers = {
            "Accept": "application/json",
            "client_id": einvoice_api.client_id or '',
            "client_secret": einvoice_api.client_secret or '',
            "IPAddress": einvoice_api.whitelisted_ip or '',
            "Content-Type": "application/json;charset=utf-8"
          }
        some_uploaded = False
        
        etyps = {'Regular':'B2B','SEZ supplies with payment':'SEZWP','SEZ supplies without payment':'SEZWOP',
                'Deemed Exp':'DEXP','EXPWP':'EXPWP','EXPWOP':'EXPWOP'}
        message = ''
        for inv in self:
            print("COde check testing this data ",inv)
            vals={}
            if type=='doc':
                vals = {
                    "ACTION": "INVOICEDTLS",
                    "DocNo":inv.number,
                    "DocDate":inv.invoice_date.strftime("%d/%m/%Y"),
                    "TYP":self.gst_invoice_type and etyps.get(self.gst_invoice_type,"B2B") or "B2B",
                    }
            elif  type=='irn':
                if not inv.einvoice_irn:
                    if some_uploaded: continue
                    raise UserError("IRN is not generated for invoice " + str(inv.number))
                    
                vals = {
                        "action": "GETDETAILS",
                        "IRN": inv.einvoice_irn
                        }
            print(json.dumps(vals))
    
            headers.update({'user_name':einvoice_api.gstrobo_user or '',"Gstin": einvoice_api.name or '',})
            try:
                r = requests.post(einvoice_api.einvoice_url, data=json.dumps(vals), headers=headers)
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
                        'einvoice_api':einvoice_api.id,
                        'einv_ack':rdata.get('AckNo'),
                        'einv_date':rdata.get('AckDt'),
                        'einv_signedinvoice':rdata.get('SignedInvoice'),
                        'einv_signed_qrcode':rdata.get('SignedQRCode'),
                        'einv_base64_qrcode':rdata.get('Base64QRCode'),
                        'einvoice_message':message,
                        'einv_qrcode_name':str(inv.number) + '_QRcode.png',
                    })
                some_uploaded = True
            if status_code==0:
                if some_uploaded:
                    inv.write({
                            'is_einvoice':False,
                            'einvoice_api':einvoice_api.id,
                            'einvoice_message':message,
                        })
                    continue
                raise UserError(message)
            elif status_code==1005:
                einvoice_api.state = 'expired'
                einvoice_api.token_expiry = False
                einvoice_api.authenticate()
                inv.get_einv_byref(einvoice_api=einvoice_api,type=type)
        return True

    def generatejsonAttachment(self, jsonData, jsonFileName):
        jsonAttachment = False
        if jsonData:
            jsonData = json.dumps(jsonData, indent=4, sort_keys=False)
            base64Data = base64.b64encode(jsonData.encode('utf-8'))
            try:
                ewaydata = {
                    'datas': base64Data,
                    'type': 'binary',
                    'res_model': 'sale.order',
                    'db_datas': jsonFileName,
                    'datas_fname': jsonFileName,
                    'name': jsonFileName
                }
                jsonObjs = self.env['ir.attachment'].search([('name', '=', jsonFileName)])
                if jsonObjs:
                    jsonAttachment = jsonObjs[0]
                    jsonAttachment.write(ewaydata)
                else:
                    jsonAttachment = self.env['ir.attachment'].create(ewaydata)
            except ValueError:
                pass
        return jsonAttachment

    def getAccountInvoiceLineJson(self):
        itemList = []
        itemNo = 1
        sgstRateAmount, igstRateAmount = 0.0, 0.0
        for lineObj in self.invoice_line_ids:
            productObj = lineObj.product_id
            productName = ''
            if productObj:
                variable_attributes = productObj.attribute_line_ids.filtered(lambda l: len(l.value_ids) > 0).mapped(
                    'attribute_id')
                variant = productObj.attribute_value_ids._variant_name(variable_attributes)

                productName = variant and "%s (%s)" % (productObj.name, variant) or productObj.name
                if productObj.default_code:
                    productName = '[%s] %s' % (productObj.default_code, productName)

            taxedAmount = lineObj.price_tax
            uqc = 'OTH'
            if lineObj.uom_id:
                uom = lineObj.uom_id.id
                uqcObj = self.env['ewaybill.uqc'].search([('uom', '=', uom)])
                if uqcObj:
                    uqc = uqcObj[0].code
            hsnCode = productObj.l10n_in_hsn_code or 0
            if hsnCode and len(hsnCode) > 4:
                hsnCode = hsnCode[0:4]
            # hsnCode = int(hsnCode)
            hsnCode = hsnCode
            itemDict = {
                'itemNo': itemNo,
                'productName': productName,
                'productDesc': productName,
                'hsnCode': hsnCode,
                'quantity': lineObj.quantity,
                'qtyUnit': uqc,
                'taxableAmount': lineObj.price_subtotal,
                'sgstRate': 0,
                'cgstRate': 0,
                'igstRate': 0,
                'cessRate': 0,
                'cessNonAdvol': 0,
            }
            if lineObj.invoice_line_tax_ids:
                for rateObj in lineObj.invoice_line_tax_ids:
                    if rateObj.amount_type == "group":
                        for childObj in rateObj.children_tax_ids:
                            itemDict['sgstRate'] = childObj.amount
                            itemDict['cgstRate'] = childObj.amount
                            sgstRateAmount = sgstRateAmount + taxedAmount / 2
                            break
                    else:
                        itemDict['igstRate'] = rateObj.amount
                        igstRateAmount = igstRateAmount + taxedAmount
                    break
            itemList.append(itemDict)
            itemNo = itemNo + 1
        sgstRateAmount = round(sgstRateAmount, 2)
        igstRateAmount = round(igstRateAmount, 2)
        return [sgstRateAmount, igstRateAmount, itemList]
    def generateJson(self):
        transport_mode = 0
        date_invoice = ''
        bill_date = ''
        vals = {}
        ewaybill_pool = self.env['eway.bill']
        #         saleIds = self._context.get('active_ids')
        #         eway_bill_id = ewaybill_pool.search([('do_id', '=', self.id)])
        # transporter_line_id = self.env['transporeter.lines'].search([('transporter_mode_id_grn', '=', self.grn_id.id)],order="id asc",limit=1)
        accountJsonList = []
        #         notewaylist = list(set(saleIds)-set(saleObjs.ids))
        gstEwayVersion = self.env['ir.config_parameter'].sudo().get_param('gst_ewaybill.gst_eway_version') or '1.0.0219'
        for val in self:
            transport_line_id = False
            transporter_line_id = self.env['transporeter.lines'].search([('invoice_id', '=', val.id)], order="id asc",
                                                                        limit=1)
            # transporter_line_id = self.env['transporeter.lines'].search([('transporter_mode_id_grn', '=', val.grn_id.id)],order="id asc",limit=1)
            if not transporter_line_id:
                raise UserError("Plz add transportation details.")
            if transporter_line_id.transportation_distance <= 0:
                raise UserError("Plz fill right transportation distance.")
            if transporter_line_id.transport_mode == 'road':
                transport_mode = 1
            elif transporter_line_id.transport_mode == 'air':
                transport_mode = 2
            elif transporter_line_id.transport_mode == 'Rail':
                transport_mode = 3
            else:
                transport_mode = 4
            if val.date_invoice:
                date_invoice = val.date_invoice.strftime('%d/%m/%Y')
            if transporter_line_id.bill_date:
                bill_date = transporter_line_id.bill_date.strftime('%d/%m/%Y')
            partnerShippingObj = val.partner_shipping_id
            currency = val.currency_id
            amountTotal = val.amount_total
            untaxTotal = val.amount_untaxed
            if transporter_line_id.vehicle_type:
                vehicleType = transporter_line_id.vehicle_type
            else:
                vehicleType = ''
            if currency.name != 'INR':
                amountTotal = amountTotal * currency.rate
                untaxTotal = untaxTotal * currency.rate
            transporterObj = transporter_line_id.transporter_id
            orderLineData = val.getAccountInvoiceLineJson()
            sgstValue = orderLineData[0][0]
            igstValue = orderLineData[0][1]
            itemdata = orderLineData[0][2]
            orderJsonDate = date_invoice
            transporterDate = bill_date
            companyObj = val.partner_id
            saleJsonData = {
                'genMode': 'Excel',
                # 'userGstin':val.partner_id.vat or '',
                'userGstin': val.company_id.vat or '',
                'supplyType': transporter_line_id.supply_type or 'O',
                'subSupplyType': int(transporter_line_id.sub_supply_type or 1),
                'docType': 'INV',
                'docNo': val.number or '',
                'docDate': orderJsonDate,
                'fromGstin': val.company_id.vat or '',
                'fromTrdName': val.company_id.name or '',
                'fromAddr1': val.company_id.street or '',
                'fromAddr2': val.company_id.street2 or '',
                'fromPlace': val.company_id.partner_id.city_id.name or '',
                'fromPincode': int(val.company_id.zip or 0),
                # 'fromStateCode': int(val.company_id.state_id.l10n_in_tin) or 0,
                # 'actualFromStateCode': int(val.company_id.state_id.l10n_in_tin) or 0,
                'toGstin': val.partner_id.vat or '',
                'toTrdName': val.partner_id.name or '',
                'toAddr1': val.partner_id.street or '',
                'toAddr2': val.partner_id.street2 or '',
                'toPlace': val.partner_id.city_id.name or '',
                'toPincode': int(val.partner_id.zip or 0),
                # 'toStateCode': int(val.partner_id.state_id.l10n_in_tin) or 0,
                # 'actualToStateCode': int(val.partner_id.state_id.l10n_in_tin) or 0,
                'totalValue': untaxTotal,
                'cgstValue': sgstValue,
                'sgstValue': sgstValue,
                'igstValue': igstValue,
                'totInvValue': amountTotal,
                'mainHsnCode': val.mainHsnCode or 0,
                'cessValue': 0.0,
                'TotNonAdvolVal': 0,
                'transMode': int(transport_mode),
                'transDistance': int(transporter_line_id.transportation_distance) or 0,
                'transporterName': transporter_line_id.transport_name or '',
                'transporterId': transporter_line_id.transporter_id.ref or "",
                'transDocNo': transporter_line_id.bl_lr_rr_airway_bill_no or '',
                'transDocDate': transporterDate,
                'vehicleNo': transporter_line_id.vehicle_no or '',
                'itemList': itemdata,
                'vehicleType': vehicleType,
                'transType': int(transporter_line_id.trans_type or 1),
            }

            ewaybill_ids = ewaybill_pool.search([('do_id', '=', val.grn_id.id)], limit=1)
            if not ewaybill_ids:
                vals = {'do_id': val.grn_id.id, 'consignor_street': val.company_id.street,
                        'consignor_street2': val.company_id.street2, 'consignor_zip': val.company_id.zip,
                        'consignor_city_id': val.company_id.partner_id.city_id.id,
                        'consignor_state_id': val.company_id.partner_id.state_id.id,
                        'consignor_country_id': val.company_id.country_id.id,
                        'consignee_street': val.partner_id.street, 'consignee_street2': val.partner_id.street2,
                        'consignee_zip': val.partner_id.zip, 'consignee_city_id': val.partner_id.city_id.id,
                        'consignee_state_id': val.partner_id.state_id.id,
                        'consignee_country_id': val.partner_id.country_id.id,
                        'vehicle_no': transporter_line_id.vehicle_no,
                        'supply_type': transporter_line_id.supply_type,
                        'sub_supply_type': transporter_line_id.sub_supply_type,
                        'transportation_mode': str(transport_mode),
                        'transporter_id': transporter_line_id.transporter_id.id,
                        'transportation_distance': transporter_line_id.transportation_distance,
                        'mainHsnCode': val.mainHsnCode}
                ewaybill_id = ewaybill_pool.create(vals)
                val.ewaybill_id = ewaybill_id.id
            accountJsonList.append(saleJsonData)
        jsonData = {
            'version': gstEwayVersion,
            'billLists': accountJsonList
        }
        jsonAttachment = self.generatejsonAttachment(jsonData, "ewaybillgst" + str(val.number) + ".json")

        return jsonAttachment
    def upload_einvoice(self,einvoice_api=False):
        if not einvoice_api:
            raise UserError("Please provide E-Invoice API")
        authon_date = datetime.strptime(einvoice_api.token_no_expiry, '%d-%b-%Y %I:%M %p')
        authonticate_date = datetime.strptime(authon_date.strftime('%d-%m-%Y %H:%M'),"%d-%m-%Y %H:%M")
        if authonticate_date <= datetime.now():
            einvoice_api.authenticate()
        
        headers = {
            "Accept": "application/json",
            "client-id": einvoice_api.client_id or '',
            "client-secret": einvoice_api.client_secret or '',
            "user-name": einvoice_api.gstrobo_user or '',
            "authtoken": einvoice_api.token_no or '',
            "Tin-no": einvoice_api.name or '',
            "Content-Type": "application/json;charset=utf-8"
          }
        print("heasds",headers)
        some_uploaded = False
        msg = ''
        for inv in self:
#             if inv.is_einvoice and inv.einvoice_irn and inv.einv_cancelled==False:
#                 raise UserError("E-Invoice IRN is already Generated.")
#

            headers = {
              'client-id': 'fghgfhg34433fgh',
              'client-secret': 'vnbn234nbv21bvn3nbv',
              'user-name': 'testPranav',
              'tin-no': 'C58721731060',
              'authtoken': einvoice_api.token_no or '',
              'Content-Type': 'application/json'
            }
            vals = inv._prepare_einvoice_json()
            vals = json.dumps(vals)
            # print(vals)
            payload = json.dumps(vals)
            url_check = "http://182.76.79.246:6001/tpapi/mys/submitdocument"
            # headers.update({'user_name':einvoice_api.gstrobo_user or '',"Gstin": einvoice_api.name or '',})
            try:
                r = requests.post(url_check, vals, headers=headers)
                _logger.info("IRN API Response : %s " % str(r.content))
                j = json.loads(r.text)
                # print(j,"JSOSNSOSJSHSHJFHFHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHEA")
            except Exception as e:
                msg = "API Error: %s" %e
                raise UserError(msg)
            status_code = j.get('MessageId')
            message = j.get('Message')
            rdata = j.get('Data',{})
            rejected_docs = j.get('rejectedDocuments')
            print("REJECTED JSDKFKDFDAF",j)
            # if status_code==1:
            #     inv.write({
            #             'is_einvoice':True,
            #             'einvoice_irn':rdata.get('Irn'),
            #             'einvoice_api':einvoice_api.id,
            #             'einv_ack':rdata.get('AckNo'),
            #             'einv_date':rdata.get('AckDt'),
            #             'einv_signedinvoice':rdata.get('SignedInvoice'),
            #             'einv_signed_qrcode':rdata.get('SignedQRCode'),
            #             'einv_base64_qrcode':rdata.get('Base64QRCode'),
            #             'einvoice_message':message,
            #             'einv_qrcode_name':str(inv.number) + '_QRcode.png',
            #             'submission_uid': rdata.get('submissionUID'),
            #             'uuid':rdata.get('acceptedDocuments')[0].get('uuid')
            #         })
            #     msg += "IRN has been generated successfully for Invoice : %s.\n" % inv.number
            #     some_uploaded = True
            if not rejected_docs and j.get('acceptedDocuments'):
                inv.write({
                                'submission_uid': j.get('submissionUID'),
                                'uuid':j.get('acceptedDocuments')[0].get('uuid')
                            })
                # headers = {
                #      "Accept": "application/json",
                #      "client-id": einvoice_api.client_id or '',
                #      "client-secret": einvoice_api.client_secret or '',
                #      "User-name": einvoice_api.whitelisted_ip or '',
                #      "authtoken": einvoice_api.token or '',
                #      "Tin-no": einvoice_api.name or '',
                #      "Content-Type": "application/json;charset=utf-8"
                #     }
            elif j.get('error'):
                msg = j.get('error').get('message')
                self.show_popup(message=msg)
            if rejected_docs:
                if 'error' in j.get('rejectedDocuments')[0]:
                    print('MESAGGE DSJDJSHBSKDFBJBJHSJKJKASD',j.get('rejectedDocuments')[0].get('error').get('details')[0].get('message'))
                    self.show_popup(message=j.get('rejectedDocuments')[0].get('error').get('details')[0].get('message'))
                else:
                    print("SUBMISION ID SKFBASJJKASDJKASKJJKADWJKAS",j.get('submissionUID'),rdata)
                    vals = {
                         'submissionUid': j.get('submissionUID')
                     }
                    url_submision = "http://182.76.79.246:6001/tpapi/mys/GetDocumentSubmissions"
                    try:
                         r = requests.get(url_submision, params=vals, headers=headers)
                         _logger.info("IRN API Response : %s " % str(r.content))
                         j = json.loads(r.text)
                         print(j, "JSOSNSOSJSHSHJFHFHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHEA")
                    except Exception as e:
                         msg = "API Error: %s" % e
                         raise UserError(msg)
                    rejecte_docs = j.get('documentSummary')
                    url_submision_details = "http://182.76.79.246:6001/TpApi/MYS/GetDocumentDetails"
                    if rejecte_docs:
                        for uids in rejecte_docs:
                            vals ={
                                "uuid": uids.get('uuid')
                            }
                            try:
                                r = requests.get(url_submision_details, params=vals, headers=headers)
                                _logger.info("IRN API Response : %s " % str(r.content))
                                j = json.loads(r.text)
                                print(j, "JSOSNSOSJSHSHJFHFHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHEALAST")
                            except Exception as e:
                                msg = "API Error: %s" % e
                                raise UserError(msg)
                            inv.reason_not_accepted = j.get('status')


            #     if some_uploaded:
            #         inv.write({
            #                 'is_einvoice':False,
            #                 'einvoice_api':einvoice_api.id,
            #                 'einvoice_message':message,
            #             })
            #         continue
            #     raise UserError(message)
            # elif status_code==1005:
            #     einvoice_api.state = 'expired'
            #     einvoice_api.token_expiry = False
            #     einvoice_api.authenticate()
            #     inv.upload_einvoice(einvoice_api=einvoice_api)

        return self.show_popup(message=msg)
    
    def _prepare_ewbmain_json(self,einvoice_api):
        ewb=[]
        action = ""
        for inv in self:
            transporter_line_id = inv._get_transporter_line_id()
            # transporter_line_id = self.env['transporeter.lines'].search([('transporter_mode_id_grn', '=', inv.grn_id.id)],order="id asc",limit=1)
            if not transporter_line_id:
                raise UserError("Plz add transportation details.")
            if transporter_line_id.transportation_distance <= 0:
                raise UserError("Plz fill right transportation distance.")
            
            tmodes = {'sea': 'Ship','air': 'Air','rail': 'Rail','road': 'Road',
                      'truck': 'Road',
                      'rickshaw': 'Road',
                        'bullockcart': 'Road',
                        'byhand': 'Road',
                        'others': 'Road'}
            
            transport_mode = tmodes.get(transporter_line_id.transport_mode,None)
#             if transporter_line_id.transport_mode == 'road':
#                 transport_mode = 1
#             elif transporter_line_id.transport_mode == 'air':
#                 transport_mode = 2
#             elif transporter_line_id.transport_mode == 'Rail':
#                 transport_mode = 3
#             else:
#                 transport_mode = 4
            bill_date=None
            vehicleType=None
            if transporter_line_id.bill_date:
                bill_date = transporter_line_id.bill_date.strftime("%d-%b-%Y")
            transporterDate = bill_date
            if transporter_line_id.vehicle_type:
                vehicleType = transporter_line_id.vehicle_type=="R" and "Normal" or "Over Dimensional Cargo"
                
            stcd = inv.partner_id.state_id.code and str(inv.partner_id.state_id.code) or None
            buyer_gstin = inv.partner_id.vat or None
            buyer_pin = inv.partner_id.zip and int(inv.partner_id.zip) or None
            buyer_stcd = stcd
            buyer_pos = stcd
            buyer_name = inv.partner_id.name or None
            shipping_id = inv.partner_shipping_id or inv.partner_id
            ship_name = shipping_id.name or None
            ship_stcd = str(shipping_id.state_id.l10n_in_tin) or None
            ship_loc = shipping_id.city_id.name or shipping_id.district_id.name or None
            ship_gstin = shipping_id.vat or None
            ship_pin = shipping_id.zip and int(shipping_id.zip) or None
            if inv.invoice_type=='export':
                ship_stcd = shipping_id.country_id and str(shipping_id.country_id.gst_code) or 0
                buyer_gstin = "URP"
                ship_gstin = "URP"
                buyer_name = inv.partner_id.party_full_name or inv.partner_id.name or None
                ship_name = shipping_id.party_full_name or shipping_id.name or None
                buyer_pin = 999999 #inv.partner_id.zip and int(inv.partner_id.zip) or 999999
                ship_pin = 999999
                buyer_stcd = inv.partner_id.country_id and str(inv.partner_id.country_id.gst_code) or 0
                buyer_pos = inv.partner_id.country_id and str(inv.partner_id.country_id.gst_code) or 0
                    
            ewbdatas= {
                      "GENERATOR_GSTIN": inv.company_id.vat,
                      "TRANSACTION_TYPE": "OutWard",
                      "TRANSACTION_SUB_TYPE": "Supply",
                      "SUPPLY_TYPE": None,
                      "TRANS_TYPE_DESC": "",
                      "DOC_TYPE": "Tax Invoice",
                      "DOC_NO": inv.number,
                      "DOC_DATE": inv.date_invoice.strftime("%d-%b-%Y"),
                      "CONSIGNOR_GSTIN_NO": inv.company_id.vat or None,
                      "CONSIGNEE_GSTIN_NO": inv.partner_id.vat or None,
                      "CONSIGNOR_LEGAL_NAME": inv.company_id.name or None,
                      "CONSIGNEE_LEGAL_NAME": ship_name,
                      "SHIP_ADDRESS_LINE1":  inv.partner_id.street or None,
                      "SHIP_ADDRESS_LINE2": inv.partner_id.street2 or None,
                      "SHIP_STATE": inv.partner_id.state_id.name or None,
                      "SHIP_CITY_NAME": inv.partner_id.city_id.name or None,
                      "SHIP_PIN_CODE": ship_pin,
                      "SHIP_COUNTRY": inv.partner_id.country_id.name or None,
                      "ORIGIN_ADDRESS_LINE1": inv.company_id.street or None,
                      "ORIGIN_ADDRESS_LINE2": inv.company_id.street2 or None,
                      "ORIGIN_STATE": inv.company_id.state_id.name or None,
                      "ORIGIN_CITY_NAME": inv.company_id.city or None,
                      "ORIGIN_PIN_CODE": inv.company_id.zip or None,
                      "TRANSPORT_MODE": transport_mode,
                      "VEHICLE_TYPE": vehicleType,
                      "APPROXIMATE_DISTANCE": int(transporter_line_id.transportation_distance) or 0,
                      "TRANSPORTER_ID_GSTIN": transporter_line_id.transporter_id.ref or None,
                      "TRANS_DOC_NO": transporter_line_id.bl_lr_rr_airway_bill_no or None,
                      "TRANS_DOC_DATE":transporterDate,
                      "VEHICLE_NO": transporter_line_id.vehicle_no or None,
                    }
                  
            ItemList = []
            TOTAL_TAXABLE_VALUE = TOTALSGSTVAL=TOTALCGSTVAL=TOTALIGSTVAL=0.0
            sno=0
            
            for line in inv.invoice_line_ids.filtered(lambda l: not l.display_type):
                sno+=1
                TOTALSGSTVAL += float(line.sgst_amt)
                TOTALCGSTVAL += float(line.cgst_amt)
                TOTALIGSTVAL += float(line.igst_amt)
                
                product = line.product_id
                hsnCode = product.l10n_in_hsn_code or 0
                if hsnCode and len(hsnCode) > 4:
                    hsnCode = hsnCode[0:4]
                full_name = ''
                if product:
                    variable_attributes = product.attribute_line_ids.filtered(lambda l: len(l.value_ids) > 0).mapped(
                        'attribute_id')
                    variant = product.attribute_value_ids._variant_name(variable_attributes)
    
                    full_name = variant and "%s (%s)" % (product.name, variant) or product.name
                    if product.default_code:
                        full_name =  '[%s] %s' % (product.default_code,full_name)
                basic = line.quantity*line.price_unit
                TOTAL_TAXABLE_VALUE+=basic
                discount =  basic * ((line.discount or 0.0)+(line.discount2 or 0.0)) / 100.0
                ItemList.append({
                          "IGST_RATE": round(float(line.igst_per),2) or None,
                          "CGST_RATE": round(float(line.cgst_per),2) or None,
                          "SGST_RATE": round(float(line.sgst_per),2) or None,
                          "CESS_RATE": 0,
                          "CESS_NONADVOL": 0,
                          "ITEM_NAME": full_name or line.name or None,
                          "HSN_CODE": hsnCode or None,
                          "UOM": line.uom_id.gst_uom_code or 'OTH',
                          "QUANTITY": round(line.quantity,2),
                          "TAXABLE_VALUE":basic,
                              })
            
            ewbdatas.update({
                    "Items":ItemList,
#                     "AssVal": round(inv.amount_untaxed,2),
                   "IGST_AMOUNT":round(TOTALIGSTVAL,2),
                   "CGST_AMOUNT":round(TOTALCGSTVAL,2),
                   "SGST_AMOUNT":round(TOTALSGSTVAL,2),
                   "CESS_AMOUNT":0,
                   "TOTAL_TAXABLE_VALUE": TOTAL_TAXABLE_VALUE,
                   "CESS_NONADVOL_AMOUNT": None,
                   "BUSINESS_LINE_CODE": None,
                   "OTHER_VALUE":round(inv.tcs_amount,2),
                   "TOTAL_INVOICE_VALUE":round(inv.amount_total,2),
                   
                })
            
            ewb.append(ewbdatas)

            if inv.bool_updated_data:
                action = "UPDATEINVOICE"
            else:
                action = "INVOICE"
        
        return {
            "action": action,
              "data": ewb
        }
    
    def _prepare_ewb_json(self):
        # transporter_line_id = self._get_transporter_line_id()
        transporter_line_id = self.transporeter_line
        # transporter_line_id = self.env['transporeter.lines'].search([('transporter_mode_id_grn', '=', inv.grn_id.id)],order="id asc",limit=1)
        if not transporter_line_id:
            raise UserError("Plz add transportation details.")
        if transporter_line_id.transportation_distance <= 0:
            raise UserError("Plz fill right transportation distance.")
        if transporter_line_id.transport_mode == 'road':
            transport_mode = 1
        elif transporter_line_id.transport_mode == 'air':
            transport_mode = 2
        elif transporter_line_id.transport_mode == 'Rail':
            transport_mode = 3
        else:
            transport_mode = 4
        bill_date=None
        vehicleType=None
        if transporter_line_id.bill_date:
            bill_date = transporter_line_id.bill_date.strftime('%d/%m/%Y')
        transporterDate = bill_date
        if transporter_line_id.vehicle_type:
            vehicleType = transporter_line_id.vehicle_type
            
        stcd = self.partner_id.state_id.code and str(self.partner_id.state_id.code) or None
        buyer_gstin = self.partner_id.vat or None
        buyer_pin = self.partner_id.zip and int(self.partner_id.zip) or None
        buyer_stcd = stcd
        buyer_pos = stcd
        buyer_name = self.partner_id.name or None
        shipping_id = self.partner_shipping_id or self.partner_id
        ship_name = shipping_id.name or None
        ship_stcd = str(shipping_id.state_id.code) or None
        ship_loc = shipping_id.city or shipping_id.district_id.name or None
        ship_gstin = shipping_id.vat or None
        ship_pin = shipping_id.zip and int(shipping_id.zip) or None
        if self.invoice_type=='export':
            # ship_stcd = '96' #shipping_id.country_id and str(shipping_id.country_id.gst_code) or 0
            buyer_gstin = "URP"
            ship_gstin = "URP"
            buyer_name = self.partner_id.party_full_name or self.partner_id.name or None
            ship_name = shipping_id.party_full_name or shipping_id.name or None
            buyer_pin = 999999 #self.partner_id.zip and int(self.partner_id.zip) or 999999
            # ship_pin = 999999
            buyer_stcd = '96' #self.partner_id.country_id and str(self.partner_id.country_id.gst_code) or 0
            buyer_pos = '96' #self.partner_id.country_id and str(self.partner_id.country_id.gst_code) or 0
                
        ewb={
                "ACTION": "EWAYBILL",
                "Irn":self.einvoice_irn,
                "Distance":int(transporter_line_id.transportation_distance) or 0,
                "TransMode":str(transport_mode),
                "TransId":transporter_line_id.transporter_id.ref or None,
                "TransName":transporter_line_id.transport_name or None,
                "TransDocNo":transporter_line_id.bl_lr_rr_airway_bill_no or None,
                "TransDocDt":transporterDate,
                "VehNo":transporter_line_id.vehicle_no or None,
                "VehType":vehicleType,
                "ExpShipDtls":{
                    "Gstin":ship_gstin,
                    "LglNm":ship_name,
                    "TrdNm":ship_name,
                    "Addr1":shipping_id.street or None,
                    "Addr2":shipping_id.street2 or None,
                    "Loc":ship_loc,
                    "Pin":ship_pin,
                    "Stcd":ship_stcd,
                    },
                "DispDtls":{
                    "Gstin":buyer_gstin,
                   "Nm":buyer_name,
                   "TrdNm":buyer_name,
                   "Pos":buyer_pos,
                   "Addr1":self.partner_id.street or None,
                   "Addr2":self.partner_id.street2 or None,
                   "Loc":self.partner_id.city or self.partner_id.district_id.name or None,
                   "Pin":buyer_pin,
                   "Stcd":buyer_stcd,
                   "Ph":None, #self.partner_id.mobile or self.partner_id.phone or None,
                   "Em":self.partner_id.email or None,
                    }
                }
        return ewb
    
    def create_ewaybill(self,einvoice_api=False):
        if not einvoice_api:
            raise UserError("Please provide E-Invoice API")
        
        headers = {
            "Accept": "application/json",
            "client_id": einvoice_api.client_id or '',
            "client_secret": einvoice_api.client_secret or '',
            "IPAddress": einvoice_api.whitelisted_ip or '',
            "Content-Type": "application/json;charset=utf-8"
          }
        msg = ''
        for inv in self:
            vals = inv._prepare_ewb_json()
            print(json.dumps(vals))
    
            headers.update({'user_name':einvoice_api.gstrobo_user or '',"Gstin": einvoice_api.name or '',})
            try:
                r = requests.post(einvoice_api.einvoice_url, data=json.dumps(vals), headers=headers)
                _logger.info("Ewaybill API Response : %s " % str(r.content))
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
                        'einv_eway_bill':rdata.get('EwbNo'),
                        'einvoice_api':einvoice_api.id,
                        'ewb_date':rdata.get('EwbDt'),
                        'ewb_valid':rdata.get('EwbValidTill'),
                    })
                msg += "EWB %s has been generated successfully for Invoice : %s.\n" % (rdata.get('EwbNo'), inv.number)
            if status_code==0:
                raise UserError(message)
            elif status_code==1005:
                einvoice_api.state = 'expired'
                einvoice_api.token_expiry = False
                einvoice_api.authenticate()
                inv.create_ewaybill(einvoice_api=einvoice_api)
        return self.show_popup(message=msg)
    
    def create_ewaybill_main(self,einvoice_api=False):
        if not einvoice_api:
            raise UserError("Please provide E-Invoice API")
        
        headers = {
            "Accept": "application/json",
            "PRIVATEKEY": einvoice_api.pvt_key or '',
            "PRIVATEVALUE": einvoice_api.pvt_value or '',
            "IP": einvoice_api.client_ip or '',
            "Content-Type": "application/json;charset=utf-8"
          }
        vals = self._prepare_ewbmain_json(einvoice_api=einvoice_api)
        print(json.dumps(vals))

#             headers.update({'user_name':einvoice_api.gstrobo_user or '',"Gstin": einvoice_api.name or '',})
        try:
            r = requests.post(einvoice_api.ewb_url, data=json.dumps(vals), headers=headers)
            _logger.info("INVOICE  Ewaybill API Response : %s " % str(r.content))
            j = json.loads(r.text)
        except Exception as e:
            msg = "API Error: %s" %e
            raise UserError(msg)
        status_code = j.get('MessageId')
        message = j.get('Message')
        rdata = j.get('Data',[])
        if status_code==1:
            for invewb in rdata:
                if invewb.get('STATUS') == 'Success':
                    invno = invewb.get('DOC_NO')
                    inv = self.search([('number', '=', invno)], limit=1)
                    inv.bool_updated_data = True
                    val1 = {
                        "action": "SYNCEWAYBILL",
                        "data": [{
                            "GENERATOR_GSTIN": inv.company_id.vat,
                            "DOC_NO": inv.number,
                            "DOC_TYPE": "Tax Invoice"
                        }]
                    }
                    try:
                        r1 = requests.post(einvoice_api.ewb_url, data=json.dumps(val1), headers=headers)
                        _logger.info("SYNCEWAYBILL Ewaybill API Response : %s " % str(r1.content))
                        j1 = json.loads(r1.text)
                    except Exception as e:
                        msg = "API Error: %s" % e
                        raise UserError(msg)
                    status_code = j.get('STATUS')
                    rdata1 = j1.get('Data', [])
                    for invewb1 in rdata1:
                        inv.write({
                                'is_einvoice':True,
                                'einv_eway_bill':invewb1.get('EWB_NO'),
                                'ewb_date': invewb1.get('EWB_DATE'),
                                'ewb_valid': invewb1.get('VALID_UPTO_DATE'),
                                'einvoice_api':einvoice_api.id,
                                'ewb_message':invewb1.get('REMARKS'),
                            })
        if status_code==0:
            raise UserError(message)
        elif status_code==1005:
            einvoice_api.state = 'expired'
            einvoice_api.token_expiry = False
            einvoice_api.authenticate()
            self.create_ewaybill_main(einvoice_api=einvoice_api)
        return True

    def _prepare_einvoice_json(self):
        line_list =[]
        for values in self.invoice_line_ids:
            values_inv = {
                "Classification_Code": "004",
                "Product_Tariff_Code": "12344321",
                "Description": values.product_id.name,
                "Origin_Country_Code": "MYS",
                "Price_Amount": 17.0,
                "Tax_Amount": 0.0,
                "Subtotal": 100.0,
                "Tax_Rate": 6.0,
                "Line_Extension_Amount": 1436.50,
                "Unit_Code": None,
                "Quantity": 1.0,
                "Discount_Rate": 0.15,
                "Discount_Amount": 100.0,
                "Discount_Reason": "RSN1",
                "Charge_Rate": 0.10,
                "Charge_Amount": 100.0,
                "Charge_Reason": "RSN2",
                "Sub_Total_Taxable_Amount": 1460.50,
                "Tax_Type_Code": "01",
                "Sub_Total_Tax_Amount": 0.0,
                "Sub_Total_Tax_Exemption_Reason": "RSN1",
                "Sub_Total_Tax_Scheme": "OTH"
            }
            line_list.append(values_inv)

        invoice_data = {
            "Invoices": [
                {
                    "Invoice_Number": self.name,
                    "Invoice_Date": self.invoice_date.strftime("%d/%m/%Y"),
                    "Invoice_Time": "12:11:03",
                    "Invoice_Type_Code": "01",
                    "Invoice_Period_Start_Date": self.invoice_date.strftime("%d/%m/%Y"),
                    "Invoice_Period_End_Date": self.invoice_date.strftime("%d/%m/%Y"),
                    "Invoice_Period_Description": "Monthly",
                    "Supplier_TIN": "C58721731060",
                    "Supplier_Registration_Name": "Binary semantics",
                    "Supplier_Id_Type": "BRN",
                    "Supplier_Id_Value": "202401019286",
                    "Supplier_SST_Registration": None,
                    "Supplier_Tourism_Tax_Registration": None,
                    "Supplier_Electronic_Mail": "general.ams@supplier.com",
                    "Supplier_Address_Line0": "Binary Semantics Gurgaon",
                    "Supplier_Address_Line1": "Bangunan Merdeka",
                    "Supplier_Address_Line2": "Persiaran Jaya",
                    "Supplier_Postal_Zone": "50480",
                    "Supplier_City_Name": "Kuala Lumpur",
                    "Supplier_Country_Subentity_Code": "14",
                    "Supplier_Country_Code": "MYS",
                    "Supplier_Telephone": "+60-123456789",
                    "Industry_Classification_Code": "01111",
                    "Industry_Classification_Name": "Growing of maize",
                    "Buyer_Registration_Name": "Hebat Group",
                    "Buyer_TIN": "EI00000000010",
                    "Buyer_Id_Type": "BRN",
                    "Buyer_Id_Value": "NA",
                    "Buyer_SST_Registration": None,
                    "Buyer_Electronic_Mail": "name@buyer.com",
                    "Buyer_Address_Line0": "Lot 66",
                    "Buyer_Address_Line1": "Bangunan Merdeka",
                    "Buyer_Address_Line2": "Persiaran Jaya",
                    "Buyer_Postal_Zone": "50480",
                    "Buyer_City_Name": "Kuala Lumpur",
                    "Buyer_Country_Subentity_Code": "14",
                    "Buyer_Country_Code": "MYS",
                    "Buyer_Telephone": "+60-123456789",
                    "Shipping_Registration_Name": "Greenz Sdn. Bhd.",
                    "Shipping_Address_Line0": "Lot 66",
                    "Shipping_Address_Line1": "Bangunan Merdeka",
                    "Shipping_Address_Line2": "Persiaran Jaya",
                    "Shipping_Postal_Zone": "50480",
                    "Shipping_City_Name": "Kuala Lumpur",
                    "Shipping_Country_Subentity_Code": "14",
                    "Shipping_Country_Code": "MYS",
                    "Shipping_TIN": "EI00000000010",
                    "Shipping_Id_Type": "BRN",
                    "Shipping_Id_Value": "NA",
                    "Currency_Code": "MYR",
                    "Tax_Currency_Code": "MYR",
                    "Discount_Amount": 100,
                    "Discount_Reason": "rsn1",
                    "Charge_Amount": 100,
                    "Charge_Reason": "rsn2",
                    "Total_Tax_Exclusive_Amount": 1436.5,
                    "Total_Tax_Inclusive_Amount": 1436.5,
                    "Total_Line_Extension_Amount": 1436.5,
                    "Total_Payable_Amount": 1436.5,
                    "Total_Allowance_Total_Amount": 1436.5,
                    "Total_Charge_Total_Amount": 1436.5,
                    "Payable_Rounding_Amount": 0.3,
                    "Total_Tax_Amount": 0,
                    "Sub_Total_Tax_Per_Tax_Type": [
                        {
                            "Sub_Total_Tax_Amount": 0,
                            "Sub_Total_Taxable_Amount": 87.63,
                            "Tax_Type_Code": "E",
                            "Sub_Total_Scheme_ID": "UN/ECE 5153",
                            "Sub_Total_Scheme_Agency_ID": "6",
                            "Sub_Total_Tax_Scheme": "OTH"
                        }
                    ],
                    "Shipment_Id": "1234",
                    "Freight_Allowance_Charge_Reason": "treason1",
                    "Freight_Allowance_Charge_Amount": 100,
                    "Payment_Means_Code": "01",
                    "Payee_Financial_Account": "1234567890123",
                    "Payment_Terms": "Payment method is cash",
                    "PrePayment_Paid_Amount": 1,
                    "PrePayment_Paid_Date": self.invoice_date.strftime("%d/%m/%Y"),
                    "PrePayment_Paid_Time": "12:11:07",
                    "PrePayment_Reference_Id": "E12345678912",
                    "Billing_Reference": "E12345678912",
                    "Customs_Form_Id": "E12345678912",
                    "Incoterms_Id": "CIF",
                    "FTA_ID": "FTA",
                    "FTA_Document_Description": "Sample Description",
                    "Authorisation_Number_Certified_Exporter": "CPT-CCN-W-211111-KL-000002",
                    "Customs_Form2_ID": "E12345678912",
                    "Line_Item_Details": [
                        {
                            "Classification_Code": "004",
                            "Product_Tariff_Code": "12344321",
                            "Description": "Laptop Peripherals",
                            "Origin_Country_Code": "MYS",
                            "Price_Amount": 17,
                            "Tax_Amount": 0,
                            "Subtotal": 100,
                            "Tax_Rate": 6,
                            "Line_Extension_Amount": 1436.5,
                            "Unit_Code": "Q13",
                            "Quantity": 1,
                            "Discount_Rate": 0.15,
                            "Discount_Amount": 100,
                            "Discount_Reason": "RSN1",
                            "Charge_Rate": 0.1,
                            "Charge_Amount": 100,
                            "Charge_Reason": "RSN2",
                            "Sub_Total_Taxable_Amount": 1460.5,
                            "Tax_Type_Code": "01",
                            "Sub_Total_Tax_Amount": 0,
                            "Sub_Total_Tax_Exemption_Reason": "RSN1",
                            "Sub_Total_Tax_Scheme": "OTH",
                            "Sub_Total_Scheme_ID": "UN/ECE 5153",
                            "Sub_Total_Scheme_Agency_ID": "6"
                        }
                    ]
                }
            ]
        }
        return invoice_data
        # invoices_data = {
        #     "Invoices": [
        #         {
        #             "Invoice_Time": self.invoice_date.strftime("%H:%M:%S"),
        #             "Invoice_Type_Code": "01",
        #             "Invoice_Period_Start_Date": self.invoice_date.strftime("%d/%m/%Y"),
        #             "Invoice_Period_End_Date": self.invoice_date.strftime("%d/%m/%Y"),
        #             "Invoice_Period_Description": "Monthly",
        #             "Supplier_TIN": "C58721731060",
        #             "Supplier_Registration_Name": self.env.user.company_id.name,
        #             "Supplier_Id_Type": "BRN",
        #             "Supplier_Id_Value": "202401019286",
        #             "Supplier_SST_Registration": None,
        #             "Supplier_Tourism_Tax_Registration": None,
        #             "Supplier_Electronic_Mail": self.env.user.company_id.email,
        #             "Supplier_Address_Line0": self.env.user.company_id.street or '',
        #             "Supplier_Address_Line1": self.env.user.company_id.street2 or '',
        #             "Supplier_Address_Line2":  '',
        #             "Supplier_Postal_Zone": self.env.user.company_id.zip or '',
        #             "Supplier_City_Name": '',
        #             "Supplier_Country_Subentity_Code": self.env.user.company_id.country_id.name or '',
        #             "Supplier_Country_Code": "MYS",
        #             "Supplier_Telephone": self.env.user.company_id.phone,
        #             "Industry_Classification_Code": "01111",
        #             "Industry_Classification_Name": "Growing of maize",
        #             "Buyer_Registration_Name": self.partner_id.name,
        #             "Buyer_TIN": "C58721731060",
        #             "Buyer_Id_Type": "BRN",
        #             "Buyer_Id_Value": "NA",
        #             "Buyer_SST_Registration": None,
        #             "Buyer_Electronic_Mail":  self.partner_id.email,
        #             "Buyer_Address_Line0": self.partner_id.street or '',
        #             "Buyer_Address_Line1": self.partner_id.street2 or '',
        #             "Buyer_Address_Line2": self.partner_id.city or '',
        #             "Buyer_Postal_Zone": self.partner_id.zip or '',
        #             "Buyer_City_Name":'',
        #             "Buyer_Country_Subentity_Code":  self.partner_id.country_id.name or '',
        #             "Buyer_Country_Code": "MYS",
        #             "Buyer_Telephone": self.partner_id.phone,
        #             "Shipping_Registration_Name": self.partner_shipping_id.name,
        #             "Shipping_Address_Line0": self.partner_shipping_id.street,
        #             "Shipping_Address_Line1": self.partner_shipping_id.street2,
        #             "Shipping_Address_Line2": self.partner_shipping_id.city,
        #             "Shipping_Postal_Zone":self.partner_shipping_id.zip,
        #             "Shipping_City_Name": self.partner_shipping_id.city,
        #             "Shipping_Country_Subentity_Code":self.partner_shipping_id.name,
        #             "Shipping_Country_Code":self.partner_shipping_id.country_id.name,
        #             "Shipping_TIN":self.partner_shipping_id.vat,
        #             "Shipping_Id_Type": "BRN",
        #             "Shipping_Id_Value": "NA",
        #             "Currency_Code": "MYR",
        #             "Tax_Currency_Code": "MYR",
        #             "Payment_Means_Code": "01",
        #             "Discount_Amount": 100.0,
        #             "Discount_Reason": "rsn1",
        #             "Charge_Amount": 100.0,
        #             "Charge_Reason": "rsn2",
        #             "Total_Tax_Exclusive_Amount":self.amount_untaxed,
        #             "Total_Tax_Inclusive_Amount": self.amount_total,
        #             "Total_Line_Extension_Amount": self.amount_total,
        #             "Total_Payable_Amount": self.amount_total,
        #             "Total_Allowance_Total_Amount": 0.0,
        #             "Total_Charge_Total_Amount": 0.0,
        #             "Payable_Rounding_Amount": 0.0,
        #             "Total_Tax_Amount": self.amount_tax,
        #             "Sub_Total_Tax_Per_Tax_Type": [
        #                 {
        #                     "Sub_Total_Tax_Amount": self.amount_tax,
        #                     "Sub_Total_Taxable_Amount": self.amount_total,
        #                     "Tax_Category_Code": "01",
        #                     "Sub_Total_Scheme_ID": "UN/ECE 5153",
        #                     "Sub_Total_Scheme_Agency_ID": "6",
        #                     "Sub_Total_Tax_Scheme": "OTH"
        #                 }
        #             ],
        #             "Shipment_Id": "1234",
        #             "Freight_Allowance_Charge_Reason": "treason1",
        #             "Freight_Allowance_Charge_Amount": 100.0,
        #             "Payee_Financial_Account": "1234567890123",
        #             "Payment_Terms": self.invoice_payment_term_id.name,
        #             "PrePayment_Paid_Amount": 1.0,
        #             "PrePayment_Paid_Date": self.invoice_date.strftime("%d/%m/%Y"),
        #             "PrePayment_Paid_Time": "12:11:07",
        #             "PrePayment_Reference_Id": "E12345678912",
        #             "Billing_Reference": "E12345678912",
        #             "Customs_Form_Id": "E12345678912",
        #             "Incoterms_Id": "CIF",
        #             "FTA_ID": "ASEAN-Australia-New Zealand FTA (AANZFTA)",
        #             "FTA_Document_Description": "Sample Description",
        #             "Authorisation_Number_Certified_Exporter": "CPT-CCN-W-211111-KL-000002",
        #             "Customs_Form2_ID": "E12345678912",
        #             "Line_Item_Details": line_list
        #         }
        #     ]
        # }

        # einvoice = {
        #     "ACTION": "INVOICE",
        #     "VERSION": "1.1",
        #     "BUSINESS_LINE_CODE": "deport-1",
        #     "Irn": None,
        #     "TPAPITRANDTLS": {"REVREVERSECHARGE": self.reverse_charge and "Y" or "N",
        #                       "TYP": etype,
        #                       "TAXPAYERTYPE": "GST",
        #                       "EcomGstin": None,
        #                       "IgstOnIntra": None, },
        #     "TPAPIDOCDTLS": {
        #         "DOCNO": self.number,
        #         "DOCDATE": self.invoice_date.strftime("%d/%m/%Y"),
        #         "DOCTYP": self.type == 'out_refund' and 'CRN' or 'INV',
        #     },
        #     "TpApiExpDtls": {
        #         "ShippingBillNo": ShippingBillNo,
        #         "ShippingBillDate": ShippingBillDate,
        #         "PortCode": PortCode,
        #         "ForeignCurrency": None,
        #         "CountryCode": None,
        #         "RefundClaim": None,
        #         "ExportDuty": "88",
        #     },
        #     "TPAPISELLERDTLS": {
        #         "GSTINNO": self.company_id.vat or None,
        #         "LEGALNAME": self.company_id.name or None,
        #         "TRDNAME": self.company_id.name or None,
        #         "ADDRESS1": self.company_id.street or None,
        #         "ADDRESS2": self.company_id.street2 or None,
        #         "LOCATION": self.company_id.city or None,
        #         # self.company_id.district_id and self.company_id.district_id.name or None,
        #         "PINCODE": self.company_id.zip or None,
        #         "StateCode": self.company_id.state_id.code or None,
        #         "MobileNo": self.company_id.partner_id.mobile or None,
        #         "EmailId": self.company_id.partner_id.email or None,
        #     },
        #     "TPAPIBUYERDTLS": {
        #         "GSTINNO": buyer_gstin,
        #         "LEGALNAME": buyer_name,
        #         "TRDNAME": buyer_name,
        #         "PLACEOFSUPPLY": buyer_pos,
        #         "ADDRESS1": self.partner_id.street or None,
        #         "ADDRESS2": self.partner_id.street2 or None,
        #         "LOCATION": self.partner_id.city or self.partner_id.district_id.name or None,
        #         "PINCODE": buyer_pin,
        #         "StateCode": buyer_stcd,
        #         "MobileNo": self.partner_id.mobile or None,
        #         "EmailId": self.partner_id.email or None,
        #     },
        #     "TpApiDispDtls": {
        #         "CompName": self.company_id.name or None,
        #         "Address1": self.company_id.street or None,
        #         "Address2": self.company_id.street2 or None,
        #         "Location": self.company_id.city or None,
        #         # self.company_id.district_id and self.company_id.district_id.name or None,
        #         "Pincode": self.company_id.zip or None,
        #         "StateCode": self.company_id.state_id.code or None,
        #     },
        #     "TpApiShipDtls": {
        #         "GstinNo": ship_gstin,
        #         "LegalName": ship_name,
        #         "TrdName": ship_name,
        #         "Address1": self.partner_shipping_id.street or None,
        #         "Address2": self.partner_shipping_id.street2 or None,
        #         "Location": ship_loc,
        #         "Pincode": ship_pin,
        #         "StateCode": ship_stcd,
        #     },
        #     "TPAPIADDLDOCUMENT": [
        #         #             {
        #         #               "Url": "tyhf",
        #         #               "Docs": "tres",
        #         #               "Info": "uhjkkkkkkkkkkkkkk"
        #         #             },
        #         #             {
        #         #               "Url": "hgrtn",
        #         #               "Docs": "jkkkj",
        #         #               "Info": "hjkhh"
        #         #             }
        #     ],
        #     "TpApiEwbDtls": {
        #         "TransId": None,
        #         "TransName": None,
        #         "TransMode": "1",
        #         "Distance": "15",
        #         "TransDocNo": None,
        #         "TransDocDt": None,
        #         "VehNo": None,
        #         "VehType": None
        #     },
        #     "TpApiPayDtls": {
        #         "PayeeName": None,
        #         "AcctDet": None,
        #         "ModeofPayment": None,
        #         "IFSCcode": None,
        #         "PaymentTerm": None,
        #         "PaymentInstr": None,
        #         "CreditTrn": None,
        #         "DirectDebit": None,
        #         "CreditDays": 125,
        #         "PaidAmt": 0,
        #         "PaymentDue": 0
        #     },
        #     "TPAPIREFDTLS": {
        #         "InvoiceRemarks": self.number or None,
        #         "TpApiDocPerdDtls": {
        #             "INVOICESTDT": self.invoice_date.strftime("%d/%m/%Y"),
        #             "INVOICEENDDT": self.invoice_date.strftime("%d/%m/%Y"),
        #         },
        #         "TPAPICONTRACT": [
        #             #               {
        #             #                 "RECADVREFR": None,
        #             #                 "RECADVDT": None,
        #             #                 "TENDREFR": None,
        #             #                 "ContrRefr": "123",
        #             #                 "ExtRefr": "253664",
        #             #                 "ProjRefr": "hshd",
        #             #                 "PORefr": "wr",
        #             #                 "PORefDt": "06/03/2020"
        #             #               }
        #         ],
        #         "TPAPIPRECDOCUMENT": [
        #             {
        #                 "INVNO": self.number or None,
        #                 "INVDT": self.invoice_date.strftime("%d/%m/%Y"),
        #                 "OTHREFNO": None
        #             }
        #         ]
        #     },
        #
        # }
        # TPAPIITEMLIST = []
        # TOTALSGSTVAL = TOTALCGSTVAL = TOTALIGSTVAL = 0.0
        # sno = 0
        # for line in self.invoice_line_ids.filtered(lambda l: not l.display_type):
        #     sno += 1
        #     # TOTALSGSTVAL += float(line.sgst_amt)
        #     # TOTALCGSTVAL += float(line.cgst_amt)
        #     # TOTALIGSTVAL += float(line.igst_amt)
        #     TOTALSGSTVAL += 9
        #     TOTALCGSTVAL += 9
        #     TOTALIGSTVAL += 9
        #     product = line.product_id
        #     hsnCode = 0
        #     # if hsnCode and len(hsnCode) > 4:
        #     #     hsnCode = hsnCode[0:4]
        #     full_name = ''
        #     if product:
        #         variable_attributes = product.attribute_line_ids.filtered(lambda l: len(l.value_ids) > 0).mapped(
        #             'attribute_id')
        #         variant = None
        #
        #         full_name = variant and "%s (%s)" % (product.name, variant) or product.name
        #         if product.default_code:
        #             full_name = '[%s] %s' % (product.default_code, full_name)
        #     basic = line.quantity * line.price_unit
        #     discount = basic * ((line.discount or 0.0) + (line.discount2 or 0.0)) / 100.0
        #     TPAPIITEMLIST.append({
        #         "SINO": str(sno),
        #         "PRODUCTDESC": full_name or line.name or None,
        #         "ISSERVICE": line.product_id.type == 'service' and "Y" or "N",
        #         "HSNCODE": str(hsnCode),
        #         "BarCode": line.product_id.barcode or None,
        #         "QUANTITY": round(line.quantity, 2),
        #         "FreeQuantity": round(line.free_qty, 2),
        #         # "UNIT": line.uom_id.gst_uom_code or 'OTH',
        #         "UNIT": 'OTH',
        #         "UNITPRICE": round(line.price_unit, 2),
        #         "TOTAMOUNT": round(basic, 2),
        #         "DISCOUNT": round(discount, 2),
        #         "PRETAXABLEVAL": round(line.price_subtotal, 2),
        #         "OTHERCHARGES": "0",
        #         "ASSAMOUNT": round(basic - discount, 2),
        #         # "GSTRATE": line.igst_per!='0.0' and round(float(line.igst_per),2) or round(float(line.sgst_per)+float(line.cgst_per),2),
        #         "GSTRATE": 19,
        #         # "IGSTAMT": round(line.igst_amt,2),
        #         "IGSTAMT": 19,
        #         # "CGSTAMT": round(line.cgst_amt,2),
        #         # "SGSTAMT": round(line.sgst_amt,2),
        #         "CGSTAMT": 9,
        #         "SGSTAMT": 9,
        #         "CESRATE": "0",
        #         "CESSAMT": "0",
        #         "CESNONADVALAMT": "0",
        #         "STATECESRATE": "0",
        #         "STATECESAMT": "0",
        #         # "TOTITEMVAL": round(line.untaxed_and_taxed_amount,2),
        #         "TOTITEMVAL": 200,
        #         "OrderLineRef": None,
        #         "OriginCountry": None,
        #         "ProdSerialNo": line.product_id.default_code or None,
        #         "StateCesNonAdvlAmt": "0",
        #         "TpApiBchDtls": {
        #             "BatchName": line.product_id.name and line.product_id.name[:20] or None,
        #             "ExpiryDate": None,
        #             "WarrantyDate": None
        #         },
        #         "TPAPIATTRIBDTLS": [
        #             {
        #                 "NM": None,
        #                 "VAL": None
        #             }
        #         ]
        #     })
        #
        # einvoice.update({
        #     "TPAPIITEMLIST": TPAPIITEMLIST,
        #     "TPAPIVALDTLS": {
        #         "TOTALTAXABLEVAL": round(self.amount_untaxed, 2),
        #         "TOTALSGSTVAL": round(TOTALSGSTVAL, 2),
        #         "TOTALCGSTVAL": round(TOTALCGSTVAL, 2),
        #         "TOTALIGSTVAL": round(TOTALIGSTVAL, 2),
        #         "TOTALCESVAL": "0",
        #         "TOTALSTATECESVAL": "0",
        #         "TOTINVOICEVAL": round(self.amount_total, 2),
        #         # "ROUNDOFAMT": round(self.round_off_value,2),
        #         "ROUNDOFAMT": 5,
        #         "TOTALINVVALUEFC": "0",
        #         "Discount": 0,  # round(self.amount_discount,2),
        #         # "OthCharge": round(self.tcs_amount,2)
        #         "OthCharge": 6
        #     },
        # })
        # return invoices_data
    # def _prepare_einvoice_json(self):
    #     etyps = {'Regular':'B2B','SEZ supplies with payment':'SEZWP','SEZ supplies without payment':'SEZWOP',
    #             'Deemed Exp':'DEXP','EXPWP':'EXPWP','EXPWOP':'EXPWOP'}
    #     etype = self.gst_invoice_type and etyps.get(self.gst_invoice_type,"B2B") or "B2B"
    #
    #     stcd = self.partner_id.state_id.code and str(self.partner_id.state_id.code) or None
    #     buyer_gstin = self.partner_id.vat or None
    #     buyer_pin = self.partner_id.zip and int(self.partner_id.zip) or None
    #     buyer_stcd = stcd
    #     buyer_pos = stcd
    #     buyer_name = self.partner_id.name or None
    #     shipping_id = self.partner_shipping_id or self.partner_id
    #     ship_name = shipping_id.name or None
    #     ship_stcd = str(shipping_id.state_id.code) or None
    #     ship_loc = shipping_id.city or shipping_id.district_id.name or None
    #     # ship_stcd = None
    #     # ship_loc = None
    #     # print("11111111111111111111111111111",self.partner_id.name,'  -b-  ',buyer_name,' -s-  ',shipping_id,' -sn-  ',ship_name,' -sl-  ',ship_loc)
    #     ship_gstin = shipping_id.vat or None
    #     ship_pin = shipping_id.zip and int(shipping_id.zip) or None
    #     # ship_gstin = None
    #     # ship_pin =  None
    #     ShippingBillNo = None
    #     ShippingBillDate = None
    #     PortCode = None
    #     # # if etype in ('SEZWP','SEZWOP'):
    #     # #     buyer_stcd = '96' #self.partner_id.state_id.l10n_in_tin and self.partner_id.state_id.l10n_in_tin.gst_code or '96'
    #     # buyer_pos = '96'
    #     # ship_stcd = '96'
    #     # buyer_stcd = '96'
    #     if self.invoice_type=='export' or etype in ('EXPWP','EXPWOP'):
    #         ship_stcd = '96' #shipping_id.state_id.l10n_in_tin and shipping_id.state_id.l10n_in_tin.gst_code or '96'
    #         buyer_gstin = "URP"
    #         ship_gstin = "URP"
    #         buyer_name = self.partner_id.party_full_name or self.partner_id.name or None
    #         ship_name = shipping_id.party_full_name or shipping_id.name or None
    #         buyer_pin = 999999 #inv.partner_id.zip and int(inv.partner_id.zip) or 999999
    #         ship_pin = 999999
    #         buyer_stcd = '96' #self.partner_id.state_id.l10n_in_tin and self.partner_id.state_id.l10n_in_tin.gst_code or '96'
    #         buyer_pos = '96' #self.partner_id.state_id.l10n_in_tin and self.partner_id.state_id.l10n_in_tin.gst_code or '96'
    #         ShippingBillNo = self.shipping_bill_number or None
    #         ShippingBillDate = self.shipping_bill_date and self.shipping_bill_date.strftime("%d/%m/%Y") or None
    #         PortCode = self.port_code or None
    #     # print("222222222222222222222", self.partner_id.name, '  -b-  ', buyer_name, ' -s-  ', shipping_id,' -sn-  ', ship_name, ' -sl-  ', ship_loc)
    #     einvoice ={
    #         "ACTION":"INVOICE",
    #         "VERSION":"1.1",
    #         "BUSINESS_LINE_CODE": "deport-1",
    #         "Irn":None,
    #         "TPAPITRANDTLS":{   "REVREVERSECHARGE":self.reverse_charge and "Y" or "N",
    #                             "TYP":etype,
    #                             "TAXPAYERTYPE":"GST",
    #                             "EcomGstin":None,
    #                             "IgstOnIntra":None,},
    #         "TPAPIDOCDTLS":{
    #                         "DOCNO":self.number,
    #                         "DOCDATE":self.invoice_date.strftime("%d/%m/%Y"),
    #                         "DOCTYP":self.type == 'out_refund' and 'CRN' or 'INV',
    #                         },
    #         "TpApiExpDtls":{
    #                         "ShippingBillNo": ShippingBillNo,
    #                         "ShippingBillDate": ShippingBillDate,
    #                         "PortCode": PortCode,
    #                         "ForeignCurrency": None,
    #                         "CountryCode": None,
    #                         "RefundClaim": None,
    #                         "ExportDuty":"88",
    #                         },
    #         "TPAPISELLERDTLS":{
    #             "GSTINNO": self.company_id.vat or None,
    #             "LEGALNAME": self.company_id.name or None,
    #             "TRDNAME": self.company_id.name or None,
    #             "ADDRESS1":  self.company_id.street or None,
    #             "ADDRESS2":  self.company_id.street2 or None,
    #             "LOCATION": self.company_id.city or None,
    #             # self.company_id.district_id and self.company_id.district_id.name or None,
    #             "PINCODE": self.company_id.zip or None,
    #             "StateCode":  self.company_id.state_id.code or None,
    #             "MobileNo":  self.company_id.partner_id.mobile or None,
    #             "EmailId":  self.company_id.partner_id.email or None,
    #             },
    #         "TPAPIBUYERDTLS":{
    #             "GSTINNO": buyer_gstin,
    #             "LEGALNAME": buyer_name,
    #             "TRDNAME": buyer_name,
    #             "PLACEOFSUPPLY": buyer_pos,
    #             "ADDRESS1": self.partner_id.street or None,
    #             "ADDRESS2": self.partner_id.street2 or None,
    #             "LOCATION": self.partner_id.city or self.partner_id.district_id.name or None,
    #             "PINCODE": buyer_pin,
    #             "StateCode": buyer_stcd,
    #             "MobileNo": self.partner_id.mobile or None,
    #             "EmailId": self.partner_id.email or None,
    #         },
    #         "TpApiDispDtls":{
    #             "CompName": self.company_id.name or None,
    #             "Address1":  self.company_id.street or None,
    #             "Address2":  self.company_id.street2 or None,
    #             "Location":  self.company_id.city or None, #self.company_id.district_id and self.company_id.district_id.name or None,
    #             "Pincode":  self.company_id.zip or None,
    #             "StateCode":  self.company_id.state_id.code or None,
    #           },
    #           "TpApiShipDtls": {
    #             "GstinNo": ship_gstin,
    #             "LegalName":  ship_name,
    #             "TrdName":  ship_name,
    #             "Address1": self.partner_shipping_id.street or None,
    #             "Address2": self.partner_shipping_id.street2 or None,
    #             "Location": ship_loc,
    #             "Pincode": ship_pin,
    #             "StateCode": ship_stcd,
    #            },
    #           "TPAPIADDLDOCUMENT": [
    # #             {
    # #               "Url": "tyhf",
    # #               "Docs": "tres",
    # #               "Info": "uhjkkkkkkkkkkkkkk"
    # #             },
    # #             {
    # #               "Url": "hgrtn",
    # #               "Docs": "jkkkj",
    # #               "Info": "hjkhh"
    # #             }
    #           ],
    #           "TpApiEwbDtls": {
    #             "TransId": None,
    #             "TransName": None,
    #             "TransMode": "1",
    #            "Distance": "15",
    #             "TransDocNo": None,
    #             "TransDocDt": None,
    #             "VehNo": None,
    #             "VehType": None
    #           },
    #           "TpApiPayDtls": {
    #             "PayeeName": None,
    #             "AcctDet": None,
    #             "ModeofPayment": None,
    #             "IFSCcode": None,
    #             "PaymentTerm": None,
    #             "PaymentInstr": None,
    #             "CreditTrn": None,
    #             "DirectDebit": None,
    #             "CreditDays": 125,
    #             "PaidAmt": 0,
    #             "PaymentDue": 0
    #           },
    #           "TPAPIREFDTLS": {
    #             "InvoiceRemarks": self.number or None,
    #             "TpApiDocPerdDtls": {
    #               "INVOICESTDT": self.invoice_date.strftime("%d/%m/%Y"),
    #               "INVOICEENDDT": self.invoice_date.strftime("%d/%m/%Y"),
    #             },
    #             "TPAPICONTRACT": [
    # #               {
    # #                 "RECADVREFR": None,
    # #                 "RECADVDT": None,
    # #                 "TENDREFR": None,
    # #                 "ContrRefr": "123",
    # #                 "ExtRefr": "253664",
    # #                 "ProjRefr": "hshd",
    # #                 "PORefr": "wr",
    # #                 "PORefDt": "06/03/2020"
    # #               }
    #             ],
    #             "TPAPIPRECDOCUMENT": [
    #               {
    #                 "INVNO": self.number or None,
    #                 "INVDT": self.invoice_date.strftime("%d/%m/%Y"),
    #                 "OTHREFNO":None
    #               }
    #             ]
    #           },
    #
    #     }
    #     TPAPIITEMLIST = []
    #     TOTALSGSTVAL=TOTALCGSTVAL=TOTALIGSTVAL=0.0
    #     sno=0
    #     for line in self.invoice_line_ids.filtered(lambda l: not l.display_type):
    #         sno+=1
    #         # TOTALSGSTVAL += float(line.sgst_amt)
    #         # TOTALCGSTVAL += float(line.cgst_amt)
    #         # TOTALIGSTVAL += float(line.igst_amt)
    #         TOTALSGSTVAL += 9
    #         TOTALCGSTVAL += 9
    #         TOTALIGSTVAL += 9
    #         product = line.product_id
    #         hsnCode =  0
    #         # if hsnCode and len(hsnCode) > 4:
    #         #     hsnCode = hsnCode[0:4]
    #         full_name = ''
    #         if product:
    #             variable_attributes = product.attribute_line_ids.filtered(lambda l: len(l.value_ids) > 0).mapped(
    #                 'attribute_id')
    #             variant =None
    #
    #             full_name = variant and "%s (%s)" % (product.name, variant) or product.name
    #             if product.default_code:
    #                 full_name =  '[%s] %s' % (product.default_code,full_name)
    #         basic = line.quantity*line.price_unit
    #         discount =  basic * ((line.discount or 0.0)+(line.discount2 or 0.0)) / 100.0
    #         TPAPIITEMLIST.append({
    #                  "SINO": str(sno),
    #               "PRODUCTDESC": full_name or line.name or None,
    #               "ISSERVICE": line.product_id.type=='service' and "Y" or "N",
    #               "HSNCODE": str(hsnCode),
    #               "BarCode": line.product_id.barcode or None,
    #               "QUANTITY": round(line.quantity,2),
    #               "FreeQuantity": round(line.free_qty,2),
    #               # "UNIT": line.uom_id.gst_uom_code or 'OTH',
    #               "UNIT":  'OTH',
    #               "UNITPRICE": round(line.price_unit,2),
    #               "TOTAMOUNT": round(basic,2),
    #               "DISCOUNT": round(discount,2),
    #               "PRETAXABLEVAL": round(line.price_subtotal,2),
    #               "OTHERCHARGES": "0",
    #               "ASSAMOUNT": round(basic-discount,2),
    #               # "GSTRATE": line.igst_per!='0.0' and round(float(line.igst_per),2) or round(float(line.sgst_per)+float(line.cgst_per),2),
    #               "GSTRATE": 19,
    #               # "IGSTAMT": round(line.igst_amt,2),
    #               "IGSTAMT": 19,
    #               # "CGSTAMT": round(line.cgst_amt,2),
    #               # "SGSTAMT": round(line.sgst_amt,2),
    #               "CGSTAMT": 9,
    #               "SGSTAMT": 9,
    #               "CESRATE": "0",
    #               "CESSAMT": "0",
    #               "CESNONADVALAMT": "0",
    #               "STATECESRATE": "0",
    #               "STATECESAMT": "0",
    #               # "TOTITEMVAL": round(line.untaxed_and_taxed_amount,2),
    #               "TOTITEMVAL": 200,
    #               "OrderLineRef": None,
    #               "OriginCountry": None,
    #              "ProdSerialNo":line.product_id.default_code or None,
    #               "StateCesNonAdvlAmt": "0",
    #               "TpApiBchDtls": {
    #                 "BatchName": line.product_id.name and line.product_id.name[:20] or None,
    #                 "ExpiryDate": None,
    #                 "WarrantyDate": None
    #               },
    #               "TPAPIATTRIBDTLS": [
    #                 {
    #                   "NM": None,
    #                   "VAL": None
    #                   }
    #                  ]
    #             })
    #
    #     einvoice.update({
    #             "TPAPIITEMLIST":TPAPIITEMLIST,
    #             "TPAPIVALDTLS": {
    #                 "TOTALTAXABLEVAL": round(self.amount_untaxed,2),
    #                 "TOTALSGSTVAL": round(TOTALSGSTVAL,2),
    #                 "TOTALCGSTVAL": round(TOTALCGSTVAL,2),
    #                 "TOTALIGSTVAL": round(TOTALIGSTVAL,2),
    #                 "TOTALCESVAL": "0",
    #                 "TOTALSTATECESVAL": "0",
    #                 "TOTINVOICEVAL": round(self.amount_total,2),
    #                 # "ROUNDOFAMT": round(self.round_off_value,2),
    #                 "ROUNDOFAMT": 5,
    #                 "TOTALINVVALUEFC": "0",
    #                 "Discount": 0, #round(self.amount_discount,2),
    #                 # "OthCharge": round(self.tcs_amount,2)
    #                 "OthCharge": 6
    #               },
    #         })
    #     return einvoice
    
    def generate_einvoice_json(self):
        jsonData = self.get_gst_einvoice_json()
        jsonAttachment = self.generatejsonAttachment(jsonData, "E-invoice"+str(self.number)+".json")
        if not jsonAttachment:
            raise UserError("JSON of E-Way Bill is not present")
        return {
            'type' : 'ir.actions.act_url',
            'url':   '/web/content/%s?download=1' % (jsonAttachment.id),
            'target': 'new',
            }
        
    def generatejsonAttachment(self, jsonData, jsonFileName):
        jsonAttachment = False
        if jsonData:
            jsonData = json.dumps(jsonData, indent=4, sort_keys=False)
            base64Data = base64.b64encode(jsonData.encode('utf-8'))
            try:
                ewaydata = {
                    'datas': base64Data,
                    'type': 'binary',
                    'res_model': 'account.move',
                    'db_datas': jsonFileName,
                    'datas_fname': jsonFileName,
                    'name': jsonFileName
                }
                jsonObjs = self.env['ir.attachment'].search([('name', '=', jsonFileName)])
                if jsonObjs:
                    jsonAttachment = jsonObjs[0]
                    jsonAttachment.write(ewaydata)
                else:
                    jsonAttachment = self.env['ir.attachment'].create(ewaydata)
            except ValueError:
                pass
        return jsonAttachment
    
    def _get_transporter_line_id(self):
        transporter_line_id = False
        trobj = self.env['transporeter.lines']
        transporter_line_id = trobj.search([('invoice_id', '=', self.id)], order="id asc",limit=1)
        return transporter_line_id
    
    def _get_seller_vals(self):
        vals = {
               "Gstin":self.company_id.vat or None,
               "LglNm":self.company_id.name or None,
               "TrdNm":self.company_id.name or None,
               "Addr1":self.company_id.street or None,
               "Addr2":self.company_id.street2 or None,
               "Loc":self.company_id.city or None, #self.company_id.district_id.name or None,
               "Pin":self.company_id.zip and int(self.company_id.zip) or None,
               # "Stcd":self.company_id.state_id.l10n_in_tin or None,
               "Ph":self.company_id.partner_id.mobile or self.company_id.partner_id.phone or None,
               "Em":self.company_id.email or None,
                }
        return vals
    def get_gst_einvoice_json(self):
        etyps = {'Regular':'B2B','SEZ supplies with payment':'SEZWP','SEZ supplies without payment':'SEZWOP',
                'Deemed Exp':'DEXP','EXPWP':'EXPWP','EXPWOP':'EXPWOP'}
        einvoice=[]
        for inv in self:    
            etype = inv.gst_invoice_type and etyps.get(inv.gst_invoice_type,"B2B") or "B2B"
            # transporter_line_id = inv._get_transporter_line_id()
            # #             transporter_line_id = self.env['transporeter.lines'].search([('transporter_mode_id_grn', '=', inv.grn_id.id)],order="id asc",limit=1)
            # # if not transporter_line_id:
            # #     raise UserError("Plz add transportation details.")
            # if transporter_line_id.transportation_distance <= 0:
            #     raise UserError("Plz fill right transportation distance.")
            # if transporter_line_id.transport_mode == 'road':
            #     transport_mode = 1
            # elif transporter_line_id.transport_mode == 'air':
            #     transport_mode = 2
            # elif transporter_line_id.transport_mode == 'Rail':
            #     transport_mode = 3
            # else:
            #     transport_mode = 4
            # bill_date=None
            # vehicleType=None
            # if transporter_line_id.bill_date:
            #     bill_date = transporter_line_id.bill_date.strftime('%d/%m/%Y')
            # transporterDate = bill_date
            # if transporter_line_id.vehicle_type:
            #     vehicleType = transporter_line_id.vehicle_type
            # stcd = inv.partner_id.state_id.l10n_in_tin and str(inv.partner_id.state_id.l10n_in_tin) or None
            buyer_gstin = inv.partner_id.vat or None
            buyer_pin = inv.partner_id.zip and int(inv.partner_id.zip) or None
            # buyer_stcd = stcd
            # buyer_pos = stcd
            buyer_name = ''
            buyer_pos = ''
            buyer_stcd = ''
            buyer_name = inv.partner_id.name or None
            shipping_id = inv.partner_shipping_id or inv.partner_id
            ship_name = shipping_id.name or None
            # ship_stcd = str(shipping_id.state_id.l10n_in_tin) or None
            # ship_loc = shipping_id.city_id.name or shipping_id.district_id.name or None
            ship_gstin = shipping_id.vat or None
            ship_pin = shipping_id.zip and int(shipping_id.zip) or None
            if inv.invoice_type=='export' or etype in ('EXPWP','EXPWOP'):
                ship_stcd = shipping_id.country_id and str(shipping_id.country_id.gst_code) or 0
                buyer_gstin = "URP"
                ship_gstin = "URP"
                buyer_name = inv.partner_id.party_full_name or inv.partner_id.name or None
                ship_name = shipping_id.party_full_name or shipping_id.name or None
                buyer_pin = 999999 #inv.partner_id.zip and int(inv.partner_id.zip) or 999999
                ship_pin = 999999
                buyer_stcd = inv.partner_id.country_id and str(inv.partner_id.country_id.gst_code) or 0
                buyer_pos = inv.partner_id.country_id and str(inv.partner_id.country_id.gst_code) or 0
                
            vals ={
                "Version":"1.1",
                "TranDtls":{
                               "TaxSch":"GST",
                               "SupTyp":inv.gst_invoice_type and etyps.get(inv.gst_invoice_type,"B2B") or "B2B",
                               "IgstOnIntra":"N",
                               "RegRev":"N",
                               "EcmGstin":None
                },
                "DocDtls":{
                               "Typ":inv.type=='out_refund' and "CRN" or "INV",
                               "No":inv.number or None,
                               "Dt":datetime.today().strftime("%d/%m/%Y"),
                },
                "SellerDtls": inv._get_seller_vals(),
                "BuyerDtls":{
                               "Gstin":buyer_gstin,
                               "LglNm":buyer_name,
                               "TrdNm":buyer_name,
                               "Pos":buyer_pos,
                               "Addr1":inv.partner_id.street or None,
                               "Addr2":inv.partner_id.street2 or None,
                               "Loc": None,
                               "Pin":buyer_pin,
                               "Stcd":buyer_stcd,
                               "Ph":None, #inv.partner_id.mobile or inv.partner_id.phone or None,
                               "Em":inv.partner_id.email or None,
                },
                "DispDtls":None,
                "ShipDtls":{
                        "Gstin": ship_gstin,
                        "LglNm":  ship_name,
                        "TrdNm":  ship_name,
                        "Addr1": shipping_id.street or None,
                        "Addr2": shipping_id.street2 or None,
                        "Loc": None,
                        "Pin": None,
                        "Stcd": None,
                    },
                "ExpDtls":{
                               "ShipBNo":None,
                               "ShipBDt":None,
                               "Port": None,
                               "RefClm":None,
                               "ForCur":None,
                               "CntCode":None,
                               "ExpDuty":0
                },
                "EwbDtls":{
                               "TransId":None,#transporter_line_id.transporter_id.ref or None,
                               "TransName":None,
                               "TransMode":str('transport_mode'),
                               "Distance": 0,
                               "TransDocNo": None,
                               "TransDocDt":datetime.today().strftime("%d/%m/%Y"),
                               "VehNo": None,
                               "VehType":None
                            }
                }
            
            
            ItemList = []
            TOTALSGSTVAL=TOTALCGSTVAL=TOTALIGSTVAL=0.0
            sno=0
            
            for line in inv.invoice_line_ids.filtered(lambda l: not l.display_type):
                sno+=1
                TOTALSGSTVAL += 18
                TOTALCGSTVAL += 18
                TOTALIGSTVAL += 18
                product = line.product_id
                hsnCode =  0
                if hsnCode and len(hsnCode) > 4:
                    hsnCode = hsnCode[0:4]
                full_name = ''
                if product:
                    variable_attributes = None
                    variant = None
    
                    full_name = variant and "%s (%s)" % (product.name, variant) or product.name
                    if product.default_code:
                        full_name =  '[%s] %s' % (product.default_code,full_name)
                basic = line.quantity*line.price_unit
                discount =  basic * ((line.discount or 0.0)+(line.discount2 or 0.0)) / 100.0
                ItemList.append({
                               "SlNo":str(sno),
                                "PrdDesc": full_name or line.name or None,
                                "IsServc": product.type=='service' and "Y" or "N",
                                "HsnCd":hsnCode or None,
                                "Barcde":product.barcode or None,
                              "Qty": round(line.quantity,2),
                               "FreeQty": round(line.free_qty,2),
                              "Unit":  'OTH',
                              "UnitPrice":round(line.price_unit,2),
                              "TotAmt": round(basic,2), 
                              "AssAmt": round(basic-discount,2), 
                              "TotItemVal": 700,
                              "PreTaxVal": 0, #round(basic-discount,2), 
                              "Discount": round(discount,2),
                              "GstRt": 0,
                              "IgstAmt": 9,
                              "CgstAmt": 9,
                              "SgstAmt": 9,
                              "CesRt": 0,
                              "CesAmt": 0,
                              "CesNonAdvlAmt": 0,
                              "StateCesRt": 0,
                              "StateCesAmt": 0,
                              "StateCesNonAdvlAmt": 0,
                              "StateCesNonAdvlAmt": 0,
                              "OthChrg": 0,
                              "BchDtls":None
                              })
            
            vals.update({
                    "ItemList":ItemList,
                    "ValDtls":{
                               "AssVal": round(inv.amount_untaxed,2),
                               "IgstVal":round(TOTALIGSTVAL,2),
                               "CgstVal":round(TOTALCGSTVAL,2),
                               "SgstVal":round(TOTALSGSTVAL,2),
                               "CesVal":0,
                               "StCesVal":0,
                               "Discount":0, #round(inv.amount_discount,2),
                               "OthChrg":600,
                               "RndOffAmt":700,
                               "TotInvVal":900,
                               },
                })
            
            einvoice.append(vals)
            
        return einvoice

    def _prepare_gst_sale_json(self, gstinvoice_api):
        gst = []
        action = ""
        for inv in self:
            date = self.date_invoice
            date1 = date.strftime("%d-%b-%Y")
            gstdatas = {
                        "SupplierGstin": self.company_id.vat,
                        "ReceiverGstin": self.partner_id.vat,
                        "LegalName": self.partner_id.name,
                        "BillAddress1": "",
                        "BillAddress2": "",
                        "BillStateName": "",
                        "BillCityName": "",
                        "CountryName": "",
                        "BpinCode": "",
                        "DocumentNumber": self.number,
                        "DocumentDate": date1,
                        "DocumentValue": self.amount_total,
                        "PlaceOfSupply": self.partner_id.state_id.name,
                        "ShipAddressLine1": "",
                        "ShipAddressLine2": "",
                        "ShipState": "",
                        "ShipCityName": "",
                        "ShipCountry": "",
                        "SpinCode": "",
                        "InvoiceCategory": "SAL-I",
                        "ReturnPeriod": "",
                        "DocType": "R",
                        "DrCrNoteType": "C",
                        "IsReverseChOrPreGst": "No",
                        "EcomGstin": "",
                        "ShippingBillNo": "",
                        "ShippingBillDate": "",
                        "PortCode": "",
                        "ReasonForIssuing": "",
                        "OrgInvoiceNumber": "",
                        "OrgInvoiceDate": "",
                        "CurrencyCode": "",
                        "ConversionAmtRS": "",
                        "ConversionAmt": "",
                        "DifferentialPercentage": "",
                        "SupplycoveredSec7ofIGSTAct": "",
                        "SupplierClaimingRefund": "",
                        "AutoPopulateforRefund": "",
                        "DFlag": "",
                        "Col1": None,
                        "Col2": None,
                        "Col3": None,
            }
            ItemList = []
            TOTAL_TAXABLE_VALUE = TOTALSGSTVAL = TOTALCGSTVAL = TOTALIGSTVAL = 0.0
            sno = 0

            for line in inv.invoice_line_ids.filtered(lambda l: not l.display_type):
                sno += 1
                TOTALSGSTVAL += float(line.sgst_amt)
                TOTALCGSTVAL += float(line.cgst_amt)
                TOTALIGSTVAL += float(line.igst_amt)

                product = line.product_id
                hsnCode = product.l10n_in_hsn_code or 0
                if hsnCode and len(hsnCode) > 4:
                    hsnCode = hsnCode[0:4]
                full_name = ''
                if product:
                    variable_attributes = product.attribute_line_ids.filtered(lambda l: len(l.value_ids) > 0).mapped(
                        'attribute_id')
                    variant = product.attribute_value_ids._variant_name(variable_attributes)

                    full_name = variant and "%s (%s)" % (product.name, variant) or product.name
                    if product.default_code:
                        full_name = '[%s] %s' % (product.default_code, full_name)
                basic = line.quantity * line.price_unit
                TOTAL_TAXABLE_VALUE += basic
                discount = basic * ((line.discount or 0.0) + (line.discount2 or 0.0)) / 100.0
                ItemList.append({
                                "HsnCode": hsnCode,
                                "ItemDescription" : line.name,
                                "UomDescription": line.product_id.uom_id.name,
                                "TaxRate": line.invoice_line_tax_ids.amount,
                                "ProductRate": line.price_unit,
                                "Quantity": line.quantity,
                                "CessRate": None,
                                "DiscountValue": None,
                                "TaxableValue": None,
                                "IgstAmount": None,
                                "CgstAmount": None,
                                "SgstAmount": None,
                                "CessAmount": None,
                                "NetAmount": line.untaxed_and_taxed_amount - line.tax_amount,
                                "CessNonAdvolAmount": None
                                })

            gstdatas.update({
                "Items": ItemList,

            })

            gst.append(gstdatas)

            # if inv.bool_updated_data:
            #     action = "UPDATEINVOICE"
            # else:
            #     action = "INVOICE"

        return {
            "action": "SAVEANDVALIDATE",
            "Invoices": gst}

    def create_gst_sale_main(self, gstinvoice_api=False):
        gstinvoice_api_pool = self.env['gst.sale.purchase']
        gstinvoice_api = gstinvoice_api_pool.search([],limit=1)
        if not gstinvoice_api:
            raise UserError("Please provide GST-Invoice API")
        if not self.number:
            raise UserError("There is no invoice number found.")
        headers = {
            "Accept": "application/json",
            "ClientId": gstinvoice_api.client_id or '',
            "ClientSecret": gstinvoice_api.client_secret or '',
            "IP": gstinvoice_api.whitelisted_ip or '',
            "Auth_Token": gstinvoice_api.auth_token or '',
            "GstinNo": gstinvoice_api.name,
            "Content-Type": "application/json;charset=utf-8"
          }
        vals = self._prepare_gst_sale_json(gstinvoice_api=gstinvoice_api)

        #             headers.update({'user_name':einvoice_api.gstrobo_user or '',"Gstin": einvoice_api.name or '',})
        print(json.dumps(vals))
        try:
            r = requests.post(gstinvoice_api.invoice_url, data=json.dumps(vals), headers=headers)
            _logger.info("GST Sale INVOICE API Response : %s " % str(r.content))
            j = json.loads(r.text)
        except Exception as e:
            msg = "API Error: %s" % e
            raise UserError(msg)
        status_code = j.get('MessageId')
        message = j.get('Message')
        rdata = j.get('Data', [])
        if status_code == 1:
            for gst_api in rdata:
                self.gst_sale_status = gst_api.get('Status')
                self.api_remark = message
        if status_code == 0:
            raise UserError(message)
        elif status_code == 1005:
            gstinvoice_api.state = 'expired'
            gstinvoice_api.token_expiry = False
            gstinvoice_api.authenticate()
            self.create_gst_sale_main(gstinvoice_api=gstinvoice_api)
        return True

    def _prepare_gst_purchase_json(self, gstinvoice_api):
        gst = []
        action = ""
        for inv in self:
            date = self.date_invoice
            date1 = date.strftime("%d-%b-%Y")
            gstdatas = {
                        "SupplierGstin": self.partner_id.vat,
                        "ReceiverGstin": self.company_id.vat,
                        "LegalName": self.company_id.name,
                        "BillAddress1": "",
                        "BillAddress2": "",
                        "BillStateName": "",
                        "BillCityName": "",
                        "CountryName": "",
                        "BpinCode": "",
                        "DocumentNumber": self.number,
                        "DocumentDate": date1,
                        "DocumentValue": self.amount_total,
                        "PlaceOfSupply": self.company_id.state_id.name,
                        "ShipAddressLine1": "",
                        "ShipAddressLine2": "",
                        "ShipState": "",
                        "ShipCityName": "",
                        "ShipCountry": "",
                        "SpinCode": "",
                        "ReturnPeriod": "",
                        "DocType": "R",
                        "DrCrNoteType": "D",
                        "IsReverseChOrPreGst": "",
                        "EcomGstin": "",
                        "BillofEntryNumber": "",
                        "BillofEntryDate": "",
                        "PortCode": "",
                        "ReasonForIssuing": "",
                        "OrgInvoiceNumber": "",
                        "OrgInvoiceDate": "",
                        "InvoiceCategory": "PUR-I",
                        "SupplyType": "INTRASTATE",
                        "ItcClaimPercent": None,
                        "ITCEligibility": "",
                        "DifferentialPercentage": "",
                        "SupplycoveredSec7ofIGSTAct": "",
                        "AutoPopulateforRefund": "",
                        "DFlag": "",
                        "Col1": None,
                        "Col2": None,
                        "Col3": None,

            }
            ItemList = []
            TOTAL_TAXABLE_VALUE = TOTALSGSTVAL = TOTALCGSTVAL = TOTALIGSTVAL = 0.0
            sno = 0

            for line in inv.invoice_line_ids.filtered(lambda l: not l.display_type):
                sno += 1
                TOTALSGSTVAL += float(line.sgst_amt)
                TOTALCGSTVAL += float(line.cgst_amt)
                TOTALIGSTVAL += float(line.igst_amt)

                product = line.product_id
                hsnCode = product.l10n_in_hsn_code or 0
                if hsnCode and len(hsnCode) > 4:
                    hsnCode = hsnCode[0:4]
                full_name = ''
                if product:
                    variable_attributes = product.attribute_line_ids.filtered(lambda l: len(l.value_ids) > 0).mapped(
                        'attribute_id')
                    variant = product.attribute_value_ids._variant_name(variable_attributes)

                    full_name = variant and "%s (%s)" % (product.name, variant) or product.name
                    if product.default_code:
                        full_name = '[%s] %s' % (product.default_code, full_name)
                basic = line.quantity * line.price_unit
                TOTAL_TAXABLE_VALUE += basic
                discount = basic * ((line.discount or 0.0) + (line.discount2 or 0.0)) / 100.0
                ItemList.append({
                                "ItemCode": line.product_id.default_code,
                                "HsnCode": hsnCode,
                                "UomDescription": line.product_id.uom_id.name,
                                "TaxRate": line.invoice_line_tax_ids.amount,
                                "ProductRate": line.price_unit,
                                "Quantity": line.quantity,
                                "CessRate": None,
                                "DiscountValue": None,
                                "TaxableValue": None,
                                "IgstAmount": None,
                                "CgstAmount": None,
                                "SgstAmount": None,
                                "CessAmount": None,
                                "NetAmount": line.untaxed_and_taxed_amount - line.tax_amount,
                                "IgstClaimAmount": None,
                                "CgstClaimAmount": None,
                                "SgstClaimAmount": None,
                                "CessClaimAmount": None

                                })

            gstdatas.update({
                "Items": ItemList,

            })

            gst.append(gstdatas)

            # if inv.bool_updated_data:
            #     action = "UPDATEINVOICE"
            # else:
            #     action = "INVOICE"

        return {
            "action": "PUR_SAVEANDVALIDATE",
            "Invoices": gst}

    def create_gst_purchase_main(self, gstinvoice_api=False):
        gstinvoice_api_pool = self.env['gst.sale.purchase']
        gstinvoice_api = gstinvoice_api_pool.search([],limit=1)
        if not gstinvoice_api:
            raise UserError("Please provide GST-Invoice API")
        if not self.number:
            raise UserError("There is no invoice number found.")

        headers = {
            "Accept": "application/json",
            "ClientId": gstinvoice_api.client_id or '',
            "ClientSecret": gstinvoice_api.client_secret or '',
            "IP": gstinvoice_api.whitelisted_ip or '',
            "Auth_Token": gstinvoice_api.auth_token or '',
            "GstinNo": gstinvoice_api.name,
            "Content-Type": "application/json;charset=utf-8"
          }
        vals = self._prepare_gst_purchase_json(gstinvoice_api=gstinvoice_api)

        #             headers.update({'user_name':einvoice_api.gstrobo_user or '',"Gstin": einvoice_api.name or '',})
        print(json.dumps(vals))
        try:
            r = requests.post(gstinvoice_api.invoice_url, data=json.dumps(vals), headers=headers)
            _logger.info("GST Sale INVOICE API Response : %s " % str(r.content))
            j = json.loads(r.text)
        except Exception as e:
            msg = "API Error: %s" % e
            raise UserError(msg)
        status_code = j.get('MessageId')
        message = j.get('Message')
        rdata = j.get('Data', [])
        if status_code == 1:
            for gst_api in rdata:
                self.gst_purchase_status = gst_api.get('Status')
                self.api_remark = message
        if status_code == 0:
            raise UserError(message)
        elif status_code not in [0,1]:
            gstinvoice_api.state = 'expired'
            gstinvoice_api.token_expiry = False
            gstinvoice_api.authenticate()
            self.create_gst_purchase_main(gstinvoice_api=gstinvoice_api)
            return True
        return True
    
class ResCountry(models.Model):
    _inherit = 'res.country'

    gst_code = fields.Char(string='State Code Description',size=2)
    
class ResPartner(models.Model):
    _inherit = 'res.partner'

    party_full_name = fields.Char(string='Partner Full Name')
    
class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'

    discount = fields.Float(string='Discount (%)', digits=dp.get_precision('Product Unit of Measure'))
    discount2 = fields.Float(string='Discount 2(%)', digits=dp.get_precision('Product Unit of Measure'))
    free_qty = fields.Float(string='Free Qty',digits=dp.get_precision('Product Unit of Measure'))
    
    
class APIMessagePopup(models.TransientModel):
    _name = "api.message.wizard"

    
    message = fields.Char("Messaage")
    
    def action_ok(self):
        """ close wizard"""
        return {'type': 'ir.actions.act_window_close'}
        
class eway_bill_wiz(models.TransientModel):
    _name = "eway.bill.wiz"
    
    einvoice_api = fields.Many2one('gstrobo.apiconfig',string="E-Invoice API Config")
    
    @api.model
    def default_get(self, fields):
        user_pool = self.env['res.users']
        result = super(eway_bill_wiz, self).default_get(fields)
        einvoice_api = self.env['gstrobo.apiconfig'].search([('state','!=','draft')],limit=1)
        if einvoice_api:
            result['einvoice_api'] = einvoice_api.id
        return result
    
    def _get_invs(self):
        if not self.einvoice_api:
            raise UserError("Please select E-Invoice API")
        context = (self._context or {})
        inv_obj = self.env['account.move']
        return inv_obj.browse(context.get('active_ids', []))
        
    def upload_einvoice(self):
        res = False
        inv_ids = self._get_invs()
        if inv_ids:
            res = inv_ids.upload_einvoice(einvoice_api=self.einvoice_api)
        return res
    
    def create_ewaybill(self):
        res = False
        inv_ids = self._get_invs()
        if inv_ids:
            res = inv_ids.create_ewaybill(einvoice_api=self.einvoice_api)
        return res
    
    def create_ewaybill_main(self):
        res = False
        inv_ids = self._get_invs()
        if inv_ids:
            res = inv_ids.create_ewaybill_main(einvoice_api=self.einvoice_api)
        return res
    
    
    def button_einvoice_gen(self,):
        res = False
        context = (self._context or {})
        inv_obj = self.env['account.move']
        inv_ids =  inv_obj.browse(context.get('active_ids', []))
        if inv_ids:
            jsonData = inv_ids.get_gst_einvoice_json()
            jsonAttachment = self.env['account.move'].generatejsonAttachment(jsonData, "E-invoices.json")
            if not jsonAttachment:
                raise UserError("JSON of E-Way Bill is not present")
            return {
                'type' : 'ir.actions.act_url',
                'url':   '/web/content/%s?download=1' % (jsonAttachment.id),
                'target': 'new',
                }
            
    def get_einv_bydoc(self):
        res = False
        inv_ids = self._get_invs()
        if inv_ids:
            res = inv_ids.get_einv_bydoc(einvoice_api=self.einvoice_api)
        return res

    def get_einv_byirn(self):
        res = False
        inv_ids = self._get_invs()
        if inv_ids:
            res = inv_ids.get_einv_byirn(einvoice_api=self.einvoice_api)
        return res

    def button_eway_bill_gen(self, ):
        context = (self._context or {})
        inv_id = context.get('active_id')
        inv_obj = self.env['account.move']
        inv_ids = inv_obj.browse(self._context.get('active_ids', []))
        if inv_ids:
            jsonAttachment = inv_ids.generateJson()
            if not jsonAttachment:
                raise UserError("JSON of E-Way Bill is not present")
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=1' % (jsonAttachment.id),
            'target': 'new',
        }


class UoM(models.Model):
    _inherit = 'uom.uom'    
    
    gst_uom_code = fields.Selection([('BAG','Bags'),
                                    ('BAL','Bale'),
                                    ('BDL','Bundles'),
                                    ('BKL','Buckles'),
                                    ('BOU','Billions of Units'),
                                    ('BOX','Box'),
                                    ('BTL','Bottles'),
                                    ('BUN','Bunches'),
                                    ('CAN','Cans'),
                                    ('CBM','Cubic Metres'),
                                    ('CCM','Cubic Centimetres'),
                                    ('CMS','Centimetres'),
                                    ('CTN','Cartons'),
                                    ('DOZ','Dozens'),
                                    ('DRM','Drums'),
                                    ('GGK','Great Gross'),
                                    ('GMS','Grams'),
                                    ('GRS','Gross'),
                                    ('GYD','Gross Yards'),
                                    ('KGS','Kilograms'),
                                    ('KLR','Kilolitre'),
                                    ('KME','Kilometre'),
                                    ('LTR','Litre'),
                                    ('MTR','Metre'),
                                    ('MLT','Millilitre'),
                                    ('MTS','Metric Ton'),
                                    ('NOS','Numbers'),
                                    ('OTH','Others'),
                                    ('PAC','Packs'),
                                    ('PCS','Pieces'),
                                    ('PRS','Pairs'),
                                    ('QTL','Quintal'),
                                    ('ROL','Rolls'),
                                    ('SET','Sets'),
                                    ('SQF','Square Feet'),
                                    ('SQM','Square Metre'),
                                    ('SQY','Square Yards'),
                                    ('TBS','Tablets'),
                                    ('TGM','Ten Gross'),
                                    ('THD','Thousands'),
                                    ('TON','Tonnes'),
                                    ('TUB','Tubes'),
                                    ('UGS','US Gallons'),
                                    ('UNT','Unit'),
                                    ('YDS','Yards')],string="GST UoM Code")






class transporeter_lines(models.Model):
    _name = "transporeter.lines"

    transporter_mode_id_grn = fields.Many2one('account.move', 'Transport Mode ID GRN')
    transport_mode = fields.Selection([
        ('sea', 'Sea'),
        ('air', 'Air'),
        ('rail', 'Rail'),
        ('road', 'Road')], string="Transport Mode")
    transporter_id = fields.Many2one('res.partner',string="Transporter", help="Name of the Road, Rail, Air line, Shipping Line")
    veh_vessel_no = fields.Char("Veh/Vessel No")
    bl_lr_rr_airway_bill_no = fields.Char("BL/LR/RR/Airway Bill No.")
    bill_date = fields.Date("BL/LR/RR/Airway Bill Date")
    vehicle_no = fields.Char("Vehicle No.")
    driver_name = fields.Char("Driver Name")
    driver_no = fields.Char("Driver No.")
    remarks = fields.Char("Remarks")
    transporter_mode_id_gatepass = fields.Many2one('stock.gatepass', 'Transport Mode Gatepass')
    is_print = fields.Boolean(string="Show in print")
    supply_type = fields.Selection([('I', 'Inward'),('O', 'Outward')],string='Supply Type',help="Supply whether it is outward/inward.",default='O' )
    sub_supply_type = fields.Selection(
        [
            ('1', 'Supply'),
            ('2', 'Import'),
            ('3', 'Export'),
            ('4', 'Job Work'),
            ('5', 'For Own Use'),
            ('6', 'Job work Returns'),
            ('7', 'Sales Return'),
            ('8', 'Others'),
            ('9', 'SKD/CKD'),
            ('10', 'Line Sales'),
            ('11', 'Recipient Not Known'),
            ('12', 'Exhibition or Fairs'),
        ],
        copy=False,
        string='Sub Supply Type',
        help="Sub types of Supply like supply, export, Job Work etc.",default='1')
    vehicle_type = fields.Selection(
        [
            ('R', 'Regular'),
            ('O', 'ODC')
        ],
        string='Vehicle Type',
        help="Vehicle whether it is Regular/ODC."
    )
    #We have to remove this because we have replaced
    transport_name = fields.Char("Transporter/Line Name", help="Name of the Road, Rail, Air line, Shipping Line")
    way_bill_no = fields.Char("Way Bill No.")
    transportation_distance = fields.Float('Transportation Distance')
    trans_type = fields.Selection([('1', 'Regular'),('2', 'Bill To-Ship To'),
                                   ('3', 'Bill From-Dispatch From'),('4', 'Combination of 2 and 3')],copy=False,
                                   string='Transaction Type',default='1')