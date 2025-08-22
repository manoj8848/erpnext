from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.payment_reconciliation_invoice.payment_reconciliation_invoice import (
	PaymentReconciliationInvoice,
)


class TestPaymentReconciliationPayment(FrappeTestCase):
	def test_get_list_is_callable_for_invoice_TC_ACC_213(self):
		# Call the static method with dummy args,Since method does nothing, No use of  assert
		PaymentReconciliationInvoice.get_list(args={})
