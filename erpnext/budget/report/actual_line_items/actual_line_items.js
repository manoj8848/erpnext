// Copyright (c) 2023, Extension and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Actual Line Items"] = {
    "filters": [
        {
            "fieldname": "project",
            "label": __("Project"),
            "fieldtype": "MultiSelectList",
            get_data: function (txt) {
                return frappe.db.get_link_options('Project', txt, {});
            },
            "width": "80",
        },
        {
            "fieldname": "wbs",
            "label": __("WBS"),
            "fieldtype": "MultiSelectList",
            get_data: function (txt) {
                return frappe.db.get_link_options('Work Breakdown Structure', txt, {});
            }
        },
        {
            "fieldname": "show_group_totals",
            "label": __("Show Group Totals"),
            "fieldtype": "Check",
            "hidden": 1
        },
        {
            "fieldname": "fiscal_year",
            "label": __("Fiscal Year"),
            "fieldtype": "Link",
            "options": "Fiscal Year"
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "depends_on": 'eval:doc.fiscal_year'
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "depends_on": 'eval:doc.fiscal_year'
        },
        {
            "fieldname": "voucher_type",
            "label": __("Voucher Type"),
            "fieldtype": "Select",
            "options": [" ","Purchase Receipt", "Purchase Invoice", "Stock Entry", "Expense Claim", "Journal Entry"],
            "default": " "
        },
        {
            "fieldname": "voucher_name",
            "label": __("Voucher Name"),
            "fieldtype": "Link",
            "options": () => frappe.query_report.get_filter_value("voucher_type"),
            "depends_on": 'eval:doc.voucher_type'
        },
        {
            "fieldname": "supplier",
            "label": __("Supplier"),
            "fieldtype": "MultiSelectList",
            get_data: function (txt) {
                return frappe.db.get_link_options('Supplier', txt, {});
            }
        },
        // {
        //     "fieldname": "ec_type",
        //     "label": __("Expense Claim Type"),
        //     "fieldtype": "Link",
        //     "options": "Expense Claim Type",
        //     // "depends_on": "eval:doc.voucher_type == 'Expense Claim'"
        // },
        // {
        //     "fieldname": "se_type",
        //     "label": __("Stock Entry Type"),
        //     "fieldtype": "Link",
        //     "options": "Stock Entry Type"
        // },
        {
            "fieldname": "item_code",
            "label": __("Item Code"),
            "fieldtype": "MultiSelectList",
            get_data: function (txt) {
                return frappe.db.get_link_options('Item', txt, {});
            }
        },
        {
            "fieldname": "item_group",
            "label": __("Item Group"),
            "fieldtype": "MultiSelectList",
            get_data: function (txt) {
                return frappe.db.get_link_options('Item Group', txt, {});
            }
        },
        // {
        //     "fieldname": "purchase_order",
        //     "label": __("Purchase Order"),
        //     "fieldtype": "MultiSelectList",
        //     get_data: function (txt) {
        //         return frappe.db.get_link_options('Purchase Order', txt, {});
        //     }
        // },
        // {
        //     "fieldname": "gl_account",
        //     "label": __("GL Account"),
        //     "fieldtype": "Link",
        //     "options": "Account"
        // },
        // {
        //     "fieldname": "cost_center",
        //     "label": __("Cost Center"),
        //     "fieldtype": "MultiSelectList",
        //     get_data: function (txt) {
        //         return frappe.db.get_link_options('Cost Center', txt, {});
        //     }
        // },
        // {
        //     "fieldname": "plant",
        //     "label": __("Plant"),
        //     "fieldtype": "MultiSelectList",
        //     get_data: function (txt) {
        //         return frappe.db.get_link_options('Plant', txt, {});
        //     }
        // },

    ],
    "formatter": function (value, row, column, data, default_formatter) {
    value = default_formatter(value, row, column, data);

    if (column.field === "WBS") {
        value = $(`<span>${value}</span>`);
        var $value = $(value).css("font-weight", "bold");
        value = $value.wrap("<p></p>").parent().html();
    }

    if (data && row[1] && row[1].content === "Grand Total") {
        value = $(`<span>${value}</span>`);
        var $value = $(value).css("font-weight", "bold");
        value = $value.wrap("<p></p>").parent().html();
    }

    return value;
}


};