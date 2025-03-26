import frappe


def execute():
	frappe.db.sql(
		"""
		UPDATE `tabStock Ledger Entry`
		SET posting_datetime = to_timestamp(posting_date || ' ' || posting_time, 'YYYY-MM-DD HH24:MI:SS')
		"""
	)