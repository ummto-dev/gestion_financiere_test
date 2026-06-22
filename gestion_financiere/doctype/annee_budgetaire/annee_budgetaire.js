// Copyright (c) 2026, Cellule Developpement UMMTO and contributors
// For license information, please see license.txt

frappe.ui.form.on('Annee Budgetaire', {
    onload: function(frm) {
        toggle_cloture_logic(frm);
    },

    refresh: function(frm) {
        toggle_cloture_logic(frm);
        apply_datepicker_filters(frm);
    },

    annee: function(frm) {
        if (frm.doc.annee) {
            let selected_year = parseInt(frm.doc.annee);
            let current_year = new Date().getFullYear();

            if (selected_year === current_year) {
                frm.set_value('date_ouverture', frappe.datetime.get_today());
            } else {
                frm.set_value('date_ouverture', selected_year + "-01-01");
            }

            apply_datepicker_filters(frm);
        }
    },

    active: function(frm) {
        toggle_cloture_logic(frm);
    },

    validate: function(frm) {
        if (frm.doc.active == 1) {
            frm.set_df_property('date_cloture', 'reqd', 0);
            frm.set_value('date_cloture', null);
        } else {
            if (!frm.doc.date_cloture) {
                frappe.msgprint(__('Veuillez saisir la date de clôture car l\'année n\'est plus active.'));
                frappe.validated = false;
            }
        }

        if (frm.doc.date_cloture && !frm.doc.active) {
            if (frm.doc.date_cloture <= frm.doc.date_ouverture) {
                frappe.msgprint({
                    title: __('Erreur de date'),
                    indicator: 'red',
                    message: __('La <b>Date de Clôture</b> doit être strictement postérieure à la <b>Date d\'Ouverture</b>.')
                });
                frappe.validated = false;
            }

            let mois_cloture = frappe.datetime.str_to_obj(frm.doc.date_cloture).getMonth();
            if (mois_cloture !== 11) {
                frappe.msgprint({
                    title: __('Règle de Gestion'),
                    indicator: 'orange',
                    message: __('Généralement, la clôture doit s\'effectuer durant le dernier mois (<b>Décembre</b>).')
                });
            }
        }
    }
});

function toggle_cloture_logic(frm) {
    if (frm.doc.active == 1) {
        frm.set_df_property('date_cloture', 'reqd', 0);
        frm.set_df_property('date_cloture', 'hidden', 1);
        if (frm.doc.date_cloture) {
            frm.set_value('date_cloture', null);
        }
    } else {
        frm.set_df_property('date_cloture', 'hidden', 0);
        frm.set_df_property('date_cloture', 'reqd', 1);
        if (!frm.doc.date_cloture && frm.doc.annee) {
            frm.set_value('date_cloture', frm.doc.annee + "-12-31");
        }
    }
}

function apply_datepicker_filters(frm) {
    if (frm.doc.annee) {
        let year = parseInt(frm.doc.annee);
        let min = new Date(year, 0, 1);
        let max = new Date(year, 11, 31);

        ["date_ouverture", "date_cloture"].forEach(field => {
            if (frm.fields_dict[field] && frm.fields_dict[field].$input) {
                let datepicker = frm.fields_dict[field].$input.data('datepicker');
                if (datepicker) {
                    datepicker.update({
                        minDate: min,
                        maxDate: max,
                        startDate: min
                    });
                }
            }
        });
    }
}
