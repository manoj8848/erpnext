import frappe
from frappe import _


def get_data():
	non_standard_fieldnames = {
			"Purchase Invoice": "purchase_receipt",
			"Landed Cost Voucher": "receipt_document",
			"Auto Repeat": "reference_document",
			"Purchase Receipt": "return_against",
			"Stock Reservation Entry": "from_voucher_no",
			"Quality Inspection": "reference_name",
		}
	transactions = [
		{
			"label": _("Related"),
			"items": ["Purchase Invoice", "Landed Cost Voucher", "Stock Reservation Entry"],
		},
		{
			"label": _("Reference"),
			"items": ["Material Request", "Purchase Order", "Quality Inspection"],
		},
		{"label": _("Returns"), "items": ["Purchase Receipt"]},
		{"label": _("Subscription"), "items": ["Auto Repeat"]},
	]

	if "assets" in frappe.get_installed_apps():
		non_standard_fieldnames.update({
			"Asset": "purchase_receipt"
		})
		transactions[0]["items"].insert(2, "Asset") 

	return {
		"fieldname": "purchase_receipt_no",
		"non_standard_fieldnames": non_standard_fieldnames,
		"internal_links": {
			"Material Request": ["items", "material_request"],
			"Purchase Order": ["items", "purchase_order"],
		},
		"transactions": transactions,
	}
