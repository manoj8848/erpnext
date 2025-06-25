# test_serial_and_batch_summary.py

import frappe
from frappe.tests.utils import FrappeTestCase
from erpnext.stock.report.serial_and_batch_summary.serial_and_batch_summary import execute, get_data, get_filter_conditions, get_columns
from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company

class TestSerialAndBatchSummary(FrappeTestCase):
    def setUp(self):
        # Use a real Company for testing
        self.company = create_company("_Test Company")

        self.base_filters = {"company": self.company}
        self.full_filters = {
                "voucher_type": "Purchase Receipt",
                "voucher_no": ["PR-0001", "PR-0002"],
                "item_code": "_Test Item",
                "warehouse": "_Test Warehouse",
                "company": "_Test Company",
                "from_date": "2023-01-01",
                "to_date": "2023-12-31",
                "serial_no": "S-123",
                "batch_no": "B-456"
            }

        # Stub get_data return for column tests
        self.stub_data = [
            {"item_code": "I1", "serial_no": "S1", "batch_no": "B1"}
        ]

    def test_execute_minimal(self):
        cols, data = execute(self.base_filters)
        self.assertTrue(isinstance(cols, list))
        self.assertTrue(isinstance(data, list))
        fnames = [c["fieldname"] for c in cols]
        self.assertIn("company", fnames)
        self.assertIn("name", fnames)
        self.assertIn("posting_date", fnames)
        # Unless special test data exists, data may be empty as long as it's the correct type

    # def test_execute_full_filters_columns(self):
    #     filters = {
    #         "company": self.company,
    #         "voucher_type": "Purchase Receipt",  # keep
    #         # "voucher_no": ["PB-0001", "PB-0002"],  # remove this
    #         "item_code": "_Test Item",
    #         "warehouse": "_Test Warehouse",
    #         "from_date": "2023-01-01",
    #         "to_date": "2023-12-31",
    #         "serial_no": "S-123",
    #         "batch_no": "B-123",
    #     }
    #     cols, _ = execute(filters)
    #     fnames = [c["fieldname"] for c in cols]

    #     self.assertIn("voucher_type", fnames)
    #     self.assertIn("voucher_no", fnames)
    #     self.assertIn("item_code", fnames)
    #     self.assertIn("item_name", fnames)
    #     self.assertIn("warehouse", fnames)
    #     self.assertIn("serial_no", fnames)
    #     self.assertIn("batch_no", fnames)
    #     self.assertIn("qty", fnames)

    def test_get_filter_conditions_all_fields(self):
        conds = get_filter_conditions(self.full_filters)

        # Basic mandatory filters
        self.assertIn(["Serial and Batch Bundle", "docstatus", "=", 1], conds)
        self.assertIn(["Serial and Batch Bundle", "is_cancelled", "=", 0], conds)

        expected_conditions = {
            ("Serial and Batch Bundle", "voucher_type", "="),
            ("Serial and Batch Bundle", "item_code", "="),
            ("Serial and Batch Bundle", "warehouse", "="),
            ("Serial and Batch Bundle", "company", "="),
            ("Serial and Batch Bundle", "voucher_no", "in"),
            ("Serial and Batch Bundle", "posting_date", "between"),
            ("Serial and Batch Entry", "serial_no", "="),
            ("Serial and Batch Entry", "batch_no", "="),
        }

        for doctype, fieldname, operator in expected_conditions:
            self.assertTrue(
                any(c[0] == doctype and c[1] == fieldname and c[2] == operator for c in conds),
                msg=f"Missing condition: {doctype}, {fieldname}, {operator}"
            )

    def test_get_data_returns_list_and_filters(self):
        # Mock frappe.get_all to ensure get_data returns our fields
        def fake_get_all(doctype, fields, filters, order_by=None):
            self.assertEqual(doctype, "Serial and Batch Bundle")
            self.assertIsInstance(fields, list)
            self.assertIsInstance(filters, list)
            return [
                {
                    "voucher_type": "Purchase Receipt",
                    "posting_date": "2023-06-01",
                    "name": "BND-1",
                    "company": self.company,
                    "voucher_no": "PB-0001",
                    "item_code": "I1",
                    "item_name": "Item One",
                    "serial_no": "S1",
                    "batch_no": "B1",
                    "warehouse": "_Test Warehouse",
                    "incoming_rate": 100.0,
                    "stock_value_difference": 10.0,
                    "qty": 2
                }
            ]

        frappe.get_all = fake_get_all

        data = get_data(self.full_filters)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["company"], self.company)
        self.assertEqual(row["serial_no"], "S1")
        self.assertEqual(row["qty"], 2)

    def test_get_columns_item_filter_logic(self):
        # If item_code filter is given, context auto-includes serial & batch
        cols = get_columns(self.base_filters | {"item_code": "ItemX"}, self.stub_data)
        fnames = [c["fieldname"] for c in cols]

        self.assertIn("serial_no", fnames)
        self.assertIn("batch_no", fnames)

    def test_get_columns_voucher_filter_logic(self):
        # If voucher_no filter given, voucher_type / voucher_no columns should be excluded
        cols = get_columns(self.base_filters | {"voucher_no": ["PB-0001"]}, self.stub_data)
        fnames = [c["fieldname"] for c in cols]
        self.assertNotIn("voucher_type", fnames)
        self.assertNotIn("voucher_no", fnames)

    def test_warehouse_column_logic(self):
        # Without warehouse filter, 'warehouse' column appears
        cols = get_columns(self.base_filters, self.stub_data)
        self.assertIn("warehouse", [c["fieldname"] for c in cols])

        # With warehouse filter, the column should be omitted
        cols2 = get_columns(self.base_filters | {"warehouse": "_Test Warehouse"}, self.stub_data)
        self.assertNotIn("warehouse", [c["fieldname"] for c in cols2])
