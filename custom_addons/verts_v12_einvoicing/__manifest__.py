# -*- coding: utf-8 -*-



{
    'name': "E-Invoicing under GST Through GSP(Binary Semantics).",

    'summary': """
        Module Uploads E-Invoices under GST through GSP(Binary Semantics)""",

    'description': """
        Module Uploads E-Invoices under GST through GSP(Binary Semantics)
    """,

    'author': "VERTS Services India Pvt. Ltd.",
    'website': "http://www.verts.co.in",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Invoicing Management',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','account','uom','product'],

    "images": [
        'static/description/icon.png'
    ],
    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'wizard/ewb_cancel_views.xml',
        'views/api_config_view.xml',

        'views/invoice_imp_view.xml',
        'views/sale_purchase_gst_views.xml',
        'views/templates.xml',
        'data/data.xml',
'views/views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
