# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase, change_settings
from frappe.utils import get_year_ending, get_year_start, today

from erpnext.accounts.doctype.payment_entry.test_payment_entry import make_test_item
from erpnext.selling.doctype.customer.test_customer import get_customer_dict

from .subscription_plan import get_plan_rate


class TestSubscriptionPlan(FrappeTestCase):
	def setUp(self):
		self.item = make_test_item("__Test Subscription Item")
		self.customer = frappe.get_doc(get_customer_dict("__Test Subscription Customer")).insert(
			ignore_permissions=True
		)

	def tearDown(self):
		frappe.db.rollback()

	@change_settings("Subscription Settings", {"prorate": 0})
	def test_plan_rate_TC_ACC_218(self):
		sub_plan = get_subscription_plan(self.item.item_code)

		fixed_rate = get_plan_rate(plan=sub_plan.name, prorate_factor=2)
		self.assertEqual(fixed_rate, 20)

		sub_plan.price_determination = "Based On Price List"
		sub_plan.save()

		based_on_price = get_plan_rate(plan=sub_plan.name, customer=self.customer.name)

		# expexts '0' because there is no price list created against item
		self.assertEqual(based_on_price, 0)

		sub_plan.price_determination = "Monthly Rate"
		sub_plan.save()

		based_monthly = get_plan_rate(
			plan=sub_plan.name,
			start_date=get_year_start(today()),
			end_date=get_year_ending(today()),
		)
		self.assertEqual(based_monthly, 120)

	@change_settings("Subscription Settings", {"prorate": 1})
	def test_prorate_factor_TC_ACC_219(self):
		sub_plan = get_subscription_plan(self.item.item_code)
		sub_plan.price_determination = "Monthly Rate"
		sub_plan.cost = 20
		sub_plan.save()

		based_monthly = get_plan_rate(
			plan=sub_plan.name,
			start_date=get_year_start(today()),
			end_date=get_year_ending(today()),
		)
		self.assertEqual(based_monthly, 240)


def get_subscription_plan(item_code):
	subscription = "__Test Subscription Plan"
	if not frappe.db.exists("Subscription Plan", subscription):
		doc = frappe.get_doc(
			{
				"doctype": "Subscription Plan",
				"plan_name": subscription,
				"currency": "INR",
				"item": item_code,
				"price_determination": "Fixed Rate",
				"cost": 10,
				"billing_interval": "Day",
				"billing_interval_count": 1,
			}
		)
		doc.insert(ignore_permissions=True)

		return doc

	return frappe.get_doc("Subscription Plan", subscription)
