import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Coalesce

def execute():
    invoice_types = ["Sales Invoice", "Purchase Invoice"]
    for invoice_type in invoice_types:
        invoice = DocType(invoice_type)
        invoice_details = (
            frappe.qb.from_(invoice)
            .select(invoice.conversion_rate, invoice.name)
            .as_("inv")
        )

        update_payment_schedule(invoice_details)

def update_payment_schedule(invoice_details):
    ps = DocType("Payment Schedule")

    query = (
        frappe.qb.update(ps)
        .set(ps.base_paid_amount, Coalesce(ps.paid_amount, 0) * invoice_details.conversion_rate)
        .set(ps.base_outstanding, Coalesce(ps.outstanding, 0) * invoice_details.conversion_rate)
        .from_(invoice_details)
        .where(ps.parent == invoice_details.name)
    )

    query.run()
