import frappe
from frappe.tests.utils import FrappeTestCase, change_settings
from frappe.utils import today

from erpnext.accounts.report.accounts_payable_summary.accounts_payable_summary import execute
from erpnext.accounts.test.accounts_mixin import AccountsTestMixin
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice

class TestAccountPaybale(AccountsTestMixin, FrappeTestCase):
    def setUp(self):
        self.maxDiff = None
        self.create_company()
        self.create_supplier()
        self.create_item()
        self.clear_old_entries()
        frappe.db.set_value(
			"Company",
			"_Test Company",
			"stock_received_but_not_billed",
			"Stock Received But Not Billed - _TC",
		)

    def teaDown(self):
        frappe.db.rollback()

    def test_01_account_payble_summary_report(self):
        """
		Test for Invoices, Paid, Advance and Outstanding
		"""
        pi = self.create_purchase_invoice()
        filters = {
			"company": self.company,
			"supplier": self.supplier,
			"posting_date": today(),
			"range1": 30,
			"range2": 60,
			"range3": 90,
			"range4": 120,
		}
        supplier_group = frappe.db.get_all(
			"Supplier",
			filters={"name": self.supplier},
			fields=["supplier_group"]
		)[0]
        report = execute(filters)
        rpt_output = report[1]
        expected_data = {
                "party_type": "Supplier",
                'party': self.supplier,
                'invoiced': 300.0,
                'paid': 0.0,
                'credit_note': 0.0,
                'outstanding': 300.0,
                'total_due': 300.0, 
                'future_amount': 0.0, 
                'sales_person': [], 
                'party_type': 'Supplier', 
                'range1': 300.0, 
                'range2': 0.0, 
                'range3': 0.0, 
                'range4': 0.0, 
                'range5': 0.0, 
                'currency': pi.currency, 
                'supplier_group': supplier_group.supplier_group, 
                'advance': 0
            }
        self.assertEqual(len(rpt_output), 1)
        self.assertEqual(rpt_output[0], expected_data)

        # simulate advance payment
        pe = get_payment_entry(pi.doctype, pi.name)
        pe.paid_amount = 150
        pe.references[0].allocated_amount = 0
        pe.save().submit()

        expected_data.update(
			{
				"advance": 150.0,
				"outstanding": 150.0,
				"range1": 150.0,
				"total_due": 150.0,
			}
		)
        report = execute(filters)
        rpt_output = report[1]
        self.assertEqual(len(rpt_output), 1)
        self.assertDictEqual(rpt_output[0], expected_data)

        # make partial payment
        pe = get_payment_entry(pi.doctype, pi.name)
        pe.paid_amount = 125
        pe.references[0].allocated_amount = 125
        pe.save().submit()

        expected_data.update(
			{"advance": 150.0, "paid": 125.0, "outstanding": 25.0, "range1": 25.0, "total_due": 25.0}
		)
        report = execute(filters)
        rpt_output = report[1]
        self.assertEqual(len(rpt_output), 1)
        self.assertDictEqual(rpt_output[0], expected_data)

    @change_settings("Buying Settings", {"supp_master_name": "Naming Series"})
    def test_02_various_filters_and_output(self):
        filters = {
			"company": self.company,
			"supplier": self.supplier,
			"posting_date": today(),
			"range1": 30,
			"range2": 60,
			"range3": 90,
			"range4": 120,
		}
        pi = self.create_purchase_invoice()
        pe = get_payment_entry(pi.doctype, pi.name)
        pe.paid_amount = 250
        pe.references[0].allocated_amount = 250
        pe.save().submit()

        supplier_group = frappe.db.get_all(
			"Supplier",
			filters={"name": self.supplier},
			fields=["supplier_group"]
		)[0]
        report = execute(filters)
        rpt_output = report[1]
        expected_data ={
                'party': self.supplier, 
                'party_name': self.supplier, 
                'invoiced': 300.0, 
                'paid': 250.0, 
                'credit_note': 0.0, 
                'outstanding': 50.0, 
                'total_due': 50.0, 
                'future_amount': 0.0, 
                'sales_person': [], 
                'party_type': 'Supplier', 
                'range1': 50.0, 
                'range2': 0.0, 
                'range3': 0.0, 
                'range4': 0.0, 
                'range5': 0.0, 
                'currency': pi.currency, 
                'supplier_group': supplier_group.supplier_group, 
                'advance': 0
            }
        self.assertEqual(len(rpt_output), 1)
        self.assertDictEqual(rpt_output[0], expected_data)
        
        # invoice fully paid
        pe = get_payment_entry(pi.doctype, pi.name).save().submit()
        report = execute(filters)
        rpt_output = report[1]
        self.assertEqual(len(rpt_output), 0)

    def create_purchase_invoice(self, do_not_submit=False):
        frappe.set_user("Administrator")
        pi = make_purchase_invoice(
			item=self.item,
			company=self.company,
			supplier=self.supplier,
			is_return=False,
			update_stock=False,
			posting_date=today(),
			do_not_save=1,
			rate=300,
			price_list_rate=300,
			qty=1,
		)
        pi = pi.save()
        if not do_not_submit:
            pi = pi.submit()
        return pi