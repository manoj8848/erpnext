import frappe
from frappe.utils import add_days, today

from erpnext.stock.report.batch_item_expiry_status.batch_item_expiry_status import execute


class TestExpiryReportValidateFilters(frappe.tests.utils.FrappeTestCase):
	def test_missing_all_filters_T_BIES_001(self):
		# No filters passed
		with self.assertRaises(frappe.ValidationError) as cm:
			execute({})
		self.assertIn("Please select the required filters", str(cm.exception))

	def test_missing_from_date_T_BIES_002(self):
		# Only to_date provided
		filters = {"to_date": today()}
		with self.assertRaises(frappe.ValidationError) as cm:
			execute(filters)
		self.assertIn("'From Date' is required", str(cm.exception))

	def test_missing_to_date_T_BIES_003(self):
		# Only from_date provided
		filters = {"from_date": today()}
		with self.assertRaises(frappe.ValidationError) as cm:
			execute(filters)
		self.assertIn("'To Date' is required", str(cm.exception))

	def test_valid_filters_T_BIES_004(self):
		# All required filters provided, should not raise
		filters = {
			"from_date": today(),
			"to_date": add_days(today(), 10),
		}
		# Should not raise any ValidationError
		try:
			columns, data = execute(filters)
		except frappe.ValidationError:
			self.fail("execute() raised ValidationError unexpectedly!")
