import frappe
from frappe.utils import add_days, today
from erpnext.stock.doctype.batch.test_batch import create_batch
from erpnext.stock.doctype.item.test_item import make_item
from erpnext.stock.doctype.warehouse.test_warehouse import create_warehouse
from datetime import date
# from erpnext.stock.stock_entry.test_stock_entry import make_stock_entry

from erpnext.stock.report.batch_item_expiry_status.batch_item_expiry_status import execute


class TestBatchItemExpiryStatusReport(frappe.tests.utils.FrappeTestCase):

   def setUp(self):
       self.item = make_item("_Test Batch Price Item", {
           "has_batch_no": 1,
           "create_new_batch": 1
       })

       self.warehouse = create_warehouse("Stores - _TC")

       self.batch = frappe.new_doc("Batch")
       self.batch.item = self.item
       self.batch.batch_qty = 2
       self.batch.expiry_date =date(2030, 1, 1)
       self.batch.insert()
       # frappe.db.commit()

       # Add batch stock via stock entry
       create_stock_entry(
           item_code=self.item,
           warehouse=self.warehouse,
           qty=10,
           company="_Test Company",
           batch_no= self.batch
       )


   def test_missing_all_filters(self):
       with self.assertRaises(frappe.ValidationError, msg="Expected error for missing all filters"):
           execute({})

   def test_missing_from_date(self):
       with self.assertRaises(frappe.ValidationError, msg="Expected error for missing from_date"):
           execute({"to_date": today()})

   def test_missing_to_date(self):
       with self.assertRaises(frappe.ValidationError, msg="Expected error for missing to_date"):
           execute({"from_date": today()})


   def test_report_returns_batch_within_date_range(self):
       filters = {
           "from_date": add_days(today(), -30),
           "to_date": add_days(today(), 30),
       }
       columns, data = execute(filters)
       self.assertTrue(any(d[1] == self.item.name for d in data), f"Expected item '{self.item.name}' not found in report data")

   def test_report_filters_by_item(self):
       # This should return data
       filters = {
           "from_date": add_days(today(), -1),
           "to_date": add_days(today(), 5),
           "item": self.item.name
       }
       columns, data = execute(filters)
       self.assertTrue(all(d[1] == self.item.name for d in data), f"Expected item '{self.item.name}' not found in report data")

#    def test_expiry_days_calculation(self):
#        filters = {
#            "from_date": add_days(today(), -1),
#            "to_date": add_days(today(), 5),
#            "item": self.item.name
#        }
#        columns, data = execute(filters)
#        expiry_col_index = [i for i, col in enumerate(columns) if "Expiry" in col][0]
#        expiry_days = data[1][expiry_col_index]
#        expected_days = (self.batch.expiry_date - frappe.utils.datetime.date.today()).days
#        self.assertEqual(expiry_days, expected_days, "Expiry (In Days) calculation incorrect")


def create_stock_entry(item_code, warehouse, qty, company,batch_no):
   se = frappe.get_doc({
       "doctype": "Stock Entry",
       "stock_entry_type": "Material Receipt",
       "company": company,
       "items": [{
           "item_code": item_code,
           "qty": qty,
           "uom": "Nos",
           "t_warehouse": warehouse,
           "rate": 100,
           "batch_no":batch_no
       }]
   })
   se.insert(ignore_permissions=True)
   se.submit()
   return se.name
