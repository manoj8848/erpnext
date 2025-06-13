import unittest
import frappe

class TestSupplierSalesAnalyticsReport(unittest.TestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        from frappe.model.meta import get_meta
        meta = get_meta("Repost Accounting Ledger Settings")
        settings = frappe.get_single("Repost Accounting Ledger Settings")
        if any(df.fieldname == "allowed_types" for df in meta.get("fields")):
            if not any(d.document_type == "Purchase Invoice" for d in settings.allowed_types):
                settings.append("allowed_types", {
					"document_type": "Purchase Invoice",
					"allowed": 1
				})
                settings.save(ignore_permissions=True)
        from erpnext.buying.doctype.supplier.test_supplier import create_supplier
        from erpnext.stock.doctype.item.test_item import create_item
        from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice
        
        self.supplier_a = create_supplier(supplier_name="Test Supplier A")
        self.supplier_b = create_supplier(supplier_name="Test Supplier B")
        
        self.item1 = create_item(item_code="TEST-ITEM-001", is_stock_item=1)
        self.item2 = create_item(item_code="TEST-ITEM-002", is_stock_item=1)
        
        self.pi1 = make_purchase_invoice(
            supplier=self.supplier_a.name,
            item_code=self.item1.name,
            update_stock=True,
            qty=2,
            rate=100
		)
        self.pi1.submit()
        
        self.pi2 = make_purchase_invoice(
			supplier=self.supplier_b.name,
			item_code=self.item2.name,
			update_stock=True,
			qty=3,
			rate=150
		)
        self.pi2.submit()

    def test_supplier_filter_and_invoice_handling(self):
        from erpnext.stock.report.supplier_wise_sales_analytics.supplier_wise_sales_analytics import get_suppliers_details

        filters = frappe._dict({"supplier": self.supplier_a.name})
        supplier_map = get_suppliers_details(filters)

        self.assertIn(self.item1.name, supplier_map, f"{self.item1.name} should appear for {self.supplier_a.name}")
        self.assertNotIn(self.item2.name, supplier_map, f"{self.item2.name} should not appear for {self.supplier_a.name}")

    def tearDown(self):
        frappe.db.rollback()
