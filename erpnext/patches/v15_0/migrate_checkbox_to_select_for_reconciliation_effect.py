import frappe
def execute():
	"""
	A New select field 'reconciliation_takes_effect_on' has been added to control Advance Payment Reconciliation dates.
	Migrate old checkbox configuration to new select field on 'Company' and 'Payment Entry'
	"""
	companies = frappe.db.get_all("Company", fields=["name", "reconciliation_takes_effect_on"])
	for x in companies:
		new_value = (
			"Advance Payment Date" if x.reconcile_on_advance_payment_date else "Oldest Of Invoice Or Advance"
		)
		frappe.db.set_value("Company", x.name, "reconciliation_takes_effect_on", new_value)
	frappe.db.sql(
		"""
		UPDATE `tabPayment Entry` 
		SET advance_reconciliation_takes_effect_on = 
			CASE 
				WHEN reconcile_on_advance_payment_date = 0 
				THEN 'Oldest Of Invoice Or Advance' 
				ELSE 'Advance Payment Date' 
			END
		"""
	)