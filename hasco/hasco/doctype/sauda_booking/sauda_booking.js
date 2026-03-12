frappe.ui.form.on("Sauda Booking Item", {
    quantity: function(frm, cdt, cdn) {
        calculate_row(frm, cdt, cdn);
    },
    base_price: function(frm, cdt, cdn) {
        calculate_row(frm, cdt, cdn);
    },
    grade_rate: function(frm, cdt, cdn) {
        calculate_row(frm, cdt, cdn);
    },
    dimension_rate: function(frm, cdt, cdn) {
        calculate_row(frm, cdt, cdn);
    },
    attribute_name: function(frm, cdt, cdn) {   
        calculate_row(frm, cdt, cdn);
    },
    addl_rate: function(frm, cdt, cdn) {
        calculate_row(frm, cdt, cdn);
    },
    adjustments: function(frm, cdt, cdn) {   
        calculate_row(frm, cdt, cdn);
    }
});

function calculate_row(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    let base = flt(row.base_price);
    let grade = flt(row.grade_rate);
    let dimension = flt(row.dimension_rate);
    let process = flt(row.attribute_name);
    let addn = flt(row.addl_rate);
    let adjustments = flt(row.adjustments);
    let qty = flt(row.quantity);

    // Rate calculation
    row.rate = base + grade + dimension + process + addn;

    // Amount calculation
    row.amount = (qty * row.rate) + adjustments;

    frm.refresh_field("table_ulgv");
    calculate_totals(frm);
}

function calculate_totals(frm) {
    let total_qty = 0;
    let total_amt = 0;

    (frm.doc.table_ulgv || []).forEach(function(row) {
        total_qty += flt(row.quantity);
        total_amt += flt(row.amount);
    });

    frm.set_value("total_quantity", total_qty);
    frm.set_value("total_amount", total_amt);
}