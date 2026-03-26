/* global erpnext */

frappe.ui.form.on("Sales Order", {
	refresh: function (frm) {
		if (!frappe.model.can_read("Pending Casting List")) return;
		if (frm.doc.docstatus !== 1) {
			// Reset so after the user submits (docstatus: 0 -> 1) we can add it.
			frm.__hasco_pending_casting_btn_added = false;
		} else {
			if (!frm.__hasco_pending_casting_btn_added) {
				frm.__hasco_pending_casting_btn_added = true;
				frm.add_custom_button(
					__("Pending Casting List"),
					function () {
						if (!frm.doc.name) {
							frappe.msgprint(__("Please save the Sales Order first."));
							return;
						}

						frappe.call({
							method: "hasco.hasco.doctype.pending_casting_list.pending_casting_list.make_pending_casting_list_from_sales_order",
							args: {
								sales_order: frm.doc.name,
							},
							callback: function (r) {
								if (!r.message || !r.message.name) return;
								frappe.set_route("Form", "Pending Casting List", r.message.name);
							},
						});
					},
					__("Create")
				);
			}
		}

		// Map Sauda Booking -> Sales Order (only allowed on draft Sales Order).
		if (frm.doc.docstatus !== 0) return;
		if (!frappe.model.can_read("Sauda Booking")) return;

		frm.add_custom_button(
			__("Sauda Booking"),
			async function () {
				const mapped_rows = await frappe.db.get_list("Sales Order Item", {
					parent: "Sales Order",
					filters: [
						["docstatus", "!=", 2],
						["custom_reference", "!=", ""],
					],
					fields: ["custom_reference"],
					limit_page_length: 0,
				});
				const mapped_sauda_bookings = [
					...new Set((mapped_rows || []).map((d) => d.custom_reference).filter(Boolean)),
				];

				const get_query_filters = { docstatus: 1 };
				if (mapped_sauda_bookings.length) {
					get_query_filters.name = ["not in", mapped_sauda_bookings];
				}

				erpnext.utils.map_current_doc({
					method: "hasco.hasco.doctype.sauda_booking.sauda_booking.make_sales_order",
					source_doctype: "Sauda Booking",
					target: frm,
					setters: [
						{
							label: __("Customer"),
							fieldname: "party_name",
							fieldtype: "Link",
							options: "Customer",
							default: frm.doc.customer || undefined,
						},
					],
					get_query_filters,
					allow_child_item_selection: true,
					child_fieldname: "table_ulgv",
					child_columns: ["grade", "dimension", "quantity", "rate", "amount"],
				});
			},
			__("Get Items From")
		);
	},
});
