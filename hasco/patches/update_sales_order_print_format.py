# Copyright (c) 2026
# For license information, please see license.txt

import re

import frappe
from frappe import _


def execute():
	pf_name = "Sales Order"

	if not frappe.db.exists("Print Format", pf_name):
		frappe.throw(_("Print Format '{0}' not found").format(pf_name))

	pf = frappe.get_doc("Print Format", pf_name)

	# Mark as custom so it won't behave like a standard core report.
	pf.custom_format = 1
	pf.standard = "No"
	pf.disabled = 0
	# Make ownership show up under this app.
	pf.module = "hasco"

	html = pf.html or ""

	# Fix destination mapping if it's still pointing to a date.
	# Example old: {{ frappe.format_date(doc.transaction_date, "dd-MMM-yyyy") }}
	html = re.sub(
		r"(<b>\s*Destination\s*:</b><br>\s*)\{\{\s*.*?\s*\}\}",
		r'\1{{ doc.shipping_address_name or doc.territory or doc.place_of_supply or "" }}',
		html,
		flags=re.IGNORECASE | re.DOTALL,
	)

	# Fix dated mapping to transaction_date.
	html = re.sub(
		r"(<b>\s*Dated\s*:</b><br>\s*)\{\{\s*.*?\s*\}\}",
		r'\1{{ frappe.format_date(doc.transaction_date, "dd-MMM-yyyy") }}',
		html,
		flags=re.IGNORECASE | re.DOTALL,
	)

	# Replace the Sales Order Items table with one driven by Sales Order Item list-view fields.
	# We replace the <table ... item-table> block right before the "Amount Chargeable" <div>.
	item_table_pattern = (
		r'<table class="table table-bordered table-condensed item-table"[^>]*>.*?</table>'
		r"(\s*<div style=\"margin-top:-10px;padding:4px;\">)"
	)

	new_item_table = r"""
<table class="table table-bordered table-condensed item-table" style="font-size:10px; width:100%; margin-top:0px; border-top:0; border-left:0; border-right:0;">
	{% set visible_fields = [] %}
	{% for df in frappe.get_meta("Sales Order Item").fields %}
		{% if df.in_list_view and not df.hidden %}
			{% set _ = visible_fields.append(df) %}
		{% endif %}
	{% endfor %}

	<thead>
		<tr>
			<th style="width:5%;">Sl No</th>
			{% for df in visible_fields %}
			<th>{{ df.label }}</th>
			{% endfor %}
		</tr>
	</thead>

	<tbody>
		{% for item in doc.items %}
		<tr>
			<td>{{ item.idx }}</td>
			{% for df in visible_fields %}
			{% set value = item.get(df.fieldname) %}
			<td>
				{% if df.fieldtype in ["Currency", "Float", "Int", "Percent"] %}
					{{ frappe.format_value(value, df, doc=item) if value is not none else "" }}
				{% else %}
					{{ value or "" }}
				{% endif %}
			</td>
			{% endfor %}
		</tr>
		{% endfor %}
	</tbody>
</table>
""".strip()

	html, table_replace_count = re.subn(
		item_table_pattern,
		new_item_table + r"\1",
		html,
		flags=re.DOTALL,
	)

	if table_replace_count == 0:
		frappe.throw(
			_(
				"Could not update Sales Order print items table for Print Format '{0}'. HTML block not found."
			).format(pf_name)
		)

	pf.html = html
	pf.save(ignore_permissions=True)
	frappe.db.commit()
