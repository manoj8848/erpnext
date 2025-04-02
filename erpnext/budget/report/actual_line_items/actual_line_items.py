import frappe

def execute(filters=None):
    if not filters:
        filters = {}

    columns = [
        {"label": "WBS", "fieldname": "wbs", "fieldtype": "Link", "options": "Work Breakdown Structure", "width": 200},
        {"label": "WBS Name", "fieldname": "wbs_name", "fieldtype": "Data", "width": 150},
        {"label": "WBS Level", "fieldname": "wbs_level", "fieldtype": "Int", "width": 100},
        {"label": "Voucher Type", "fieldname": "voucher_type", "fieldtype": "Data", "width": 100},
        {"label": "Voucher Name", "fieldname": "voucher_no", "fieldtype": "Data", "width": 150},
        {"label": "Voucher Date", "fieldname": "voucher_date", "fieldtype": "Date", "width": 100},
        {"label": "Item", "fieldname": "item", "fieldtype": "Data", "width": 100},
        {"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 150},
        {"label": "Rate", "fieldname": "rate", "fieldtype": "Float", "width": 100},
        {"label": "Amount", "fieldname": "amount", "fieldtype": "Float", "width": 100},
    ]

    conditions = []
    params = {}

    if filters.get("fiscal_year"):
        fiscal_year = filters["fiscal_year"]
        fiscal_year_data = frappe.db.get_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"], as_dict=True)

        if fiscal_year_data:
            from_date = fiscal_year_data["year_start_date"]
            to_date = fiscal_year_data["year_end_date"]
            conditions.append("be.posting_date BETWEEN %(from_date)s AND %(to_date)s")
            params["from_date"] = from_date
            params["to_date"] = to_date

    elif filters.get("from_date") and filters.get("to_date"):
        conditions.append("be.posting_date BETWEEN %(from_date)s AND %(to_date)s")
        params["from_date"] = filters["from_date"]
        params["to_date"] = filters["to_date"]

    if filters.get("project"):
        conditions.append("be.project IN %(project)s")
        params["project"] = tuple(filters["project"]) 

    if filters.get("wbs"):
        conditions.append("be.wbs IN %(wbs)s")
        params["wbs"] = tuple(filters["wbs"])

    if filters.get("voucher_type"):
        conditions.append("be.voucher_type = %(voucher_type)s")
        params["voucher_type"] = filters["voucher_type"]

    if filters.get("supplier"):
        conditions.append("pi.supplier IN %(supplier)s")
        params["supplier"] = tuple(filters["supplier"])

    if filters.get("item_code"):
        conditions.append("pii.item_code IN %(item_code)s")
        params["item_code"] = tuple(filters["item_code"])

    if filters.get("item_group"):
        conditions.append("pii.item_group IN %(item_group)s")
        params["item_group"] = tuple(filters["item_group"])

    vouchers = ["Purchase Invoice", "Purchase Receipt"]
    conditions.append("be.voucher_type IN %(vouchers)s")
    params["vouchers"] = tuple(vouchers)

    base_query = """
        SELECT 
            be.wbs AS wbs,
            be.wbs_name AS wbs_name,
            be.wbs_level AS wbs_level,
            be.voucher_type AS voucher_type,
            be.voucher_no AS voucher_no,
            be.posting_date AS voucher_date,
            CASE
                WHEN be.voucher_type = 'Purchase Invoice' THEN pii.item_code
                WHEN be.voucher_type = 'Purchase Receipt' THEN mri.item_code
                ELSE NULL
            END AS item,
            CASE
                WHEN be.voucher_type = 'Purchase Invoice' THEN pii.qty
                WHEN be.voucher_type = 'Purchase Receipt' THEN mri.qty
                ELSE NULL
            END AS qty,
            CASE
                WHEN be.voucher_type = 'Purchase Invoice' THEN pii.rate
                WHEN be.voucher_type = 'Purchase Receipt' THEN mri.rate
                ELSE NULL
            END AS rate,
            CASE
                WHEN be.voucher_type = 'Purchase Invoice' THEN pii.qty * pii.rate
                WHEN be.voucher_type = 'Purchase Receipt' THEN mri.qty * mri.rate
                ELSE 0
            END AS amount
        FROM 
            `tabBudget Entry` AS be
        LEFT JOIN 
            `tabPurchase Invoice` AS pi ON pi.name = be.voucher_no
        LEFT JOIN 
            `tabPurchase Invoice Item` AS pii ON pii.parent = pi.name
        LEFT JOIN 
            `tabMaterial Request` AS mr ON mr.name = be.voucher_no
        LEFT JOIN 
            `tabMaterial Request Item` AS mri ON mri.parent = mr.name
    """

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    data = frappe.db.sql(base_query, params, as_dict=True)

    total_qty = sum(row.get("qty", 0) for row in data)
    total_amount = sum(row.get("amount", 0) for row in data)

    data.append({})
    data.append({
        "wbs": "Grand Total",
        "wbs_name": "",
        "wbs_level": None,
        "voucher_type": "",
        "voucher_no": "",
        "voucher_date": None,
        "item": "",
        "qty": total_qty,
        "rate": "",
        "amount": total_amount,
    })

    return columns, data
