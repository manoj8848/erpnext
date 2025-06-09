# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from frappe.model.document import Document  # pragma: no cover


class CustomsTariffNumber(Document):  # pragma: no cover
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:  # pragma: no cover
		from frappe.types import DF

		description: DF.Data | None
		tariff_number: DF.Data
	# end: auto-generated types

	pass
