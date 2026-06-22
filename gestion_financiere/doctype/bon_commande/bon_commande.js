// bon_commande.js

frappe.ui.form.on('Bon Commande', {

    refresh(frm) {
        frm.trigger('set_queries');
        frm.trigger('add_custom_buttons');
        frm.trigger('afficher_solde_factures');
        frm.trigger('coloriser_statut');
    },

    onload(frm) {
        frm.trigger('set_queries');
    },

    // ══════════════════════════════════════════
    //  FILTRES EN CASCADE
    // ══════════════════════════════════════════

    set_queries(frm) {
        // Ordonnateur (Faculté) - Pas de filtre par année
        frm.set_query('ordonnateur', () => {
            return {
                filters: {}  // Pas de filtre, toutes les facultés disponibles
            };
        });
        frm.set_query('budget_global', () => {
            // Vérifier prérequis
            if (!frm.doc.ordonnateur) {
                frappe.msgprint(__('Veuillez d\'abord sélectionner l\'ordonnateur'));
                return { filters: { name: ['=', ''] } };
            }
            
            return {
                filters: {
                    cost_center: frm.doc.ordonnateur
                }
            };
        });
        
        // Filtrer Titre par Année
        frm.set_query('titre', () => {
            if (!frm.doc.annee_budgetaire) {
                frappe.msgprint(__('Sélectionnez d\'abord l\'Année Budgétaire'));
                return { filters: { name: ['=', ''] } };
            }
            return {
                filters: { annee: frm.doc.annee_budgetaire }
            };
        });
        
        // Filtrer Chapitre par Titre ET Année
        frm.set_query('chapitre', () => {
            if (!frm.doc.titre) {
                frappe.msgprint(__('Sélectionnez d\'abord le Titre'));
                return { filters: { name: ['=', ''] } };
            }
            return {
                filters: {
                    titre: frm.doc.titre,
                    budget_global: frm.doc.budget_global
                }
            };
        });
        
        // Filtrer Article par Chapitre ET A Priori
        frm.set_query('article', () => {
            if (!frm.doc.chapitre) {
                frappe.msgprint(__('Sélectionnez d\'abord le Chapitre'));
                return { filters: { name: ['=', ''] } };
            }
            return {
                filters: {
                    budget_chapitre: frm.doc.chapitre,
                    //type: 'A priori'  // Commenté pour permettre tous les articles
                }
            };
        });
    },

    // ══════════════════════════════════════════
    //  BOUTONS PERSONNALISÉS
    // ══════════════════════════════════════════

    add_custom_buttons(frm) {
        if (frm.doc.__islocal) return;

        frm.clear_custom_buttons();

        // Workflow : Valider
        if (frm.doc.status === 'Brouillon') {
            frm.add_custom_button(__('Valider'), () => {
                frm.set_value('status', 'Validé');
                frm.save();
            }, __('Workflow'));
        }

        // Workflow : Envoyer au CF
        if (frm.doc.status === 'Validé') {
            frm.add_custom_button(__('Envoyer au CF'), () => {
                frm.set_value('status', 'Envoyé CF');
                frm.save();
            }, __('Workflow'));
        }
        // Workflow : Envoyé CF
        if (frm.doc.status === 'Envoyé CF') {
            frm.add_custom_button(__('Visa CF'), () => {
                frm.set_value('status', 'Visé CF');
                frm.save();
            }, __('Workflow'));
        }
        // Workflow : Enregistrer Visa CF
        if (frm.doc.status === 'Visé CF') {
            frm.add_custom_button(__('Enregistrer Visa CF'), () => {
                frm.trigger('dialog_visa_cf');
            }, __('Workflow'));
        }

        // Créer Fiche Dépense
        if (frm.doc.status === 'Validé' && !frm.doc.fiche_depense) {
            frm.add_custom_button(__('Créer Fiche Dépense'), () => {
                frappe.confirm(
                    __('Créer la Fiche Dépense pour ce Bon de Commande ?'),
                    () => {
                        frappe.call({
                            method: 'gestion_financiere.gestion_financiere.doctype.bon_commande.bon_commande.creer_fiche_depense_bc',
                            args: { bon_commande: frm.doc.name },
                            callback(r) {
                                if (!r.exc) {
                                    frappe.show_alert({
                                        message: __('Fiche Dépense créée !'),
                                        indicator: 'green'
                                    });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }, __('Actions'));
        }

        // Voir Fiche Dépense
        if (frm.doc.fiche_depense) {
            frm.add_custom_button(__('Voir Fiche Dépense'), () => {
                frappe.set_route('Form', 'Fiche Budgetaire', frm.doc.fiche_depense);
            });
        }

        // Enregistrer Facture
        if (frm.doc.status === 'En Exécution') {
            frm.add_custom_button(__('Enregistrer Facture'), () => {
                frappe.new_doc('Facture Fournisseur', {
                    type_reference: 'Bon Commande',
                    bon_commande: frm.doc.name,
                    fournisseur: frm.doc.prestataire,
                    annee_budgetaire: frm.doc.annee_budgetaire
                });
            }, __('Actions'));
        }
    },

    // ══════════════════════════════════════════
    //  DIALOGUES
    // ══════════════════════════════════════════

    dialog_visa_cf(frm) {
        const d = new frappe.ui.Dialog({
            title: __('Enregistrement Visa CF'),
            fields: [
                {
                    fieldtype: 'Data',
                    fieldname: 'visa_cf',
                    label: __('N° Visa CF'),
                    reqd: 1
                },
                {
                    fieldtype: 'Date',
                    fieldname: 'date_visa_cf',
                    label: __('Date Visa CF'),
                    default: frappe.datetime.get_today(),
                    reqd: 1
                }
            ],
            primary_action_label: __('Valider'),
            primary_action(values) {
                frm.set_value('visa_cf', values.visa_cf);
                frm.set_value('date_visa_cf', values.date_visa_cf);
                frm.set_value('status', 'Visé CF');
                frm.save();
                d.hide();
            }
        });
        d.show();
    },

    // ══════════════════════════════════════════
    //  AFFICHAGE SOLDE FACTURES
    // ══════════════════════════════════════════

    afficher_solde_factures(frm) {
        if (!frm.doc.name || frm.doc.__islocal) return;

        frappe.call({
            method: 'gestion_financiere.gestion_financiere.doctype.facture_fournisseur.facture_fournisseur.get_factures_bon_commande',
            args: { bon_commande: frm.doc.name },
            callback(r) {
                if (!r.exc && r.message) {
                    const { total_factures, montant_bc, reste } = r.message;
                    const taux = montant_bc > 0 
                        ? ((total_factures / montant_bc) * 100).toFixed(1)
                        : 0;
                    
                    let couleur = '#28a745';
                    if (taux >= 100) couleur = '#007bff';
                    else if (taux > 75) couleur = '#ffc107';
                    
                    frm.dashboard.add_comment(
                        `<b>BC N° ${frm.doc.numero_bon_commande}</b><br>
                         Montant BC : <b>${format_currency(montant_bc)} DA</b><br>
                         Factures : <b>${format_currency(total_factures)} DA</b> (${taux}%)<br>
                         <span style="color:${couleur};font-size:1.1em;font-weight:bold">
                             Reste : ${format_currency(reste)} DA
                         </span>`,
                        'blue', true
                    );
                }
            }
        });
    },

    // ══════════════════════════════════════════
    //  CHANGEMENTS - CASCADE
    // ══════════════════════════════════════════
    budget_global(frm) {
        frm.trigger('set_queries');
        if (frm.doc.titre || frm.doc.chapitre || frm.doc.article ) {
            frm.set_value('titre', '');
            frm.set_value('chapitre', '');
            frm.set_value('article', '');
        }
    },
    annee_budgetaire(frm) {
        frm.trigger('set_queries');
        if (frm.doc.titre || frm.doc.chapitre || frm.doc.article) {
            frm.set_value('titre', '');
            frm.set_value('chapitre', '');
            frm.set_value('article', '');
        }
    },

    titre(frm) {
        frm.trigger('set_queries');
        if (frm.doc.chapitre || frm.doc.article) {
            frm.set_value('chapitre', '');
            frm.set_value('article', '');
        }
    },

    chapitre(frm) {
        frm.trigger('set_queries');
        if (frm.doc.article) {
            frm.set_value('article', '');
        }
    },

    article(frm) {
        if (!frm.doc.article) return;
        
        frappe.db.get_value('Budget Article', frm.doc.article,
            ['code_article', 'intitule_article', 'chapitre', 'type'], r => {
                // if (r.type !== 'A priori') {
                //     frappe.msgprint({
                //         title: __('❌ Article Invalide'),
                //         message: __('Les BC sont réservés aux articles À Priori.'),
                //         indicator: 'red'
                //     });
                //     frm.set_value('article', '');
                //     return;
                // }
                
                frm.set_value('code_article', r.code_article);
                frm.set_value('intitule_article', r.intitule_article);
            }
        );
    },

    ordonnateur(frm) {
        if (!frm.doc.ordonnateur) return;
        
        frappe.db.get_value('Cost Center', frm.doc.ordonnateur,
            'cost_center_name', r => {
                frm.set_value('denomination', r.cost_center_name);
            }
        );
    },

    prestataire(frm) {
        if (!frm.doc.prestataire) return;
        
        frappe.db.get_doc('Fournisseur', frm.doc.prestataire).then(fourn => {
            frm.set_value('raison_sociale', fourn.raison_sociale);
            frm.set_value('adresse_prestataire', fourn.adresse);
            frm.set_value('numero_compte', fourn.numero_compte);
        });
    },

    taux_tva(frm) {
        frm.trigger('recalcul_totaux');
    },

    delai_livraison(frm) {
        frm.trigger('calcul_date_limite');
    },

    unite_delai(frm) {
        frm.trigger('calcul_date_limite');
    },

    date_commande(frm) {
        frm.trigger('calcul_date_limite');
    },

    calcul_date_limite(frm) {
        if (!frm.doc.date_commande || !frm.doc.delai_livraison) return;
        
        // Sera calculé par le Python lors du save
        frm.save();
    },

    recalcul_totaux(frm) {
        let total_ht = 0;
        
        (frm.doc.bc_element || []).forEach(item => {
            total_ht += flt(item.montant);
        });
        
        frm.set_value('total_ht', total_ht);
        
        const montant_tva = total_ht * flt(frm.doc.taux_tva) / 100;
        frm.set_value('montant_tva', montant_tva);
        frm.set_value('total_ttc', total_ht + montant_tva);
    },

    // ══════════════════════════════════════════
    //  COLORISATION STATUT
    // ══════════════════════════════════════════

    coloriser_statut(frm) {
        const couleurs = {
            'Brouillon': 'gray',
            'Validé': 'orange',
            'Envoyé CF': 'blue',
            'Visé CF': 'green',
            'En Exécution': 'purple',
            'Soldé': 'darkgreen'
        };
        const status = frm.doc.status || 'Brouillon';
        frm.page.set_indicator(__(status), couleurs[status]);
    },
});

// ══════════════════════════════════════════════
//  CHILD TABLE : BC Elements
// ══════════════════════════════════════════════

frappe.ui.form.on('BC Elements', {
    
    quantite(frm, cdt, cdn) {
        calculate_row_total(frm, cdt, cdn);
    },

    prix_unitaire(frm, cdt, cdn) {
        calculate_row_total(frm, cdt, cdn);
    },

    bc_elements_remove(frm) {
        frm.trigger('recalcul_totaux');
    }
});

function calculate_row_total(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const total = flt(row.quantite) * flt(row.prix_unitaire);
    frappe.model.set_value(cdt, cdn, 'montant', total);
    frm.trigger('recalcul_totaux');
}

// ══════════════════════════════════════════════
//  UTILITAIRES
// ══════════════════════════════════════════════

function format_currency(val) {
    return new Intl.NumberFormat('fr-DZ', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(parseFloat(val) || 0);
}

function flt(val) {
    return parseFloat(val) || 0;
}
