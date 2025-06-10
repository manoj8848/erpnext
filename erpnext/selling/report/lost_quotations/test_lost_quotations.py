import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.selling.doctype.customer.test_customer import get_customer_dict
from erpnext.selling.doctype.quotation.test_quotation import make_quotation


class TestLostQuotations(FrappeTestCase):
	def setUp(self):
		item = make_test_item("Test Lost Quotation Item")
		self.item_code = item.item_code

		customer = frappe.get_doc(get_customer_dict("Test Lost Quotation Customer")).insert(
			ignore_permissions=True
		)
		self.customer = customer.name
		self.get_reason = self.setup_quotation_lost_reason()
		qo = make_quotation(
			item_code=self.item_code,
			customer=self.customer,
			transaction_date=add_days(today(), -4),
			do_not_save=1,
		)
		qo.insert(ignore_permissions=True)
		qo.declare_enquiry_lost(
			[{"lost_reason": self.get_reason.get("reason")}],
			[{"competitor": [self.get_reason.get("competitor")]}],
			"Test quotation Lost",
		)
		qo.submit()
		qo.reload()

		self.filters = {"company": qo.company, "timespan": "Last Week", "group_by": "Lost Reason"}

	def tearDown(self):
		frappe.db.rollback()

	def test_lost_quotation_report_TC_S_212(self):
		from .lost_quotations import execute

		data = execute(self.filters)
		if data[1]:
			for row in data[1]:
				print(row)
				if row[0] == self.get_reason.get("reason"):
					self.assertEqual(row[0], "__Test Quotation Lost Reason")
					self.assertEqual(row[1], 1)

		self.filters.update({"group_by": "Competitor"})
		data_1 = execute(self.filters)
		if data_1:
			for idx in data_1[1]:
				if idx[0] == "Not Specified":
					self.assertEqual(idx[1], 1)

	def setup_quotation_lost_reason(self):
		reason = "__Test Quotation Lost Reason"
		competitor = "__ Test Lost Competitor"
		if not frappe.db.exists("Quotation Lost Reason", reason):
			frappe.get_doc({"doctype": "Quotation Lost Reason", "order_lost_reason": reason}).insert(
				ignore_permissions=True
			)

		if not frappe.db.exists("Competitor", competitor):
			frappe.get_doc({"doctype": "Competitor", "competitor_name": competitor}).insert(
				ignore_permissions=True
			)

		return {"reason": reason, "competitor": competitor}
