# Copyright (c) 2024, VINOD GAJJALA and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestPaymentReconciliationRecord(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_on_cancel_raises_error_TC_ACC_215(self):
		# Create a test PaymentReconciliationRecord
		doc = frappe.get_doc({"doctype": "Payment Reconciliation Record", "title": "Test Cancellation Block"})
		doc.insert()
		doc.submit()
		doc.reload()

		# Attempt to cancel and assert that the correct exception message is thrown
		with self.assertRaises(frappe.ValidationError) as cm:
			doc.cancel()

		self.assertIn("Cancelling records is not allowed", str(cm.exception))
