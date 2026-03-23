/* global erpnext */

frappe.ui.form.on("Sales Order", {
	refresh: function (frm) {
		if (frm.doc.docstatus !== 0) return;
		if (!frappe.model.can_read("Sauda Booking")) return;

		frm.add_custom_button(
			__("Sauda Booking"),
			function () {
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
					get_query_filters: {
						docstatus: 1,
					},
					allow_child_item_selection: true,
					child_fieldname: "table_ulgv",
					child_columns: ["grade", "dimension", "quantity", "rate", "amount"],
				});
			},
			__("Get Items From")
		);
	},
});
