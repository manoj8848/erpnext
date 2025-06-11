import unittest
import frappe

class TestSupplierSalesAnalyticsReport(unittest.TestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.allow_reposting_for_purchase_invoice()

        # Create two suppliers
        from erpnext.buying.doctype.supplier.test_supplier import create_supplier
        self.supplier_a = create_supplier(supplier_name="Test Supplier A")
        self.supplier_b = create_supplier(supplier_name="Test Supplier B")

        # Create two items
        from erpnext.stock.doctype.item.test_item import create_item
        self.item1 = create_item(item_code="TEST-ITEM-001", is_stock_item=1)
        self.item2 = create_item(item_code="TEST-ITEM-002", is_stock_item=1)

        # Create Purchase Invoices with update_stock=True
        from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice

        self.pi1 = make_purchase_invoice(
            supplier=self.supplier_a.name,
            item_code=self.item1.name,
            update_stock=True,
            qty=2,
            rate=100
        )
        self.pi1.flags.ignore_validate_update_after_submit = True
        self.pi1.submit()

        self.pi2 = make_purchase_invoice(
            supplier=self.supplier_b.name,
            item_code=self.item2.name,
            update_stock=True,
            qty=3,
            rate=150
        )
        self.pi2.flags.ignore_validate_update_after_submit = True
        self.pi2.submit()

    def allow_reposting_for_purchase_invoice(self):
        from erpnext.accounts.doctype.repost_accounting_ledger_settings.repost_accounting_ledger_settings import (
            get_repost_accounting_ledger_settings,
        )

        settings = get_repost_accounting_ledger_settings()
        if "Purchase Invoice" not in settings.allowed_for_repost:
            settings.allowed_for_repost.append("Purchase Invoice")
            settings.save(ignore_permissions=True)

    def test_supplier_filter_and_invoice_handling(self):
        from erpnext.stock.report.supplier_wise_sales_analytics.supplier_wise_sales_analytics import get_suppliers_details

        # Filters with only supplier A — item2 should be filtered out
        filters = frappe._dict({"supplier": self.supplier_a.name})

        supplier_map = get_suppliers_details(filters)

        # Only item1 should remain
        self.assertIn(self.item1.name, supplier_map, f"{self.item1.name} should be in report for {self.supplier_a.name}")
        self.assertNotIn(self.item2.name, supplier_map, f"{self.item2.name} should not be in report for {self.supplier_a.name}")

    def tearDown(self):
		frappe.db.rollback()
