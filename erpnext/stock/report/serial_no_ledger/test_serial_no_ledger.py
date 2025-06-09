from types import SimpleNamespace
import frappe
from frappe.tests.utils import FrappeTestCase
import erpnext.stock.report.serial_no_ledger.serial_no_ledger as snl


class TestSerialNoLedger(FrappeTestCase):
    def setUp(self):
        self.filters = {}

    def test_get_columns(self):
        columns = snl.get_columns(self.filters)
        self.assertIsInstance(columns, list)
        self.assertTrue(any(isinstance(col, dict) and col.get("fieldname") == "posting_date" for col in columns))

    # def test_get_serial_nos_no_filter(self):
    #     def fake_get_all(doctype, fields, filters, order_by):
    #         self.assertIn("parent", filters)
    #         return [
    #             {"serial_no": "SN-003", "parent": "bundle-1", "stock_value_difference": 20},
    #             {"serial_no": "SN-004", "parent": "bundle-1", "stock_value_difference": 30},
    #         ]

    #     frappe.get_all = fake_get_all
    #     serial_bundle_ids = ["bundle-1", "bundle-2"]
    #     serial_nos = snl.get_serial_nos({}, serial_bundle_ids)
    #     self.assertIn("bundle-1", serial_nos)

    def test_get_data_no_stock_ledgers(self):
        snl.get_stock_ledger_entries = lambda filters, to_date, order, check_serial_no: []
        data = snl.get_data({})
        self.assertEqual(data, [])

    # def test_get_data_with_stock_ledger(self):
    #     sle = SimpleNamespace(
    #         posting_date="2025-01-01",
    #         posting_time="12:00:00",
    #         voucher_type="Purchase Invoice",
    #         voucher_no="PINV-0001",
    #         actual_qty=5,
    #         company="TestCo",
    #         warehouse="WH-001",
    #         serial_no="SN-001,SN-002",
    #         serial_and_batch_bundle="bundle-1",
    #         stock_value_difference=50,
    #     )

    #     snl.get_stock_ledger_entries = lambda filters, to_date, order, check_serial_no: [sle]
    #     snl.get_serial_nos = lambda filters, bundle_ids: {
    #         "bundle-1": [
    #             {"serial_no": "SN-003", "valuation_rate": 20},
    #             {"serial_no": "SN-004", "valuation_rate": 30},
    #         ]
    #     }

    #     frappe.db.get_value = lambda dt, dn, fld, **kwargs: "Test Supplier" if fld == "supplier" else None

    #     filters = {"serial_no": "SN-001"}
    #     data = snl.get_data(filters)

    #     self.assertTrue(any(d.get("serial_no") == "SN-001" for d in data))
    #     self.assertTrue(any(d.get("serial_no") == "SN-003" for d in data))
    #     self.assertTrue(any(d.get("qty") == 1 for d in data))

    def test_execute(self):
        filters = {"item_code": "ITEM-001"}
        columns, data = snl.execute(filters)
        self.assertIsInstance(columns, list)
        self.assertIsInstance(data, list)

    def test_get_data_division_by_zero(self):
        sle = SimpleNamespace(
            posting_date="2025-01-01",
            posting_time="12:00:00",
            voucher_type="Purchase Invoice",
            voucher_no="PINV-0001",
            actual_qty=1,
            company="TestCo",
            warehouse="WH-001",
            serial_no="SN-001",
            serial_and_batch_bundle=None,
            stock_value_difference=0,
        )

        snl.get_stock_ledger_entries = lambda filters, to_date, order, check_serial_no: [sle]
        snl.get_serial_nos = lambda filters, bundle_ids: {}
        frappe.db.get_value = lambda dt, dn, fld, **kwargs: None

        filters = {}
        data = snl.get_data(filters)
        self.assertTrue(all("valuation_rate" in d for d in data))

    def test_get_data_no_serial_no_and_no_bundle(self):
        sle = SimpleNamespace(
            posting_date="2025-01-01",
            posting_time="12:00:00",
            voucher_type="Other Voucher",
            voucher_no="OV-0001",
            actual_qty=10,
            company="TestCo",
            warehouse="WH-001",
            serial_no=None,
            serial_and_batch_bundle=None,
            stock_value_difference=100,
        )
        snl.get_stock_ledger_entries = lambda filters, to_date, order, check_serial_no: [sle]
        snl.get_serial_nos = lambda filters, bundle_ids: {}
        frappe.db.get_value = lambda dt, dn, fld, **kwargs: None

        data = snl.get_data({})
        self.assertEqual(len(data), 0)

    def test_get_data_party_field_none(self):
        sle = SimpleNamespace(
            posting_date="2025-01-01",
            posting_time="12:00:00",
            voucher_type="Random Voucher",
            voucher_no="RV-0001",
            actual_qty=3,
            company="TestCo",
            warehouse="WH-001",
            serial_no="SN-005",
            serial_and_batch_bundle=None,
            stock_value_difference=30,
        )
        snl.get_stock_ledger_entries = lambda filters, to_date, order, check_serial_no: [sle]
        snl.get_serial_nos = lambda filters, bundle_ids: {}
        frappe.db.get_value = lambda dt, dn, fld, **kwargs: None

        data = snl.get_data({})
        self.assertEqual(data[0].get("party"), None)
        self.assertEqual(data[0].get("party_type"), None)
