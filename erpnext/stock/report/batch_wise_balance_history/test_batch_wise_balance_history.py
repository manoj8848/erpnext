import unittest
import frappe
from frappe import _dict
from frappe.utils import getdate, nowdate, add_days, now_datetime
from erpnext.stock.doctype.item.test_item import create_item
from erpnext.stock.doctype.stock_entry.test_stock_entry import make_stock_entry
from erpnext.stock.report.batch_wise_balance_history import batch_wise_balance_history
from erpnext.stock.doctype import repost_item_valuation
import importlib


class TestBatchWiseBalanceHistoryReport(unittest.TestCase):
    def setUp(self):
        super().setUp()
        importlib.reload(repost_item_valuation)
        self.item = create_item(item_code="Test Batch Item", is_stock_item=1, valuation_rate=100)
        self.item.has_batch_no = 1
        self.item.save()
        self.warehouse = "_Test Warehouse - _TC"
        self.batch = self.make_batch(self.item)
        self.company = "_Test Company"

        posting_datetime = now_datetime()
        posting_date = posting_datetime.date()
        posting_time = posting_datetime.time()

        make_stock_entry(
            item=self.item.name,
            qty=10,
            rate=100,
            posting_date=posting_date,
            posting_time=posting_time,
            to_warehouse=self.warehouse,
            batch_no=self.batch,
        )

        make_stock_entry(
            item=self.item.name,
            qty=5,
            rate=100,
            posting_date=posting_date,
            posting_time=posting_time,
            to_warehouse=self.warehouse,
            batch_no=self.batch,
        )

        make_stock_entry(
            item=self.item.name,
            qty=3,
            rate=100,
            posting_date=posting_date,
            posting_time=posting_time,
            from_warehouse=self.warehouse,
            batch_no=self.batch,
        )

        self.from_date = add_days(posting_datetime.date(), -3)
        self.to_date = posting_datetime.date()

    def make_batch(self, item_code):
        from frappe.utils import nowdate
        batch = frappe.get_doc({
            "doctype": "Batch",
            "item": item_code,
            "batch_id": f"TEST-BATCH-{frappe.utils.now_datetime().timestamp()}",
            "manufacturing_date": nowdate(),
        }).insert()
        return batch.name

    def test_report_data_T_BWBH_001(self):
        filters = _dict({
            "item_code": self.item.name,
            "warehouse": self.warehouse,
            "batch_no": self.batch,
            "company": self.company,
            "from_date": self.from_date,
            "to_date": self.to_date,
        })
        columns, data = batch_wise_balance_history.execute(filters)

        self.assertTrue(data)
        record = data[0]

        self.assertEqual(record[0], self.item.name)
        self.assertEqual(record[3], self.warehouse)
        self.assertEqual(record[4], self.batch)
        self.assertEqual(record[6], 15)  # In Qty
        self.assertEqual(record[7], 3)   # Out Qty
        self.assertEqual(record[8], 12)  # Balance Qty = 10 + 5 - 3

    def test_invalid_date_range_T_BWBH_002(self):
        filters = _dict({
            "from_date": self.to_date,
            "to_date": self.from_date,
        })
        with self.assertRaises(frappe.ValidationError):
            batch_wise_balance_history.execute(filters)

    def test_missing_required_filters_T_BWBH_003(self):
        # More than 100k entries case can't be triggered easily, just check missing filters
        filters = _dict({
            "from_date": self.from_date,
            "to_date": self.to_date,
        })
        batch_wise_balance_history.execute(filters)  # Should not raise error

    def test_report_with_no_data_T_BWBH_004(self):
        filters = _dict({
            "item_code": "Nonexistent Item",
            "from_date": self.from_date,
            "to_date": self.to_date,
        })
        columns, data = batch_wise_balance_history.execute(filters)
        self.assertEqual(len(data), 0)

    def test_columns_T_BWBH_005(self):
        filters = _dict({
            "from_date": self.from_date,
            "to_date": self.to_date,
        })
        columns, _ = batch_wise_balance_history.execute(filters)
        expected_titles = ["Item", "Item Name", "Description", "Warehouse", "Batch", "Opening Qty", "In Qty", "Out Qty", "Balance Qty", "UOM"]
        self.assertTrue(all(any(col.startswith(title) for col in columns) for title in expected_titles))
