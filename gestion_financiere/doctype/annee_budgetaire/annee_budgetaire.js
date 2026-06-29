frappe.ui.form.on('Annee Budgetaire', {
    annee: function(frm) {
        if (frm.doc.annee) {
            let selected_year = parseInt(frm.doc.annee);
            let current_year = new Date().getFullYear();

            if (selected_year === current_year) {
                frm.set_value('active', 1);
            } else {
                frm.set_value('active', 0);
            }
        }
    },

    validate: function(frm) {
        if (frm.doc.annee && frm.doc.annee < 2000) {
            frappe.msgprint(__('L\'année budgétaire doit être supérieure ou égale à 2000.'));
            frappe.validated = false;
        }
    }
});
