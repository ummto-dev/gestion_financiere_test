// budget_article.js

frappe.ui.form.on('Budget Article', {
    
	refresh(frm) {
        frm.trigger("set_queries");
	},
   // ══════════════════════════════════════════
    //  FILTRES EN CASCADE
    // ══════════════════════════════════════════
    set_queries(frm) {
        // Implementation for setting queries
        frm.set_query('budget_chapitre', () => {
            if (!frm.doc.cost_center) {
                frappe.throw(__('Veuillez sélectionner un ordonnateur avant de choisir un chapitre.'));
            }
            if (!frm.doc.annee_budgetaire) {
                frappe.throw(__('Veuillez sélectionner l\'Année Budgétaire avant de choisir un chapitre.'));
            }
            budget_global = frm.doc.ord + '-' + frm.doc.annee_budgetaire;
            return {
                filters: {
                    'annee_budgetaire': frm.doc.annee_budgetaire,
                    'budget_global': budget_global,
                }
            };
        });

        frm.set_query('article', () => {
            if (!frm.doc.budget_chapitre) { 
                frappe.throw(__('Veuillez sélectionner un chapitre avant de choisir un article.'));
            }
            return {
                filters: {
                    'chapitre': frm.doc.chapitre,
                }
            };
        });
        
    },
});