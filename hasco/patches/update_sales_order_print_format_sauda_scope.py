# Copyright (c) 2026
# For license information, please see license.txt

from hasco.patches.update_sales_order_print_format import execute as update_sales_order_pf_execute


def execute():
	"""Re-apply Sales Order print format update with Sauda-only scope."""
	update_sales_order_pf_execute()
