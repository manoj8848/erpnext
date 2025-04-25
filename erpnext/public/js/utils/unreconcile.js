frappe.provide("erpnext.accounts");

erpnext.accounts.unreconcile_payment = {
	add_unreconcile_btn(frm) {
		if (frm.doc.docstatus == 1) {
			if (
				(frm.doc.doctype == "Journal Entry" &&
					!["Journal Entry", "Bank Entry", "Cash Entry"].includes(frm.doc.voucher_type)) ||
				![
					"Purchase Invoice",
					"Sales Invoice",
					"Journal Entry",
					"Payment Entry",
					"Payment Reconciliation Record", // Added custom Doctype
				].includes(frm.doc.doctype)
			) {
				return;
			}
			if (frm.doc.doctype === "Payment Reconciliation Record") {
				// No need for check for references
				frm.add_custom_button(
					__("UnReconcile"),
					function () {
							// Directly unreconcile all allocations for Payment Reconciliation Record
							erpnext.accounts.unreconcile_payment.unreconcile_all_allocations(frm);
					},
					__("Actions")
				);
			} else {
				// Check for references and then pop up the button
			frappe.call({
				method: "erpnext.accounts.doctype.unreconcile_payment.unreconcile_payment.doc_has_references",
				args: {
					doctype: frm.doc.doctype,
					docname: frm.doc.name,
				},
				callback: function (r) {
					if (r.message) {
						frm.add_custom_button(
							__("UnReconcile"),
							function () {
								erpnext.accounts.unreconcile_payment.build_unreconcile_dialog(frm);
							},
							__("Actions")
						);
					}
				},
			});
			}
		}
	},

	unreconcile_all_allocations(frm) {
		// Show Clearing Date dialog before proceeding
		this.show_clearing_date_dialog((clearing_date) => {
			// Prepare data for unreconciling all allocations
			const allocation_data = frm.doc.allocation
			.filter(allocation => allocation.unreconcile === 0)
			.map(allocation => ({
				company: frm.doc.company,
				voucher_type: allocation.reference_type,
				voucher_no: allocation.reference_name,
				against_voucher_type: allocation.invoice_type,
				against_voucher_no: allocation.invoice_number,
			}));
	
			// Trigger the server-side method to unreconcile
			frappe.call({
				method: "erpnext.accounts.doctype.unreconcile_payment.unreconcile_payment.create_unreconcile_doc_for_selection",
				args: { selections: allocation_data, clearing_date : clearing_date},
				callback: () => {
					frappe.msgprint(__("UnReconciliation completed."), __("Success"));
	
					// After unreconciling, create the duplicate Payment Reconciliation Record
					this.create_payment_reconciliation_record_on_unreconcile(frm, clearing_date);
				},
			});
		});
	},
	
	show_clearing_date_dialog(callback) {
		// Create a dialog to capture the clearing date
		const dialog = new frappe.ui.Dialog({
			title: __("Enter Clearing Date"),
			fields: [
				{
					label: __("Clearing Date"),
					fieldname: "clearing_date",
					fieldtype: "Date",
					reqd: 1,
					default: frappe.datetime.get_today()
				},
			],
			primary_action_label: __("UnReconcile"),
			primary_action(values) {
				if (values.clearing_date) {
					dialog.hide(); 
					callback(values.clearing_date); 
				}
			},
		});
		dialog.show();
	},
	
	create_payment_reconciliation_record_on_unreconcile(frm, clearing_date) {
		// Create a duplicate Payment Reconciliation Record with clearing date
		frappe.call({
			method: "erpnext.accounts.doctype.unreconcile_payment.unreconcile_payment.payment_reconciliation_record_on_unreconcile",
			args: {
				payment_reconciliation_record_name: frm.doc.name,
				clearing_date,
			},
			callback: (r) => {
				if (r.message) {
					frappe.msgprint(
						__("A duplicate Payment Reconciliation Record has been created with the UnReconcile flag."),
						__("Success")
					);
					frm.reload_doc();
				}
			},
		});
	},
		
	
	build_selection_map(frm, selections) {
		// assuming each row is an individual voucher
		// pass this to server side method that creates unreconcile doc for each row
		let selection_map = [];
		if (["Sales Invoice", "Purchase Invoice"].includes(frm.doc.doctype)) {
			selection_map = selections.map(function (elem) {
				return {
					company: elem.company,
					voucher_type: elem.voucher_type,
					voucher_no: elem.voucher_no,
					against_voucher_type: frm.doc.doctype,
					against_voucher_no: frm.doc.name,
					allocated_amount: elem.allocated_amount
				};
			});
		} else if (["Payment Entry", "Journal Entry"].includes(frm.doc.doctype)) {
			selection_map = selections.map(function (elem) {
				return {
					company: elem.company,
					voucher_type: frm.doc.doctype,
					voucher_no: frm.doc.name,
					against_voucher_type: elem.voucher_type,
					against_voucher_no: elem.voucher_no,
					allocated_amount: elem.allocated_amount
				};
			});
		}
		return selection_map;
	},

	build_unreconcile_dialog(frm) {
		if (
			["Sales Invoice", "Purchase Invoice", "Payment Entry", "Journal Entry"].includes(frm.doc.doctype)
		) {
			let child_table_fields = [
				{
					label: __("Voucher Type"),
					fieldname: "voucher_type",
					fieldtype: "Dynamic Link",
					options: "DocType",
					in_list_view: 1,
					read_only: 1,
				},
				{
					label: __("Voucher No"),
					fieldname: "voucher_no",
					fieldtype: "Link",
					options: "voucher_type",
					in_list_view: 1,
					read_only: 1,
				},
				{
					label: __("Allocated Amount"),
					fieldname: "allocated_amount",
					fieldtype: "Currency",
					in_list_view: 1,
					read_only: 1,
					options: "account_currency",
				},
				{
					label: __("Currency"),
					fieldname: "account_currency",
					fieldtype: "Link",
					options: "Currency",
					read_only: 1,
				},
			];
			let unreconcile_dialog_fields = [
				{
					label: __("Clearing Date"),
					fieldname: "clearing_date",
					fieldtype: "Date",
					reqd: 1,
					default: frappe.datetime.get_today(),
				},
				{
					label: __("Allocations"),
					fieldname: "allocations",
					fieldtype: "Table",
					read_only: 1,
					fields: child_table_fields,
					cannot_add_rows: true,
				},
			];

			// Get linked payments
			frappe.call({
				method: "erpnext.accounts.doctype.unreconcile_payment.unreconcile_payment.get_linked_payments_for_doc",
				args: {
					company: frm.doc.company,
					doctype: frm.doc.doctype,
					docname: frm.doc.name,
				},
				callback: function (r) {
					if (r.message) {
						// Populate child table with allocations
						unreconcile_dialog_fields[1].data = r.message;
						unreconcile_dialog_fields[1].get_data = function () {
							return r.message;
						};
	
						let d = new frappe.ui.Dialog({
							title: __("UnReconcile Allocations"),
							fields: unreconcile_dialog_fields,
							size: "large",
							primary_action_label: __("UnReconcile"),
							primary_action(values) {
								let clearing_date = values.clearing_date;
								let selected_allocations = values.allocations.filter((x) => x.__checked);
	
								if (selected_allocations.length > 0) {
									let selection_map =
										erpnext.accounts.unreconcile_payment.build_selection_map(
											frm,
											selected_allocations
										);
									erpnext.accounts.unreconcile_payment.create_unreconcile_docs(
										frm,
										selection_map,
										clearing_date // Pass the clearing date
									);
									d.hide();
								} else {
									frappe.msgprint(__("No Selection"));
								}
							},
						});

						d.show();
					}
				},
			});
		}
	},

	create_unreconcile_docs(frm,selection_map,clearing_date) {
		frappe.call({
			method: "erpnext.accounts.doctype.unreconcile_payment.unreconcile_payment.create_unreconcile_doc_for_selection",
			args: {
				selections: selection_map,
			},
			callback: function(r) {
				// Call the method to create the Payment Reconciliation Record after UnReconcile
				erpnext.accounts.unreconcile_payment.create_payment_reconciliation_record_for_other_source_docs(
					frm, 
					selection_map,
					clearing_date
				);
			}
		});
	},
	//Create Payment Reconciliation Record after UnReconcile
    create_payment_reconciliation_record_for_other_source_docs(frm, selected_allocations, clearing_date) {
		// Build the data for Payment Reconciliation Record
		let payment_reconciliation_data = {
			company: frm.doc.company,
			unreconcile: 1, // Default value
			clearing_date: clearing_date
		};
		if (frm.doc.doctype === "Sales Invoice") {
			payment_reconciliation_data.party_type = "Customer";
			payment_reconciliation_data.party = frm.doc.customer;
		} else if (frm.doc.doctype === "Purchase Invoice") {
			payment_reconciliation_data.party_type = "Supplier";
			payment_reconciliation_data.party = frm.doc.supplier;
		} else {
			payment_reconciliation_data.party_type = frm.doc.party_type;
			payment_reconciliation_data.party = frm.doc.party;
		}
	
		let allocations = [];
		// Handle the allocation mapping for different doctypes
		if (["Sales Invoice", "Purchase Invoice"].includes(frm.doc.doctype)) {
			allocations = selected_allocations.map(function (elem) {
				return {
					reference_type: elem.voucher_type,      
					reference_name: elem.voucher_no,          
					invoice_type: elem.against_voucher_type,        
					invoice_number: elem.against_voucher_no,                  
					allocated_amount: elem.allocated_amount,  
				};
			});
		} else if (["Payment Entry", "Journal Entry"].includes(frm.doc.doctype)) {
			allocations = selected_allocations.map(function (elem) {
				return {
					reference_type: frm.doc.doctype,               
					reference_name: frm.doc.name,                  
					invoice_type: elem.against_voucher_type,        
					invoice_number: elem.against_voucher_no,         
					allocated_amount: elem.allocated_amount, 
				};
			});
		}
		frappe.call({
			method: "erpnext.accounts.doctype.unreconcile_payment.unreconcile_payment.payment_reconciliation_record_on_unreconcile",
			args: {
				header: payment_reconciliation_data,
				allocation: allocations,
			}
		});
	}
	
};
