// Copyright (c) 2026, Cellule Developpement UMMTO and contributors
// For license information, please see license.txt

frappe.ui.form.on('Situation Paiement', {

    refresh(frm) {
        frm.trigger('convention_query');
        frm.trigger('add_custom_buttons');
        frm.trigger('afficher_resume_soldes');
        frm.trigger('coloriser_statut');
        if (frm.fields_dict.paiements) {
                // Désactiver l'ajout/suppression de lignes
                frm.fields_dict.paiements.grid.cannot_add_rows = true;
                frm.fields_dict.paiements.grid.cannot_delete_rows = true;
                // Rendre la grille non éditable
                frm.fields_dict.paiements.grid.editable = false;
                // Masquer les boutons d'ajout/suppression (au cas où)
                frm.fields_dict.paiements.grid.wrapper.find('.grid-add-row').hide();
                frm.fields_dict.paiements.grid.wrapper.find('.grid-remove-rows').hide();
            }      
    },
	// ══════════════════════════════════════════
    //  FILTRE CHAMP CONVENTION Uniquement à la création depuis ce doctype.
    //  Affiche les conventions :
    //    - sans Situation Paiement existante
    //    - dont le statut ≠ 'Rejeté Définitif'
    // ══════════════════════════════════════════
    convention_query(frm) {
        // Si le doc est déjà sauvegardé (vient d'un autre doctype),
        // on ne pose pas de filtre restrictif.
        if (!frm.doc.__islocal) return;

        frm.set_query('convention', function () {
            return {
                filters: {
                    status: ['!=', 'Rejeté Définitif']
                },
                query: 'gestion_financiere.gestion_financiere.doctype.situation_paiement.situation_paiement.get_conventions_sans_situation'
            };
        });
    },
    //convention_query: function(frm) {
        //// Si le doc est déjà sauvegardé (vient d'un autre doctype),
        //// on ne pose pas de filtre restrictif.
        //if (!frm.doc.__islocal) return;
        //frm.set_query('convention', function() {
            //return {
                //query: 'gestion_financiere.gestion_financiere.doctype.situation_paiement.situation_paiement.get_conventions_disponibles'
            //};
        //});
    //},

    add_custom_buttons(frm) {
        if (frm.doc.__islocal) return;

        // Bouton : Voir Convention
        if (frm.doc.convention) {
            frm.add_custom_button(__('Voir Convention'), () => {
                frappe.set_route('Form', 'Convention', frm.doc.convention);
            });
        }

        // Bouton : Voir Fiche Dépense
        if (frm.doc.fiche_depense) {
            frm.add_custom_button(__('Voir Fiche Dépense'), () => {
                frappe.set_route('Form', 'Fiche Budgetaire', frm.doc.fiche_depense);
            });
        }

        // Bouton : Créer Mandat de Paiement
        if (frm.doc.status === 'En Cours' && frm.doc.reste_a_payer > 0) {
            frm.add_custom_button(__('Créer Mandat de Paiement'), () => {
                frappe.new_doc('Mandat Paiement', {
                    type_source: 'Fiche Depense',
                    fiche_depense: frm.doc.fiche_depense,
                    situation_paiement: frm.doc.name,
                    annee_budgetaire: frm.doc.annee_budgetaire,
                    article: frm.doc.article,
                    chapitre: frm.doc.chapitre,
                    fournisseur: frm.doc.fournisseur
                });
            }, __('Actions'));
        }
    },

	
	// ══════════════════════════════════════════
	//  AFFICHAGE RÉSUMÉ SOLDES (NOUVEAU)
	// ══════════════════════════════════════════
	
	afficher_resume_soldes(frm) {
	    if (!frm.doc.montant_total_convention) return;
	    
	    const total = flt(frm.doc.montant_total_convention);
	    const paye = flt(frm.doc.montant_paye);
	    const reste = flt(frm.doc.reste_a_payer);
	    const taux = total > 0 ? ((paye / total) * 100).toFixed(1) : 0;
	    
	    let couleur = '#28a745';  // Vert
	    if (taux >= 100) couleur = '#007bff';      // Bleu (soldé)
	    else if (taux > 75) couleur = '#ffc107';   // Orange
	    else if (taux > 50) couleur = '#17a2b8';   // Cyan
	    
	    frm.dashboard.add_comment(
	        `<b>Convention ${frm.doc.numero_convention}</b><br>
	         Montant total : <b>${format_currency(total)} DA</b><br>
	         Montant payé : <b>${format_currency(paye)} DA</b> (${taux}%)<br>
	         <span style="color:${couleur};font-size:1.2em;font-weight:bold">
	             Reste à payer : ${format_currency(reste)} DA
	         </span>`,
	        'blue', true
	    );
	},
	
    coloriser_statut(frm) {
        const couleurs = {
            'En Cours': 'orange',
            'Soldé': 'green'
        };
        const status = frm.doc.status || 'En Cours';
        frm.page.set_indicator(__(status), couleurs[status]);
    },

	convention(frm) {
	    if (!frm.doc.convention) return;
	    
	    // Les champs sont automatiquement chargés via fetch_from dans le JSON
	    // Juste un rafraîchissement pour s'assurer que tout est à jour
	    frm.refresh_fields();
	}

});

// 
