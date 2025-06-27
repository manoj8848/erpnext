import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days

import erpnext.stock.report.incorrect_stock_value_report.incorrect_stock_value_report as report


class TestStockGLMismatchReport(FrappeTestCase):
    def setUp(self):
        self.company = "Test Company"
        self.account = "Stock In Hand - TC"
        self.filters = {
            "company": self.company,
            "account": self.account,
            "from_date": str(today())
        }

        # Monkey patch ERPNext utilities (no unittest.mock)
        self._original_is_perpetual_inventory_enabled = report.erpnext.is_perpetual_inventory_enabled
        self._original_get_stock_and_account_balance = report.get_stock_and_account_balance
        self._original_get_stock_value_on = report.get_stock_value_on
        self._original_frappe_qb = report.frappe.qb.from_

    def tearDown(self):
        # Restore patched methods
        report.erpnext.is_perpetual_inventory_enabled = self._original_is_perpetual_inventory_enabled
        report.get_stock_and_account_balance = self._original_get_stock_and_account_balance
        report.get_stock_value_on = self._original_get_stock_value_on
        report.frappe.qb.from_ = self._original_frappe_qb

    def test_perpetual_inventory_required(self):
        report.erpnext.is_perpetual_inventory_enabled = lambda company: False
        with self.assertRaises(frappe.ValidationError):
            report.execute(self.filters)

    def test_execute_with_mocked_data(self):
        report.erpnext.is_perpetual_inventory_enabled = lambda company: True
        report.get_data = lambda filters: [{"item_code": "ITEM-001", "difference_value": 100}]
        columns, data = report.execute(self.filters)

        self.assertTrue(columns)
        self.assertTrue(data)
        self.assertIn("item_code", data[0])

    # def test_get_unsync_date_detects_mismatch(self):
    #     # Patch query and balances
    #     report.frappe.qb.from_ = lambda table: DummyQB(today())
    #     report.get_stock_and_account_balance = lambda **kwargs: (1000, 800, [])

    #     unsync_date = report.get_unsync_date(self.filters)
    #     self.assertEqual(str(unsync_date), str(today()))

    # def test_get_unsync_date_no_mismatch(self):
    #     report.frappe.qb.from_ = lambda table: DummyQB(today())
    #     report.get_stock_and_account_balance = lambda **kwargs: (1000, 1000, [])

    #     unsync_date = report.get_unsync_date(self.filters)
    #     self.assertIsNone(unsync_date)

    def test_get_data_with_difference(self):
        # Setup dummy SLE record
        mock_data = [{
            "name": "SLE-0001",
            "posting_date": str(today()),
            "posting_time": "12:00:00",
            "voucher_type": "Purchase Receipt",
            "voucher_no": "PR-0001",
            "stock_value_difference": 200,
            "stock_value": 1300,
            "warehouse": "Main Warehouse",
            "item_code": "ITEM-001",
        }]

        report.frappe.qb.from_ = lambda table: DummyQB(today(), mock_data)
        report.get_stock_value_on = lambda posting_date, item_code, warehouses: 1000

        report.get_unsync_date = lambda filters: str(today())
        self.filters["from_date"] = str(today())

        result = report.get_data(self.filters)
        self.assertEqual(len(result), 1)
        # self.assertEqual(result[0]["expected_stock_value"], 1200)
        # self.assertEqual(result[0]["difference_value"], 100)

    # def test_get_columns_has_expected_fields(self):
    #     columns = report.get_columns(self.filters)
    #     expected_fields = {
    #         "name", "posting_date", "posting_time", "voucher_type", "voucher_no",
    #         "item_code", "warehouse", "expected_stock_value", "stock_value", "difference_value"
    #     }
    #     found_fields = {col["fieldname"] for col in columns}
    #     self.assertTrue(expected_fields.issubset(found_fields))


# Helper class to simulate frappe.qb.from_().select().run()
class DummyQB:
    def __init__(self, date, run_data=None):
        self.date = date
        self.run_data = run_data or [[str(date)]]

    def select(self, *args, **kwargs):
        return self

    def run(self, **kwargs):
        return self.run_data

    def where(self, *args, **kwargs):
        return self

    def orderby(self, *args, **kwargs):
        return self