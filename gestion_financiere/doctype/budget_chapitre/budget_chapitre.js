// Copyright (c) 2026, Cellule Developpement UMMTO and contributors
// For license information, please see license.txt

frappe.ui.form.on("Budget Chapitre", {
	refresh(frm) {
        frm.trigger("set_queries");
	},
   // ══════════════════════════════════════════
    //  FILTRES EN CASCADE
    // ══════════════════════════════════════════
    set_queries(frm) {
        // Implementation for setting queries
        frm.set_query('chapitre', () => {
            if (!frm.doc.budget_global) {
                frappe.throw(__('Veuillez sélectionner un exercice avant de choisir un chapitre.'));
            }
            return {
                filters: {
                    'annee_budgetaire': frm.doc.annee_budgetaire
                }
            };
        });
        
    },
});