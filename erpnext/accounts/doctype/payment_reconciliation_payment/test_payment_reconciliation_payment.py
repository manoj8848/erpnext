from frappe.tests.utils import FrappeTestCase
from erpnext.accounts.doctype.payment_reconciliation_payment.payment_reconciliation_payment import PaymentReconciliationPayment

class TestPaymentReconciliationPayment(FrappeTestCase):
	
    def test_get_list_is_callable_for_payment_TC_ACC_214(self):
        # Call the static method with dummy args,Since method does nothing, No use of  assert
        PaymentReconciliationPayment.get_list(args={})
