# -*- coding: utf-8 -*-
# Copyright 2019 Verts Services India Pvt Ltd.
# http://www.verts.co.in

from odoo import fields, models, api, _
from odoo.exceptions import Warning
from datetime import datetime
from xlsxwriter.workbook import Workbook
from io import BytesIO
import base64
import xlrd
#import pyqrcode
import qrcode

class InvoiceImp(models.TransientModel):
    _name = 'invoice.imp'
    _description = "Invoice Import"
    
    import_invoice_file = fields.Binary("Invoice file")


    def import_invoice_details(self):
        if not self.import_invoice_file:
            raise Warning(_("Please select Invoice file first!"))
        
        data_decode = self.import_invoice_file
        val = base64.decodestring(data_decode)
        fp = BytesIO()
        fp.write(val)
        wb = xlrd.open_workbook(file_contents=fp.getvalue())
        sheet_name = wb.sheet_names()
        sh = wb.sheet_by_name(sheet_name[0])
        n_rows = sh.nrows
        not_found = []
        for row in range(1, n_rows):
            invoice_no = sh.row_values(row)[3]
            inv_id= self.env['account.move'].search([('number', '=', invoice_no)],limit=1)
            if not inv_id:
                not_found.append(invoice_no)
                continue
                #raise Warning(_("Invoice %s Does not exist in ERP! " % invoice_no))
            elif not_found:
                continue
            else:
                ack_no = str(sh.row_values(row)[1] or '')
                ack_date = str(sh.row_values(row)[2] or '')
                irn_no = sh.row_values(row)[9]
                signed_qr = str(sh.row_values(row)[10])
                eway_no = sh.row_values(row)[11]
                

                vals = {'einv_ack' : ack_no or '',
                                  'einv_date' :ack_date or '',
                                  'einvoice_irn' : irn_no or '',
                                  'einv_eway_bill' : eway_no or '',
                                  'is_einvoice':True,
                                  }
                if signed_qr:
                    #qrcode = pyqrcode.create(str(signed_qr), error='Q', mode='binary')
                    buffer = BytesIO()
                    #qrcode.png(buffer)
                    qr = qrcode.QRCode()
                    qr.add_data(str(signed_qr))
                    #qr.make(fit=True)
                    img = qr.make_image()
                    img.save(buffer)
                    
                    qrb64 = base64.encodebytes(buffer.getvalue())

                    vals.update({ 'einv_signed_qrcode':signed_qr or '',
                                  'einv_base64_qrcode':qrb64,
                                  'einv_qrcode_name':str(invoice_no) + '_QRcode.png',})
                    
                inv_id.write(vals)
        if not_found:
            raise Warning(_("Following Invoices do not exist in ERP, Please fix them and Import the sheet again! \n %s" % ', '.join(not_found)))
                