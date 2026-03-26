# Copyright (c) 2026
# For license information, please see license.txt

import frappe
from frappe import _


def _build_html() -> str:
	# Use a fixed column set matching the actual child doctype fields,
	# because the default "Standard" print layout doesn't include the full table columns.
	return """
<div style="border:1px solid #000; padding:0px;">
	<style>
		table, th, td { border: 1px solid #000 !important; border-collapse: collapse; }
		.item-table { font-size: 10px; width: 100%; margin-top: 0px; border-top: 0; border-left: 0; border-right: 0; }
		.item-table th, .item-table td { padding: 3px 4px; }
		@media print {
			.item-table { border-left: 1px solid #000 !important; border-right: 1px solid #000 !important; }
		}
	</style>

	<div style="text-align:center; border-bottom:1px solid #000; padding:6px 0;">
		<span style="font-size:18px; font-weight:600;">PENDING CASTING LIST</span>
	</div>

	<div style="width:100%; display:flex; border-bottom:1px solid #000; font-size:12px;">
		<div style="width:50%; padding:8px;">
			<b>Voucher No.:</b><br>
			{{ doc.name }}
		</div>
		<div style="width:50%; padding:8px;">
			<b>Order Date:</b><br>
			{{ frappe.format_date(doc.order_date, "dd-MMM-yyyy") if doc.order_date else "" }}
		</div>
	</div>

	<div style="width:100%; display:flex; font-size:12px;">
		<div style="width:50%; padding:8px; border-bottom:1px solid #000;">
			<b>Party Name:</b><br>
			{{ doc.party_name or "" }}
		</div>
		<div style="width:50%; padding:8px; border-bottom:1px solid #000;">
			<b>Sales Order:</b><br>
			{{ doc.sales_order or "" }}
		</div>
	</div>

	<table class="table table-bordered table-condensed item-table">
		<thead>
			<tr>
				<th style="width:5%;">Sl No</th>
				<th style="width:10%;">Grade</th>
				<th style="width:12%;">Item Code</th>
				<th style="width:12%;">Mould Size</th>
				<th style="width:12%;">Dimension</th>
				<th style="width:12%;">Hot Top Type</th>
				<th style="width:12%;">Process</th>
				<th style="width:10%;">Order Type</th>
				<th style="width:14%;">Order Status</th>
				<th style="width:8%;">Pick</th>
				<th style="width:10%;">Pick Date</th>
				<th style="width:18%;">Other Info</th>
			</tr>
		</thead>

		<tbody>
			{% for row in doc.table_jthm %}
			<tr>
				<td class="text-center">{{ row.idx }}</td>
				<td>{{ row.grade or "" }}</td>
				<td>{{ row.item_code or "" }}</td>
				<td>{{ row.mould_size or "" }}</td>
				<td>{{ row.dimension or "" }}</td>
				<td>{{ row.hot_top_type or "" }}</td>
				<td>{{ row.link_vbsl or "" }}</td>
				<td>{{ row.order_type or "" }}</td>
				<td>{{ row.order_status or "" }}</td>
				<td>{{ row.pick or "" }}</td>
				<td>{{ frappe.format_date(row.pick_date, "dd-MMM-yyyy") if row.pick_date else "" }}</td>
				<td>
					{{ row.other_info or row.other_information or "" }}
				</td>
			</tr>
			{% endfor %}
		</tbody>
	</table>
</div>
""".strip()


def execute():
	pf_name = "Pending Casting List"
	doctype_name = "Pending Casting List"

	html = _build_html()

	# Upsert print format
	if frappe.db.exists("Print Format", pf_name):
		pf = frappe.get_doc("Print Format", pf_name)
	else:
		pf = frappe.new_doc("Print Format")
		pf.name = pf_name
		pf.owner = frappe.session.user

	pf.doc_type = doctype_name
	pf.print_format_for = "DocType"
	pf.print_format_type = "Jinja"
	pf.module = "hasco"
	pf.disabled = 0
	pf.standard = "No"
	pf.custom_format = 1
	pf.pdf_generator = pf.get("pdf_generator") or "wkhtmltopdf"
	pf.html = html

	# Mark explicitly as a custom template so Frappe uses pf.html directly.
	pf.save(ignore_permissions=True)

	# Set as default for this standard DocType via Property Setter.
	# (Directly setting `DocType.default_print_format` is blocked for standard doctypes.)
	if frappe.db.exists(
		"Property Setter",
		{
			"doc_type": doctype_name,
			"property": "default_print_format",
			"doctype_or_field": "DocType",
		},
	):
		ps = frappe.db.get_value(
			"Property Setter",
			{
				"doc_type": doctype_name,
				"property": "default_print_format",
				"doctype_or_field": "DocType",
			},
			"name",
		)
		ps_doc = frappe.get_doc("Property Setter", ps)
	else:
		ps_doc = frappe.new_doc("Property Setter")
		ps_doc.doctype_or_field = "DocType"
		ps_doc.doc_type = doctype_name
		ps_doc.property = "default_print_format"

	ps_doc.value = pf_name
	ps_doc.module = "hasco"
	ps_doc.save(ignore_permissions=True)
