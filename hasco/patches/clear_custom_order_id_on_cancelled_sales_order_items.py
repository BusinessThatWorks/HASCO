# Copyright (c) 2026, Pratikshya Gochhayat and contributors
# For license information, please see license.txt

"""Clear Sales Order Item.custom_order_id for lines on cancelled Sales Orders.

Runs before backfill: frees unique values so ``backfill_sales_order_item_custom_order_id``
can assign Order IDs without seeing stale rows. ``before_cancel`` keeps this true going forward.
"""

import frappe


def execute():
	if not frappe.get_meta("Sales Order Item").has_field("custom_order_id"):
		return

	if frappe.db.db_type == "postgres":
		frappe.db.sql(
			"""
			UPDATE "tabSales Order Item" AS soi
			SET custom_order_id = NULL
			FROM "tabSales Order" AS p
			WHERE p.name = soi.parent
				AND p.docstatus = 2
				AND COALESCE(soi.custom_order_id, '') != ''
			"""
		)
	else:
		frappe.db.sql(
			"""
			UPDATE `tabSales Order Item` soi
			INNER JOIN `tabSales Order` p ON p.name = soi.parent
			SET soi.custom_order_id = NULL
			WHERE p.docstatus = 2
				AND IFNULL(soi.custom_order_id, '') != ''
			"""
		)
