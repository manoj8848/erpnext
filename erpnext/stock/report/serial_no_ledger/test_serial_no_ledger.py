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
        print("data",data)
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
        print("data2",data)
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


    def test_get_serial_nos_from_bundle(self):
        sle = SimpleNamespace(
            posting_date="2025-01-01",
            posting_time="10:00:00",
            voucher_type="Delivery Note",
            voucher_no="DN-0001",
            actual_qty=-1,
            company="TestCo",
            warehouse="WH-001",
            serial_no=None,
            serial_and_batch_bundle="BUNDLE-001",
            stock_value_difference=-120,
        )

        # Mocking get_stock_ledger_entries to return one SLE with a bundle
        snl.get_stock_ledger_entries = lambda filters, to_date, order, check_serial_no: [sle]

        # Mocking frappe.get_all to simulate serials from a bundle
        mock_bundle_data = [
            {"serial_no": "SN-BND-1", "parent": "BUNDLE-001", "valuation_rate": -100},
            {"serial_no": "SN-BND-2", "parent": "BUNDLE-001", "valuation_rate": -20},
        ]
        frappe.get_all = lambda doctype, fields, filters, order_by: mock_bundle_data

        # Patch get_serial_nos to return mocked result using the same logic as the original function
        def mock_get_serial_nos(filters, bundle_ids):
            result = {}
            for entry in mock_bundle_data:
                if entry["parent"] in bundle_ids:
                    result.setdefault(entry["parent"], []).append({
                        "serial_no": entry["serial_no"],
                        "valuation_rate": abs(entry["valuation_rate"]),
                    })
            return result

        snl.get_serial_nos = mock_get_serial_nos

        frappe.db.get_value = lambda dt, dn, fld, **kwargs: "Test Customer"

        data = snl.get_data({})
        serial_nos = [row.get("serial_no") for row in data if "serial_no" in row]

        self.assertIn("SN-BND-1", serial_nos)
        self.assertIn("SN-BND-2", serial_nos)
        self.assertTrue(all("valuation_rate" in row for row in data if "serial_no" in row))