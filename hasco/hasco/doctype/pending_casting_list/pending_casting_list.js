// Copyright (c) 2026, Pratikshya Gochhayat and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pending Casting List", {
	refresh: function (frm) {
		if (frm.doc.docstatus !== 0) return;
		if (frm.__pending_casting_fetch_btn_added) return;
		frm.__pending_casting_fetch_btn_added = true;

		frm.add_custom_button(
			__("Sales Order"),
			function () {
				const do_fetch = function (salesOrder) {
					if (!salesOrder) {
						frappe.msgprint(__("Please select a Sales Order."));
						return;
					}

					frappe.call({
						method: "hasco.hasco.doctype.pending_casting_list.pending_casting_list.fetch_items_from_sales_order",
						args: {
							sales_order: salesOrder,
						},
						callback: function (r) {
							if (!r.message) return;

							frm.set_value("sales_order", salesOrder);
							frm.set_value("party_name", r.message.party_name || null);
							frm.set_value("order_date", r.message.order_date || null);

							frm.clear_table("table_jthm");
							(r.message.items || []).forEach((row) => {
								const child = frm.add_child("table_jthm");
								Object.keys(row).forEach((k) => {
									child[k] = row[k];
								});
							});
							frm.refresh_field("table_jthm");
						},
					});
				};

				if (frm.doc.sales_order) {
					do_fetch(frm.doc.sales_order);
					return;
				}

				const d = new frappe.ui.Dialog({
					title: __("Sales Order"),
					fields: [
						{
							fieldname: "sales_order",
							fieldtype: "Link",
							options: "Sales Order",
							label: __("Sales Order"),
							reqd: 1,
							get_query: function () {
								return {
									filters: {
										docstatus: ["!=", 2],
									},
								};
							},
						},
					],
					primary_action_label: __("Fetch"),
					primary_action: function (values) {
						d.hide();
						do_fetch(values.sales_order);
					},
				});
				d.show();
			},
			__("Fetch From")
		);
	},
});
