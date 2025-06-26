from types import SimpleNamespace
import frappe
from frappe.tests.utils import FrappeTestCase
import erpnext.stock.report.serial_no_ledger.serial_no_ledger as snl


class TestSerialNoLedger(FrappeTestCase):
    def setUp(self):
        self.filters = {}

    def test_get_data_no_stock_ledgers(self):
        snl.get_stock_ledger_entries = lambda filters, to_date, order, check_serial_no: []
        data = snl.get_data({})
        self.assertEqual(data, [])

    def test_get_data_with_stock_ledger(self):
        sle = SimpleNamespace(
            posting_date="2025-01-01",
            posting_time="12:00:00",
            voucher_type="Purchase Invoice",
            voucher_no="PINV-0001",
            actual_qty=5,
            company="TestCo",
            warehouse="WH-001",
            serial_no="SN-001,SN-002",
            serial_and_batch_bundle="bundle-1",
            stock_value_difference=50,
        )

        snl.get_stock_ledger_entries = lambda filters, to_date, order, check_serial_no: [sle]
        snl.get_serial_nos = lambda filters, bundle_ids: {
            "bundle-1": [
                {"serial_no": "SN-003", "valuation_rate": 20},
                {"serial_no": "SN-004", "valuation_rate": 30},
            ]
        }

        frappe.db.get_value = lambda dt, dn, fld, **kwargs: "Test Supplier" if fld == "supplier" else None

        filters = {"serial_no": "SN-001"}
        data = snl.get_data(filters)

        self.assertTrue(any(d.get("serial_no") == "SN-001" for d in data))
        self.assertTrue(any(d.get("serial_no") == "SN-003" for d in data))
        self.assertTrue(any(d.get("qty") == 1 for d in data))

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

    def test_get_data_zero_actual_qty(self):
        sle = SimpleNamespace(
            posting_date="2025-01-01",
            posting_time="12:00:00",
            voucher_type="Purchase Receipt",
            voucher_no="PR-0001",
            actual_qty=0,
            company="TestCo",
            warehouse="WH-001",
            serial_no="SN-ZERO",
            serial_and_batch_bundle=None,
            stock_value_difference=0,
        )

        snl.get_stock_ledger_entries = lambda filters, to_date, order, check_serial_no: [sle]
        snl.get_serial_nos = lambda filters, bundle_ids: {}
        frappe.db.get_value = lambda dt, dn, fld, **kwargs: "Test Supplier"

        data = snl.get_data({})
        self.assertEqual(len(data), 1, "Should not include rows with zero actual_qty")

    def test_get_data_multiple_sles_with_serial_and_bundle(self):
        sle1 = SimpleNamespace(
            posting_date="2025-01-01",
            posting_time="12:00:00",
            voucher_type="Purchase Receipt",
            voucher_no="PR-001",
            actual_qty=2,
            company="TestCo",
            warehouse="WH-001",
            serial_no="SN-001\nSN-002",
            serial_and_batch_bundle=None,
            stock_value_difference=200,
        )

        sle2 = SimpleNamespace(
            posting_date="2025-01-02",
            posting_time="13:00:00",
            voucher_type="Delivery Note",
            voucher_no="DN-001",
            actual_qty=-1,
            company="TestCo",
            warehouse="WH-001",
            serial_no=None,
            serial_and_batch_bundle="BND-001",
            stock_value_difference=-100,
        )

        snl.get_stock_ledger_entries = lambda filters, to_date, order, check_serial_no: [sle1, sle2]

        snl.get_serial_nos = lambda filters, bundle_ids: {
            "BND-001": [{"serial_no": "SN-003", "valuation_rate": 100}]
        }

        frappe.db.get_value = lambda dt, dn, fld, **kwargs: "Test Supplier" if fld == "supplier" else "Test Customer"

        data = snl.get_data({})

        serials = [row.get("serial_no") for row in data]
        self.assertIn("SN-001", serials)
        self.assertIn("SN-002", serials)
        self.assertIn("SN-003", serials)
        self.assertEqual(sum(row.get("qty", 0) for row in data), 1)

    def test_real_get_serial_nos_logic(self):
        # Save original frappe.get_all to restore later
        original_get_all = frappe.get_all

        try:
            # Define a mock version of frappe.get_all
            def mock_get_all(doctype, fields=None, filters=None, order_by=None):
                self.assertEqual(doctype, "Serial and Batch Entry")
                self.assertEqual(
                    filters,
                    {"parent": ["in", ["BND-123", "BND-456"]]}
                )
                self.assertEqual(order_by, "idx asc")

                return [
                    {"serial_no": "SN-A", "parent": "BND-123", "valuation_rate": 50},
                    {"serial_no": "SN-B", "parent": "BND-123", "valuation_rate": -25},
                    {"serial_no": "SN-C", "parent": "BND-456", "valuation_rate": 0},
                ]

            # Replace frappe.get_all with mock
            frappe.get_all = mock_get_all

            # Import and call the function under test
            from erpnext.stock.report.serial_no_ledger.serial_no_ledger import get_serial_nos

            filters = {}
            bundle_ids = ["BND-123", "BND-456"]
            result = get_serial_nos(filters, bundle_ids)

            expected = {
                "BND-123": [
                    {"serial_no": "SN-A", "valuation_rate": 50},
                    {"serial_no": "SN-B", "valuation_rate": 25},
                ],
                "BND-456": [
                    {"serial_no": "SN-C", "valuation_rate": 0}
                ]
            }
            print("result",result)

            self.assertEqual(result, expected)

        finally:
            # Always restore original frappe.get_all
            frappe.get_all = original_get_all
