# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.accounts.doctype.subscription.test_subscription import create_subscription
from erpnext.accounts.doctype.subscription_plan.test_subscription_plan import get_subscription_plan
from erpnext.selling.doctype.customer.test_customer import get_customer_dict


class TestProcessSubscription(FrappeTestCase):
	def setUp(self):
		item = make_test_item("__Test Subscription Item")
		customer = frappe.get_doc(get_customer_dict("__Test Subscription Customer_")).insert(
			ignore_permissions=True
		)
		self.item_code = item.item_code
		self.customer = customer.name

	def tearDown(self):
		frappe.db.rollback()

	def test_create_subscription_process_TC_ACC_262(self):
		from unittest.mock import patch

		from .process_subscription import create_subscription_process

		subscription_plan = get_subscription_plan(self.item_code)
		args = {
			"customer": self.customer,
			"start_date": today(),
			"plans": [{"plan": subscription_plan.name, "qty": 1}],
		}
		subscription = create_subscription(**args)
		self.assertEqual(subscription.status, "Active")

		with patch("frappe.db.commit"):
			create_subscription_process(subscription)
			get_process_subscription = frappe.get_last_doc("Process Subscription")
			self.assertEqual(get_process_subscription.subscription, subscription.name)
