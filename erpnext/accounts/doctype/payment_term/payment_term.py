# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from frappe.model.document import Document


class PaymentTerm(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.accounts.doctype.discount_terms.discount_terms import DiscountTerms
		from frappe.types import DF

		credit_days: DF.Int
		credit_months: DF.Int
		default_account_for_purchase: DF.Link | None
		default_account_for_sales: DF.Link | None
		description: DF.SmallText | None
		discount: DF.Float
		discount_type: DF.Literal["Percentage", "Amount"]
		discount_validity: DF.Int
		discount_validity_based_on: DF.Literal["Day(s) after invoice date", "Day(s) after the end of the invoice month", "Month(s) after the end of the invoice month"]
		due_date_based_on: DF.Literal["Day(s) after invoice date", "Day(s) after the end of the invoice month", "Month(s) after the end of the invoice month"]
		invoice_portion: DF.Float
		is_for_purchase: DF.Check
		is_for_sales: DF.Check
		mode_of_payment: DF.Link | None
		payment_term_name: DF.Data | None
		table_ouui: DF.Table[DiscountTerms]
	# end: auto-generated types

	pass
