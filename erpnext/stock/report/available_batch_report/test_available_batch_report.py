import frappe
from frappe.tests.utils import FrappeTestCase
from frappe._dict import _dict
from erpnext.stock.report.batchwise_balance_with_expiry.batchwise_balance_with_expiry import (
    execute,
    get_columns,
    get_data,
    parse_batchwise_data,
    get_batchwise_data_from_stock_ledger,
    get_batchwise_data_from_serial_batch_bundle,
    get_query_based_on_filters,
)
from frappe.utils import today, add_days


class TestAvailableBatchReport(FrappeTestCase):
    def setUp(self):
        # Create Item
        self.item = frappe.get_doc({
            "doctype": "Item",
            "item_code": "TestItem001",
            "item_name": "Test Item 001",
            "stock_uom": "Nos",
            "has_batch_no": 1,
            "is_stock_item": 1
        }).insert(ignore_permissions=True, ignore_if_duplicate=True)

        # Create Warehouse
        self.warehouse = frappe.get_doc({
            "doctype": "Warehouse",
            "warehouse_name": "Test Warehouse",
            "company": "_Test Company"
        }).insert(ignore_permissions=True, ignore_if_duplicate=True)

        # Create Batch
        self.batch = frappe.get_doc({
            "doctype": "Batch",
            "item": self.item.name,
            "batch_qty": 10,
            "expiry_date": add_days(today(), 10)
        }).insert(ignore_permissions=True, ignore_if_duplicate=True)

        # Create Stock Ledger Entry
        frappe.get_doc({
            "doctype": "Stock Ledger Entry",
            "item_code": self.item.name,
            "warehouse": self.warehouse.name,
            "batch_no": self.batch.name,
            "actual_qty": 10,
            "posting_date": today(),
            "is_cancelled": 0,
            "voucher_type": "Stock Entry",
            "voucher_no": "Test-Voucher"
        }).insert(ignore_permissions=True)

    def test_execute(self):
        columns, data = execute(_dict({
            "item_code": self.item.name,
            "show_item_name": 1,
            "include_expired_batches": 0,
            "to_date": today()
        }))
        self.assertTrue(columns)
        self.assertTrue(data)
        self.assertEqual(data[0]["item_code"], self.item.name)

    def test_get_columns_with_and_without_item_name(self):
        with_name = get_columns(_dict({"show_item_name": 1}))
        without_name = get_columns(_dict({"show_item_name": 0}))

        with_fields = [col["fieldname"] for col in with_name]
        without_fields = [col["fieldname"] for col in without_name]

        self.assertIn("item_name", with_fields)
        self.assertNotIn("item_name", without_fields)

    def test_get_data(self):
        filters = _dict({
            "item_code": self.item.name,
            "to_date": today(),
            "include_expired_batches": 0
        })
        data = get_data(filters)
        self.assertTrue(len(data) > 0)
        self.assertEqual(data[0].item_code, self.item.name)

    def test_parse_batchwise_data(self):
        raw_data = {
            ("ITEM-001", "WH-001", "BATCH-001"): _dict({
                "item_code": "ITEM-001",
                "warehouse": "WH-001",
                "batch_no": "BATCH-001",
                "balance_qty": 5
            }),
            ("ITEM-002", "WH-002", "BATCH-002"): _dict({
                "item_code": "ITEM-002",
                "warehouse": "WH-002",
                "batch_no": "BATCH-002",
                "balance_qty": 0
            })
        }
        result = parse_batchwise_data(raw_data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].item_code, "ITEM-001")

    def test_get_batchwise_data_from_stock_ledger(self):
        filters = _dict({"item_code": self.item.name})
        data = get_batchwise_data_from_stock_ledger(filters)
        key = (self.item.name, self.warehouse.name, self.batch.name)
        self.assertIn(key, data)
        self.assertGreater(data[key].balance_qty, 0)

    def test_get_batchwise_data_from_serial_batch_bundle_empty(self):
        result = get_batchwise_data_from_serial_batch_bundle({}, _dict({}))
        self.assertIsInstance(result, dict)

    # --- Tests for get_query_based_on_filters ---

    def get_base_query(self):
        table = frappe.qb.DocType("Stock Ledger Entry")
        batch = frappe.qb.DocType("Batch")
        return frappe.qb.from_(table).select(table.item_code).inner_join(batch).on(table.batch_no == batch.name), batch, table

    def test_filter_by_item_code(self):
        query, batch, table = self.get_base_query()
        filters = _dict({"item_code": self.item.name})
        q = get_query_based_on_filters(query, batch, table, filters)
        self.assertIn(self.item.name, str(q))

    def test_filter_by_batch_no(self):
        query, batch, table = self.get_base_query()
        filters = _dict({"batch_no": self.batch.name})
        q = get_query_based_on_filters(query, batch, table, filters)
        self.assertIn(self.batch.name, str(q))

    def test_include_expired_batches_false(self):
        query, batch, table = self.get_base_query()
        filters = _dict({
            "to_date": today(),
            "include_expired_batches": 0
        })
        q = get_query_based_on_filters(query, batch, table, filters)
        sql = str(q)
        self.assertIn("expiry_date", sql)
        self.assertIn("batch_qty", sql)

    def test_to_date_in_past(self):
        query, batch, table = self.get_base_query()
        filters = _dict({"to_date": add_days(today(), -5)})
        q = get_query_based_on_filters(query, batch, table, filters)
        self.assertIn("posting_date", str(q))

    def test_filter_by_warehouse(self):
        # Ensure child exists for proper testing
        child_wh = frappe.get_doc({
            "doctype": "Warehouse",
            "warehouse_name": "Child WH",
            "parent_warehouse": self.warehouse.name,
            "company": "_Test Company"
        }).insert(ignore_permissions=True)

        query, batch, table = self.get_base_query()
        filters = _dict({"warehouse": self.warehouse.name})
        q = get_query_based_on_filters(query, batch, table, filters)
        self.assertIn("warehouse", str(q))

    def test_filter_by_warehouse_type(self):
        frappe.db.set_value("Warehouse", self.warehouse.name, "warehouse_type", "Retail")
        query, batch, table = self.get_base_query()
        filters = _dict({"warehouse_type": "Retail"})
        q = get_query_based_on_filters(query, batch, table, filters)
        self.assertIn("warehouse", str(q))

    def test_show_item_name(self):
        query, batch, table = self.get_base_query()
        filters = _dict({"show_item_name": 1})
        q = get_query_based_on_filters(query, batch, table, filters)
        self.assertIn("item_name", str(q))