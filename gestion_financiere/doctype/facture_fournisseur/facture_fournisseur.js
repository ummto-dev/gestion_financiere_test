// facture_fournisseur.js

frappe.ui.form.on('Facture Fournisseur', {

    refresh(frm) {
        frm.trigger('set_champs_visibles');
        frm.trigger('add_custom_buttons');
        frm.trigger('afficher_solde_reference');
        frm.trigger('coloriser_statut');
    },

    onload(frm) {
        frm.trigger('set_champs_visibles');
        frm.trigger('set_queries'); //ligne ajoutée
    },


    // ══════════════════════════════════════════
    //  FILTRES partie ajoutée
    // ══════════════════════════════════════════

    set_queries(frm) {
        // ✅ FILTRE CHAPITRE
        frm.set_query('chapitre', () => {
            // Vérifier prérequis
            if (!frm.doc.budget_global) {
                frappe.msgprint(__('Veuillez d\'abord sélectionner l\'exercice budgétaire'));
                return { filters: { name: ['=', ''] } };
            }
            
            return {
                filters: {
                    budget_global: frm.doc.budget_global
                }
            };
        })
        // ✅ FILTRE ARTICLE
        frm.set_query('article', () => {
            // Vérifier prérequis
            if (!frm.doc.budget_global) {
                frappe.msgprint(__('Veuillez d\'abord sélectionner l\'exercice budgétaire'));
                return { filters: { name: ['=', ''] } };
            }
            
            return {
                filters: {
                    //budget_global: frm.doc.budget_global,
                    budget_chapitre: frm.doc.chapitre
                }
            };
        });
        
        // ✅ FILTRE BON COMMANDE
        frm.set_query('bon_commande', () => {
            // Vérifier prérequis
            if (!frm.doc.fournisseur) {
                frappe.msgprint(__('Veuillez d\'abord sélectionner le fournisseur'));
                return { filters: { name: ['=', ''] } };
            }
            
            if (!frm.doc.budget_global) {
                frappe.msgprint(__('Veuillez d\'abord sélectionner l\'budget_global'));
                return { filters: { name: ['=', ''] } };
            }
            
            // ✅ Filtre simple selon le type d'article
            let filters = {
                prestataire: frm.doc.fournisseur,
                budget_global: frm.doc.budget_global
            };
            
            // Si article sélectionné, ajouter le filtre sur l'article
            if (frm.doc.article) {
                filters.article = frm.doc.article;
                filters.status = ['not in', ['Rejeté Définitif', 'Soldé']];
                // // Ajouter le filtre de statut selon le type d'article
                // if (frm.doc.type_article === 'A priori') {
                //     filters.status = 'Visé CF';
                // } else if (frm.doc.type_article === 'A posteriori') {
                //     filters.status = 'Validé';
                // }
            } else {
                // Si pas d'article, afficher les deux statuts possibles
                //filters.status = ['in', ['Visé CF', 'Validé']];
                filters.status = ['not in', ['Rejeté Définitif', 'Soldé']];
            }
            
            return { filters: filters };
        });
        
        // ✅ FILTRE CONVENTION
        frm.set_query('convention', () => {
            // Vérifier prérequis
            if (!frm.doc.fournisseur) {
                frappe.msgprint(__('Veuillez d\'abord sélectionner le fournisseur'));
                return { filters: { name: ['=', ''] } };
            }
            
            if (!frm.doc.budget_global) {
                frappe.msgprint(__('Veuillez d\'abord sélectionner l\'exercice budgétaire'));
                return { filters: { name: ['=', ''] } };
            }
            
            // ✅ Filtres directs (plus simple et plus fiable)
            return {
                filters: {
                    fournisseur: frm.doc.fournisseur,
                    budget_global: frm.doc.budget_global,
                    status: ['not in', ['Rejeté Définitif', 'Soldé']],
                    article: frm.doc.article
                }
            };
        });
    },



    // ══════════════════════════════════════════
    //  AFFICHAGE CONDITIONNEL
    // ══════════════════════════════════════════

    set_champs_visibles(frm) {
        const type = frm.doc.type_reference;
        
        frm.toggle_display('bon_commande', type === 'Bon Commande');
        frm.toggle_display('convention', type === 'Convention');
    },

    // ══════════════════════════════════════════
    //  BOUTONS PERSONNALISÉS
    // ══════════════════════════════════════════

    add_custom_buttons(frm) {
        if (frm.doc.__islocal) return;

        frm.clear_custom_buttons();

        // Voir Bon de Commande
        if (frm.doc.bon_commande) {
            frm.add_custom_button(__('Voir Bon de Commande'), () => {
                frappe.set_route('Form', 'Bon Commande', frm.doc.bon_commande);
            });
        }

        // Voir Convention
        if (frm.doc.convention) {
            frm.add_custom_button(__('Voir Convention'), () => {
                frappe.set_route('Form', 'Convention', frm.doc.convention);
            });
        }

        // Voir Mandat
        if (frm.doc.mandat_paiement) {
            frm.add_custom_button(__('Voir Mandat'), () => {
                frappe.set_route('Form', 'Mandat Paiement', frm.doc.mandat_paiement);
            });
        }
    },

    // ══════════════════════════════════════════
    //  AFFICHAGE SOLDE RÉFÉRENCE
    // ══════════════════════════════════════════

    afficher_solde_reference(frm) {
        if (frm.doc.type_reference === 'Bon Commande' && frm.doc.bon_commande) {
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.facture_fournisseur.facture_fournisseur.get_factures_bon_commande',
                args: { bon_commande: frm.doc.bon_commande },
                callback(r) {
                    if (!r.exc && r.message) {
                        const { total_factures, montant_bc, reste } = r.message;
                        const taux = montant_bc > 0 
                            ? ((total_factures / montant_bc) * 100).toFixed(1)
                            : 0;
                        
                        let couleur = '#28a745';
                        if (taux > 90) couleur = '#dc3545';
                        else if (taux > 75) couleur = '#ffc107';
                        
                        frm.dashboard.add_comment(
                            `<b>Bon de Commande ${frm.doc.bon_commande}</b><br>
                             Montant BC : <b>${format_currency(montant_bc)} DA</b><br>
                             Factures enregistrées : <b>${format_currency(total_factures)} DA</b> (${taux}%)<br>
                             <span style="color:${couleur};font-size:1.1em;font-weight:bold">
                                 Reste : ${format_currency(reste)} DA
                             </span>`,
                            'blue', true
                        );

                        if (frm.doc.montant_ttc > reste) {
                            frappe.show_alert({
                                message: __('⚠️ Le montant de cette facture dépasse le reste du BC !'),
                                indicator: 'red'
                            }, 10);
                        }
                    }
                }
            });
        }
        
        if (frm.doc.type_reference === 'Convention' && frm.doc.convention) {
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.facture_fournisseur.facture_fournisseur.get_factures_convention',
                args: { convention: frm.doc.convention },
                callback(r) {
                    if (!r.exc && r.message) {
                        const { total_factures, montant_convention, reste } = r.message;
                        const taux = montant_convention > 0 
                            ? ((total_factures / montant_convention) * 100).toFixed(1)
                            : 0;
                        
                        let couleur = '#28a745';
                        if (taux > 90) couleur = '#dc3545';
                        else if (taux > 75) couleur = '#ffc107';
                        
                        frm.dashboard.add_comment(
                            `<b>Convention ${frm.doc.convention}</b><br>
                             Montant Convention : <b>${format_currency(montant_convention)} DA</b><br>
                             Factures enregistrées : <b>${format_currency(total_factures)} DA</b> (${taux}%)<br>
                             <span style="color:${couleur};font-size:1.1em;font-weight:bold">
                                 Reste : ${format_currency(reste)} DA
                             </span>`,
                            'blue', true
                        );

                        if (frm.doc.montant_ttc > reste) {
                            frappe.show_alert({
                                message: __('⚠️ Le montant de cette facture dépasse le reste de la Convention !'),
                                indicator: 'red'
                            }, 10);
                        }
                    }
                }
            });
        }
    },

    // ══════════════════════════════════════════
    //  CHANGEMENTS
    // ══════════════════════════════════════════

    type_reference(frm) {
        frm.trigger('set_champs_visibles');
        
        // Effacer l'autre référence
        if (frm.doc.type_reference === 'Bon Commande') {
            frm.set_value('convention', '');
        } else if (frm.doc.type_reference === 'Convention') {
            frm.set_value('bon_commande', '');
        }
    },

    article(frm) {
        if (!frm.doc.article) return;
        
        // ✅ Charger les informations de l'article
        frappe.db.get_doc('Budget Article', frm.doc.article).then(art => {
            // Mettre à jour le type d'article
            frm.set_value('type_article', art.type);
            
            // ✅ Rafraîchir les filtres
            frm.trigger('set_queries');
            frm.trigger('set_champs_visibles');
            
            // // ✅ Afficher informations
            // frappe.show_alert({
            //     message: __(
            //         '✅ Article chargé<br>' +
            //         'Code : {0}<br>' +
            //         'Type : {1}<br>' +
            //         'Chapitre : {2}',
            //         [art.code_article, art.type, art.chapitre]
            //     ),
            //     indicator: 'green'
            // }, 5);
            
            if (art.type === 'A priori') {
                frappe.msgprint({
                    title: __('📋 Article à Priori'),
                    message: __(
                        'Pour les articles à priori, la référence (BC/Convention) est obligatoire.<br>' +
                        'Le processus est : Engagement → Paiement.'
                    ),
                    indicator: 'orange'
                });
            }
        });
    },

	fournisseur(frm) {
        if (!frm.doc.fournisseur) return;
        
        frappe.db.get_value('Fournisseur', frm.doc.fournisseur, 'raison_sociale', r => {
            frm.set_value('raison_sociale', r.raison_sociale);
        });
        
        // ✅ Rafraîchir les filtres
        frm.trigger('set_queries');
        
        // ✅ Effacer BC/Convention si le fournisseur change
        if (frm.doc.bon_commande) {
            frappe.db.get_value('Bon Commande', frm.doc.bon_commande, 'prestataire', r => {
                if (r.prestataire !== frm.doc.fournisseur) {
                    frappe.msgprint({
                        title: __('⚠️ Fournisseur modifié'),
                        message: __('Le Bon de Commande a été effacé car il ne correspond plus au nouveau fournisseur.'),
                        indicator: 'orange'
                    });
                    frm.set_value('bon_commande', '');
                }
            });
        }
        
        if (frm.doc.convention) {
            frappe.db.get_value('Convention', frm.doc.convention, 'fournisseur', r => {
                if (r.fournisseur !== frm.doc.fournisseur) {
                    frappe.msgprint({
                        title: __('⚠️ Fournisseur modifié'),
                        message: __('La Convention a été effacée car elle ne correspond plus au nouveau fournisseur.'),
                        indicator: 'orange'
                    });
                    frm.set_value('convention', '');
                }
            });
        }
    },


	budget_gloabl(frm) {
        if (!frm.doc.budget_global) return;
        
        // ✅ Rafraîchir les filtres
        frm.trigger('set_queries');
        
        // ✅ Effacer BC/Convention si l'exercice change
        if (frm.doc.bon_commande) {
            frappe.db.get_value('Bon Commande', frm.doc.bon_commande, 'budget_global', r => {
                if (r.budget_global !== frm.doc.budget_global) {
                    frappe.msgprint({
                        title: __('⚠️ Exercice budgétaire modifiée'),
                        message: __('Le Bon de Commande a été effacé car il ne correspond plus à l\'exercice budgetaire.'),
                        indicator: 'orange'
                    });
                    frm.set_value('bon_commande', '');
                }
            });
        }

        if (frm.doc.convention) {
            frappe.db.get_value('Convention', frm.doc.convention, 'budget_global', r => {
                if (r.budget_global !== frm.doc.budget_global) {
                    frappe.msgprint({
                        title: __('⚠️ Année budgétaire modifiée'),
                        message: __('La Convention a été effacée car elle ne correspond plus à l\'exercice budgetaire.'),
                        indicator: 'orange'
                    });
                    frm.set_value('convention', '');
                }
            });
        }
    },

    bon_commande(frm) {
        if (!frm.doc.bon_commande) return;
        
        // ✅ Charger les informations du BC
        frappe.db.get_doc('Bon Commande', frm.doc.bon_commande).then(bc => {
            // Vérifier cohérence fournisseur
            if (bc.prestataire !== frm.doc.fournisseur) {
                frappe.msgprint({
                    title: __('⚠️ Incohérence Détectée'),
                    message: __(
                        'Le fournisseur de la facture ({0}) ne correspond pas ' +
                        'au prestataire du BC ({1}).',
                        [frm.doc.fournisseur, bc.prestataire]
                    ),
                    indicator: 'red'
                });
                frm.set_value('bon_commande', '');
                return;
            }
            
            // ✅ CHARGER IMPUTATION BUDGÉTAIRE
            frm.set_value('budget_global', bc.budget_global);
            frm.set_value('chapitre', bc.chapitre);
            frm.set_value('article', bc.article);
            // Charger Article et ses infos
            if (bc.article) {
                frappe.db.get_doc('Budget Article', bc.article).then(art => {
                    // Vous pouvez ajouter des champs dans Facture Fournisseur pour afficher ces infos
                    // Par exemple : article, chapitre, code_article, etc.
                    
                    frappe.show_alert({
                        message: __(
                            '✅ BC chargé<br>' +
                            'Article : {0}<br>' +
                            'Chapitre : {1}',
                            [art.code_article, art.chapitre]
                        ),
                        indicator: 'green'
                    }, 5);
                });
            }
            
            // Pré-remplir TVA si disponible
            if (bc.taux_tva && !frm.doc.taux_tva) {
                frm.set_value('taux_tva', bc.taux_tva);
            }
        });
        
        frm.trigger('afficher_solde_reference');
    },

    convention(frm) {
        if (!frm.doc.convention) return;
        
        // ✅ Charger les informations de la Convention
        frappe.db.get_doc('Convention', frm.doc.convention).then(conv => {
            // Vérifier cohérence fournisseur
            if (conv.fournisseur !== frm.doc.fournisseur) {
                frappe.msgprint({
                    title: __('⚠️ Incohérence Détectée'),
                    message: __(
                        'Le fournisseur de la facture ({0}) ne correspond pas ' +
                        'au fournisseur de la Convention ({1}).',
                        [frm.doc.fournisseur, conv.fournisseur]
                    ),
                    indicator: 'red'
                });
                frm.set_value('convention', '');
                return;
            }
            
            // ✅ CHARGER IMPUTATION BUDGÉTAIRE
            frm.set_value('budget_global', conv.budget_global);
            frm.set_value('chapitre', conv.chapitre);
            frm.set_value('article', conv.article);

            
            // Charger Article et ses infos
            if (conv.article) {
                frappe.db.get_doc('Budget Article', conv.article).then(art => {
                    frappe.show_alert({
                        message: __(
                            '✅ Convention chargée<br>' +
                            'Article : {0}<br>' +
                            'Chapitre : {1}',
                            [art.code_article, art.chapitre]
                        ),
                        indicator: 'green'
                    }, 5);
                });
            }
        });
        
        frm.trigger('afficher_solde_reference');
    },



    // ══════════════════════════════════════════
    //  MONTANT ET TVA
    // ══════════════════════════════════════════


    montant_ht(frm) {
        frm.trigger('calcul_tva');
    },

    taux_tva(frm) {
        frm.trigger('calcul_tva');
    },

    calcul_tva(frm) {
        if (frm.doc.montant_ht && frm.doc.taux_tva) {
            const montant_tva = flt(frm.doc.montant_ht) * flt(frm.doc.taux_tva) / 100;
            frm.set_value('montant_tva', montant_tva);
            frm.set_value('montant_ttc', flt(frm.doc.montant_ht) + montant_tva);
        } else if (frm.doc.montant_ht && !frm.doc.taux_tva) {
            frm.set_value('montant_tva', 0);
            frm.set_value('montant_ttc', flt(frm.doc.montant_ht));
        }
    },

    montant_ttc(frm) {
        frm.trigger('afficher_solde_reference');
    },

    // ══════════════════════════════════════════
    //  COLORISATION STATUT
    // ══════════════════════════════════════════

    coloriser_statut(frm) {
        const couleurs = {
            'En Attente': 'orange',
            'Mandaté': 'blue',
            'Payé': 'green'
        };
        const status = frm.doc.status || 'En Attente';
        frm.page.set_indicator(__(status), couleurs[status]);
    },

     // ══════════════════════════════════════════
    //   STATUT En Attente
    // ══════════════════════════════════════════
   
    status(frm) {
                // Effacer les Champs mandat paiement, numero mandant et date mandat
        if (frm.doc.type_reference === 'EN Attente') {
            frm.set_value('mandant_paiement', '');
            frm.set_value('numero_mandat', '')
            frm.set_value('date_mandat', '');
        }
    },
    
});

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
