# -*- coding: utf-8 -*-
from odoo import http

# class VertsV12Einvoicing(http.Controller):
#     @http.route('/verts_v12_einvoicing/verts_v12_einvoicing/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/verts_v12_einvoicing/verts_v12_einvoicing/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('verts_v12_einvoicing.listing', {
#             'root': '/verts_v12_einvoicing/verts_v12_einvoicing',
#             'objects': http.request.env['verts_v12_einvoicing.verts_v12_einvoicing'].search([]),
#         })

#     @http.route('/verts_v12_einvoicing/verts_v12_einvoicing/objects/<model("verts_v12_einvoicing.verts_v12_einvoicing"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('verts_v12_einvoicing.object', {
#             'object': obj
#         })