import frappe
from frappe.utils import today, add_days
from frappe.tests.utils import FrappeTestCase

from erpnext.buying.report.purchase_order_analysis.purchase_order_analysis import execute

class TestPurchaseOrderAnalysis(FrappeTestCase):
	def setUp(self):
		po = create_purchase_order()
		po.submit()

		self.filters = frappe._dict(
			company = po.company,
			from_date = add_days(today(), -30),
			to_date = today(),
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_purchase_order_analysis_report(self):
		self.filters.update(
			{
				"status": ["To Receive and Bill"],
				"group_by_po": 1
			}
		)

		data = execute(self.filters)
		report_data = data[1][0]

		self.assertEqual(report_data.get("status"), "To Receive and Bill")
		self.assertEqual(report_data.get("supplier"), "_Test Supplier")
		self.assertEqual(report_data.get("item_code"), "_Test Item")
		self.assertEqual(report_data.get("qty"), 10)
		self.assertEqual(report_data.get("received_qty"), 0)
		self.assertEqual(report_data.get("pending_qty"), 10)
		self.assertEqual(report_data.get("billed_qty"), 0)
		self.assertEqual(report_data.get("amount"), 5000)
		self.assertEqual(report_data.get("billed_amount"), 0)
		self.assertEqual(report_data.get("pending_amount"), 5000)
		self.assertEqual(report_data.get("company"), "_Test Company")
		self.assertEqual(report_data.get("received_qty_amount"), 0)
		self.assertEqual(report_data.get("qty_to_bill"), 10)

	def test_validate_filters_codecov(self):
		self.filters.update({"from_date": ""})

		with self.assertRaises(frappe.ValidationError):
			execute(self.filters)

		self.filters.update({"from_date": today(),"to_date": add_days(today(), -1)})

		with self.assertRaises(frappe.ValidationError):
			execute(self.filters)

		self.filters = {}
		data = execute(self.filters)
		self.assertEqual(len(data[1]), 0)


def create_purchase_order():
	po = frappe.copy_doc(test_records[0]).insert()
	po = frappe.get_doc("Purchase Order", po.name)
	po.transaction_date = today()
	po.schedule_date = today()
	po.items[0].schedule_date = today()
	po.save()

	return po

test_records = frappe.get_test_records("Purchase Order")