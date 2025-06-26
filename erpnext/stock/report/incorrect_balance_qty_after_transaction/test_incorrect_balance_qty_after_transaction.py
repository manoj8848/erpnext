import frappe
from frappe.tests.utils import FrappeTestCase
from erpnext.stock.report.incorrect_balance_qty_after_transaction.incorrect_balance_qty_after_transaction import execute
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
from erpnext.stock.doctype.item.test_item import create_item
from erpnext.accounts.doctype.payment_entry.test_payment_entry import create_company
from erpnext.accounts.utils import nowdate
from erpnext.stock.doctype.stock_entry.test_stock_entry import get_or_create_fiscal_year
from erpnext import is_perpetual_inventory_enabled



class TestIncorrectBalanceQtyReport(FrappeTestCase):
    def setUp(self):

        self.company = create_company("_Test Company")
        self.company = "_Test Company"
        self.warehouse = create_warehouse(warehouse_name = "_Test Warehouse - _TC", company = "_Test Company")
        self.item_code = create_item(item_code = "_Test Item",valuation_rate=100, warehouse = "_Test Warehouse - _TC", company = "_Test Company", is_stock_item = 1)
        get_or_create_fiscal_year("_Test Company")

        make_stock_entry()

        stock_entry1 = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "company": self.company,
            "posting_date": "2025-06-02",
            "items": [{
                "item_code": self.item_code,
                "qty": 5,
                "t_warehouse": self.warehouse,
                "basic_rate": 100
            }]
        })
        stock_entry1.insert(ignore_permissions=True)
        stock_entry1.save()
        stock_entry1.submit()
        self.stock_entry_name = stock_entry1.name
        # print("self.stock_entry_name",self.stock_entry_name)
        print("self.stock_entry_name",stock_entry1.docstatus)
        # print("stock_entry_name",self.stock_entry_name)

        # stock_entry2 = frappe.get_doc({
        #     "doctype": "Stock Entry",
        #     "stock_entry_type": "Material Receipt",
        #     "company": self.company,
        #     "posting_date": "2025-06-03",
        #     "items": [{
        #         "item_code": self.item_code,
        #         "qty": 5,
        #         "t_warehouse": self.warehouse,
        #         "basic_rate": 100
        #     }]
        # })
        # stock_entry2.insert()
        # stock_entry2.submit()
        # self.stock_entry_name2 = stock_entry2.name


        

        # # Insert Stock Ledger Entries to simulate imbalance
        # frappe.get_doc({
        #     "doctype": "Stock Ledger Entry",
        #     "item_code": self.item_code,
        #     "warehouse": self.warehouse,
        #     "actual_qty": 5,
        #     "qty_after_transaction": 5,
        #     "voucher_type": "Stock Entry",
        #     "voucher_no": self.stock_entry_name,
        #     "company": self.company,
        #     "posting_date": "2025-06-02",
        #     "posting_time": "10:00:00",
        #     "is_cancelled": 0
        # }).insert()

        # frappe.get_doc({
        #     "doctype": "Stock Ledger Entry",
        #     "item_code": self.item_code,
        #     "warehouse": self.warehouse,
        #     "actual_qty": 3,
        #     "qty_after_transaction": 7.0,  # Expected should be 5 + 3 = 8.0 → mismatch = 1.0
        #     "voucher_type": "Stock Entry",
        #     "voucher_no": self.stock_entry_name2,
        #     "company": self.company,
        #     "posting_date": "2025-06-03",
        #     "posting_time": "11:00:00",
        #     "is_cancelled": 0
        # }).insert()

        sle = frappe.get_all(
            "Stock Ledger Entry",
            filters={
                "voucher_type": "Stock Entry",
                "voucher_no": self.stock_entry_name,
                "item_code": self.item_code,
                "warehouse": self.warehouse,
            },
            # fields=["name", "qty_after_transaction"],
            # limit=1,
        )
        print("sle",sle)

    def test_execute_reports_difference(self):
        columns, data = execute({
            "item_code": self.item_code,
            "warehouse": self.warehouse,
            "company": self.company
        })

        # There should be at least one row with non-zero difference
        difference_index = [col["fieldname"] for col in columns].index("differnce")

        has_difference = any(
            row.get("differnce") and abs(row.get("differnce", 0)) > 0.5
            for row in data if isinstance(row, dict)
        )

        self.assertTrue(has_difference, "Expected at least one row with balance mismatch > 0.5")


def make_stock_entry(**args):
    items = args.get("items") or [
        {
            "item_code": "_Test Item",
            "qty": 5,
            "s_warehouse": args.get("from_warehouse") or "Stores - _TIRC",
            "t_warehouse": args.get("to_warehouse") or "_Test Warehouse - _TC",
            "basic_rate": 100,
        }
    ]

    se = frappe.new_doc("Stock Entry")
    # se.update(
    #     {
    #         "purpose": args.get("purpose") or "Material Receipt",
    #         "stock_entry_type": args.get("stock_entry_type") or "Material Receipt",
    #         "company": args.get("company") or "_Test Company",
    #         "items": args.get("items") or [ "_Test Item" ]
    #     }
    # )

    return se