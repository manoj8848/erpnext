// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Open Item Reconciliation", {
	refresh(frm) {

        frm.set_df_property("credit_amount", "cannot_delete_rows", true);
		frm.set_df_property("debit_amount", "cannot_delete_rows", true);
		frm.set_df_property("allocation", "cannot_delete_rows", true);

		frm.set_df_property("credit_amount", "cannot_add_rows", true);
		frm.set_df_property("debit_amount", "cannot_add_rows", true);
		frm.set_df_property("allocation", "cannot_add_rows", true);


        frm.set_query("account",{
            "is_group":0,
            "is_open_item":1
        })

        get_unreconciled_entries(frm)
        button_switches(frm)

        frm.fields_dict['credit_amount'].grid.wrapper.on('click', '.grid-row-check', function() {
            get_selected_outstanding_credit_amt(frm)
        });
        frm.fields_dict['debit_amount'].grid.wrapper.on('click', '.grid-row-check', function() {
            get_selected_outstanding_debit_amt(frm)
        });
	},

    account(frm){
        frm.add_custom_button(__("Get Unreconciled Entries"), function () {
            fetch_unreconciled_entries(frm)
        });
        frm.change_custom_button_type(__("Get Unreconciled Entries"), null, "primary");
    }
});

function get_unreconciled_entries(frm){
    if(frm.doc.account && frm.is_new()){
        frm.add_custom_button(__("Get Unreconciled Entries"), function () {
            fetch_unreconciled_entries(frm)
        });
        frm.change_custom_button_type(__("Get Unreconciled Entries"), null, "primary");
    }
    else{
        frm.remove_custom_button(__("Get Unreconciled Entries"));
    }
}

function fetch_unreconciled_entries(frm){
    frappe.call({
        method:"fetch_unreconciled_gl_entries",
        doc:frm.doc,
        callback:function(r){
            if (!(frm.doc.credit_amount.length || frm.doc.debit_amount.length)) {
                frappe.throw({
                    message: __("No Unreconciled Credit & Debit GL Entries found for this  account"),
                });
            } else if (!frm.doc.credit_amount.length) {
                frappe.throw({ message: __("No Outstanding Credit GL Entries found for this account") });
            } else if (!frm.doc.debit_amount.length) {
                frappe.throw({ message: __("No Outstanding Debit GL Entries found for this account") });
            }
            frm.refresh_field("credit_amount")
            frm.refresh_field("debit_amount")
            frm.refresh()
            frm.save()
        }
    })
}

function allocate_entries(frm){
		let credit_gl = frm.fields_dict.credit_amount.grid.get_selected_children();
		if (!credit_gl.length) {
			credit_gl = frm.doc.credit_amount;
		}
		let debit_gl = frm.fields_dict.debit_amount.grid.get_selected_children();
		if (!debit_gl.length) {
			debit_gl = frm.doc.debit_amount;
		}
		return frm.call({
			doc: frm.doc,
			method: "allocate_entries",
			args: {
				credit_gl: credit_gl,
				debit_gl: debit_gl,
			},
			callback: () => {
				frm.refresh();
			},
		});
}

function reconcile_allocated_entries(frm){
    let allocated_entries = frm.doc.allocation;
    frappe.call({
        method:"reconcile_allocated_entries",
        doc: frm.doc,
        args:{
            allocated_entries:allocated_entries
        },
        callback:function(r){
            if (!r.exc) {
                frm.remove_custom_button(__("Get Unreconciled Entries"));
                frm.remove_custom_button(__("Allocate"));
                frm.remove_custom_button(__("Reconcile"));
                frappe.msgprint(__("Reconciliation successful!"));
                frm.save("Submit")
                
            }
        }
        

    })
}

function button_switches(frm){
    if (frm.doc.credit_amount.length && frm.doc.debit_amount.length && frm.doc.docstatus < 1) {
        frm.add_custom_button(__("Allocate"), function () {
            allocate_entries(frm)
        });
        frm.change_custom_button_type(__("Allocate"), null, "primary");
        frm.change_custom_button_type(__("Get Unreconciled Entries"), null, "default");
    }
    if (frm.doc.allocation.length && frm.doc.docstatus < 1 ) {
        frm.add_custom_button(__("Reconcile"), function () {
            reconcile_allocated_entries(frm)
        });
        frm.change_custom_button_type(__("Reconcile"), null, "primary");
        frm.change_custom_button_type(__("Get Unreconciled Entries"), null, "default");
        frm.change_custom_button_type(__("Allocate"), null, "default");
    }
}

function get_selected_outstanding_credit_amt(frm){
    let credit_total = 0.0
    let credit_gl = frm.fields_dict.credit_amount.grid.get_selected_children();
    if(credit_gl){
        credit_gl.forEach(row => {
            credit_total += row.outstanding_amount;
        });
        frm.set_value('total_credit_amount', credit_total); 
    }
    else{
        frm.set_value('total_credit_amount', 0.0);
    }

}

function get_selected_outstanding_debit_amt(frm){
    let debit_total = 0.0
    let debit_gl = frm.fields_dict.debit_amount.grid.get_selected_children();
    if(debit_gl){
        debit_gl.forEach(row => {
            debit_total += row.outstanding_amount;
        });
        frm.set_value('total_debit_amount', debit_total); 
    }
    else{
        frm.set_value('total_debit_amount', 0.0);
    }

}
