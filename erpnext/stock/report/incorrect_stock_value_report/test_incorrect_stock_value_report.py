import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days
from erpnext.stock.report.incorrect_stock_value_report.incorrect_stock_value_report import get_data, execute
from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company
from erpnext.stock.doctype.item.test_item import create_item
from erpnext.stock.doctype.stock_entry.test_stock_entry import get_or_create_fiscal_year
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse


class TestIncorrectStockValueReport(FrappeTestCase): 
    def setUp(self):
        self.company = create_company("_Test Company")
        self.company = "_Test Company"
        self.warehouse = create_warehouse(warehouse_name="_Test Warehouse - _TC", company=self.company)

        self.item_code = create_item(
            item_code="_Test Item",
            valuation_rate=100,
            warehouse=self.warehouse,
            company=self.company,
            has_batch_no=1,
        )

        get_or_create_fiscal_year(self.company)

        self.account = "Stock In Hand - _TC"

        self.sle_date = add_days(today(), -3)

        self.batch = self.create_batch("BATCH-001", self.item_code, self.warehouse)

        # Pass batch no in stock entry
        self.stock_entry = self.create_stock_entry(self.item_code, self.warehouse, 100, self.batch.name)
        self.stock_entry2 = self.create_stock_entry(self.item_code, self.warehouse, 10, self.batch.name)

        print("stock1",self.stock_entry)
        print("stock2",self.stock_entry2)


        # SLE 1: Valid stock value
        frappe.get_doc({
            "doctype": "Stock Ledger Entry",
            "voucher_type": "Stock Entry",
            "voucher_no": self.stock_entry,
            "item_code": self.item_code,
            "actual_qty": 100,
            "posting_date": self.sle_date,
            "posting_time": "09:00:00",
            "company": self.company,
            "warehouse": self.warehouse,
            "stock_value_difference": 1000,
            "stock_value": 1000,
            "is_cancelled": 0
        }).insert(ignore_permissions=True)

        # SLE 2: Mismatched stock value to create a difference
        frappe.get_doc({
            "doctype": "Stock Ledger Entry",
            "voucher_type": "Stock Entry",
            "voucher_no": self.stock_entry2,
            "item_code": self.item_code,
            "actual_qty": 10,
            "posting_date": add_days(self.sle_date, 1),
            "posting_time": "10:00:00",
            "company": self.company,
            "warehouse": self.warehouse,
            "stock_value_difference": 100,
            "stock_value": 1200,  # should be 1100 if synced
            "is_cancelled": 0
        }).insert(ignore_permissions=True)

    def test_execute_returns_columns_and_data(self):
        filters = {
            "company": self.company,
            "account": self.account,
            "from_date": self.sle_date
        }
        columns, data = execute(filters)
        print("data",data)
        self.assertTrue(columns, "Report should return columns")
        self.assertIsInstance(columns, list, "Columns should be a list")
        self.assertIsInstance(data, list, "Data should be a list")

    def test_get_data_detects_unsync(self):
        filters = {
            "company": self.company,
            "account": self.account,
            "from_date": self.sle_date
        }
        result = get_data(filters)
        print("result",result)

        self.assertTrue(result, "Expected at least one mismatch row in the report result")
        for row in result:
            self.assertIn("difference_value", row)
            self.assertGreater(abs(row["difference_value"]), 0.1)
            self.assertIn("expected_stock_value", row)

    
    def test_get_data_filters_and_calculates_correctly(self):
        filters = {
            "company": self.company,
            "account": self.account,
            "from_date": self.sle_date
        }

        # Directly invoke get_data to test filtering and calculation logic
        data = get_data(filters)

        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 0, "Expected at least one row due to mismatch")

        for row in data:
            self.assertIn("item_code", row)
            self.assertEqual(row["item_code"], self.item_code)

            self.assertIn("warehouse", row)
            self.assertEqual(row["warehouse"], self.warehouse)

            self.assertIn("stock_value", row)
            self.assertIn("expected_stock_value", row)
            self.assertIn("difference_value", row)

            # Validate mismatch condition
            calculated_expected = row["expected_stock_value"]
            actual_stock_value = row["stock_value"]
            self.assertAlmostEqual(
                row["difference_value"],
                abs(actual_stock_value - calculated_expected),
                delta=0.01,
                msg="Difference value must match computed mismatch"
            )



    def create_batch(self, batch_name, item_code, warehouse):
        if not frappe.db.exists("Batch", batch_name):
            batch_doc = frappe.get_doc({
                "doctype": "Batch",
                "batch_id": batch_name,
                "item": item_code.name if hasattr(item_code, "name") else item_code,
                "warehouse": warehouse
            })
            batch_doc.insert()
            return batch_doc
        return frappe.get_doc("Batch", batch_name)

    def create_stock_entry(self, item_code, warehouse, qty, batch_no):
        entry = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "company": self.company,
            "posting_date": today(),
            "items": [{
                "item_code": item_code.name if hasattr(item_code, "name") else item_code,
                "qty": qty,
                "t_warehouse": warehouse,
                "batch_no": batch_no,    # Assign batch no here
            }]
        })
        entry.insert()
        entry.submit()
        return entry.name