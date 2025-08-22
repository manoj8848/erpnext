from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.payment_reconciliation_allocation.payment_reconciliation_allocation import (
	PaymentReconciliationAllocation,
)


class TestPaymentReconciliationPayment(FrappeTestCase):
	def test_get_list_is_callable_for_allocation_TC_ACC_212(self):
		# Call the static method with dummy args,Since method does nothing, No use of  assert
		PaymentReconciliationAllocation.get_list(args={})
