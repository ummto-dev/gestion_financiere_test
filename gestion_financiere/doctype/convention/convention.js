// convention.js

frappe.ui.form.on('Convention', {

    refresh(frm) {
        frm.trigger('set_queries');
        frm.trigger('add_custom_buttons');
        //frm.trigger('set_champs_visibles');
        frm.trigger('coloriser_statut');
    },

    onload(frm) {
        //frm.trigger('set_champs_visibles');
    },

	// ══════════════════════════════════════════
	//  FILTRES 
	// ══════════════════════════════════════════
	set_queries(frm) {
        
	    // 1. Filtrer Titre par Année Budgétaire
	    frm.set_query('titre', () => {
            if (!frm.doc.budget_global) {
	            frappe.msgprint(__('Veuillez d\'abord sélectionner l\'exercice budgetaire'));
	            return { filters: { name: ['=', ''] } }; // Retourne vide
	        }
	        if (!frm.doc.annee_budgetaire) {
	            frappe.msgprint(__('Veuillez d\'abord sélectionner l\'Année Budgétaire'));
	            return { filters: { name: ['=', ''] } }; // Retourne vide
	        }
	        return {
	            filters: {
	                annee: frm.doc.annee_budgetaire
	            }
	        };
	    });
	    
	    // 2. Filtrer Chapitre par Titre
	    frm.set_query('chapitre', () => {
	        if (!frm.doc.titre) {
	            frappe.msgprint(__('Veuillez d\'abord sélectionner le Titre'));
	            return { filters: { name: ['=', ''] } };
	        }
	        return {
	            filters: {
	                titre: frm.doc.titre,
                    budget_global: frm.doc.budget_global
	            }
	        };
	    });
	    
	    // 3. Filtrer Article par Chapitre ET A priori uniquement
	    frm.set_query('article', () => {
	        if (!frm.doc.chapitre) {
	            frappe.msgprint(__('Veuillez d\'abord sélectionner le Chapitre'));
	            return { filters: { name: ['=', ''] } };
	        }
	        return {
	            filters: {
	                budget_chapitre: frm.doc.chapitre,
	                type: 'A priori'
	            }
	        };
	    });
	},
	
	// ══════════════════════════════════════════
	//  CHANGEMENTS - CASCADE
	// ══════════════════════════════════════════
	
	annee_budgetaire(frm) {
	    // Rafraîchir les filtres
	    frm.trigger('set_queries');
	    
	    // Effacer les champs dépendants
	    if (frm.doc.titre || frm.doc.chapitre || frm.doc.article) {
	        frm.set_value('titre', '');
	        frm.set_value('chapitre', '');
	        frm.set_value('article', '');
	        frm.set_value('code_article', '');
	        frm.set_value('intitule_article', '');
	        
	        frappe.show_alert({
	            message: __('Titre, Chapitre et Article effacés suite au changement d\'année'),
	            indicator: 'orange'
	        });
	    }
	},
	
	titre(frm) {
	    // Rafraîchir les filtres
	    frm.trigger('set_queries');
	    
	    // Effacer les champs dépendants
	    if (frm.doc.chapitre || frm.doc.article) {
	        frm.set_value('chapitre', '');
	        frm.set_value('article', '');
	        frm.set_value('code_article', '');
	        frm.set_value('intitule_article', '');
	        
	        frappe.show_alert({
	            message: __('Chapitre et Article effacés suite au changement de Titre'),
	            indicator: 'orange'
	        });
	    }
	},
	
	chapitre(frm) {
	    // Rafraîchir les filtres
	    frm.trigger('set_queries');
	    
	    // Effacer l'article
	    if (frm.doc.article) {
	        frm.set_value('article', '');
	        frm.set_value('code_article', '');
	        frm.set_value('intitule_article', '');
	        
	        frappe.show_alert({
	            message: __('Article effacé suite au changement de Chapitre'),
	            indicator: 'orange'
	        });
	    }
	},
	
	article(frm) {
	    if (!frm.doc.article) return;
	    
	    // Fetch infos article et vérifier cohérence
	    frappe.db.get_value('Budget Article', frm.doc.article,
	        ['code_article', 'intitule_article', 'budget_chapitre', 
	         'type'], r => {
	            
	            // Validation 1 : Type A priori
	            if (r.type !== 'A priori') {
	                frappe.msgprint({
	                    title: __('❌ Article Invalide'),
	                    message: __(
	                        'Les Conventions sont réservées aux articles <b>À Priori</b>.<br>' +
	                        'L\'article sélectionné est de type <b>{0}</b>.'
	                    ).format(r.type),
	                    indicator: 'red'
	                });
	                frm.set_value('article', '');
	                return;
	            }
	            
	            // Validation 2 : Même chapitre
	            if (r.budget_chapitre !== frm.doc.chapitre) {
	                frappe.msgprint({
	                    title: __('❌ Incohérence Chapitre'),
	                    message: __(
	                        'L\'article appartient au chapitre <b>{0}</b>, ' +
	                        'pas au chapitre <b>{1}</b> sélectionné.'
	                    ).format(r.budget_chapitre, frm.doc.chapitre),
	                    indicator: 'red'
	                });
	                frm.set_value('article', '');
	                return;
	            }
	            
	            // Validation 3 : Même exercice budgetaire
	            // if (r.budget_global !== frm.doc.budget_global) {
	            //     frappe.msgprint({
	            //         title: __('❌ Incohérence Année'),
	            //         message: __(
	            //             'L\'article appartient à l\'année <b>{0}</b>, ' +
	            //             'pas à l\'année <b>{1}</b>.'
	            //         ).format(r.budget_global, frm.doc.budget_global),
	            //         indicator: 'red'
	            //     });
	            //     frm.set_value('article', '');
	            //     return;
	            // }
	            
	            // Tout est OK → Remplir les champs
	            frm.set_value('code_article', r.code_article);
	            frm.set_value('intitule_article', r.intitule_article);
	            
	            frappe.show_alert({
	                message: __('✅ Article validé : {0}').format(r.code_article),
	                indicator: 'green'
	            });
	        }
	    );
	},
	
    // ══════════════════════════════════════════
    //  AFFICHAGE CONDITIONNEL
    // ══════════════════════════════════════════

    // set_champs_visibles(frm) {
    //     const est_prestation = frm.doc.type_convention === 'Prestation';
        
    //     frm.toggle_display('situation_paiement', est_prestation);
    //     frm.toggle_display('montant_paye', est_prestation);
    //     frm.toggle_display('reste_a_payer', est_prestation);
    // },

    // ══════════════════════════════════════════
    //  BOUTONS PERSONNALISÉS
    // ══════════════════════════════════════════

    add_custom_buttons(frm) {
        if (frm.doc.__islocal) return;

        frm.clear_custom_buttons();

        // Workflow : Signer
        if (frm.doc.status === 'Brouillon') {
            frm.add_custom_button(__('Signer'), () => {
                frm.trigger('dialog_signature');
            }, __('Workflow'));
        }

        // Workflow : Demander Visa CF
        if (frm.doc.status === 'Signé') {
            frm.add_custom_button(__('Demander Visa CF'), () => {
                frm.set_value('status', 'Envoyé CF');
                frm.save();
            }, __('Workflow'));
        }

        // Workflow : Enregistrer Visa CF
        if (frm.doc.status === 'Envoyé CF') {
            frm.add_custom_button(__('Enregistrer Visa CF'), () => {
                frm.trigger('dialog_visa_cf');
            }, __('Workflow'));
        }

        // Créer Fiche Dépense (après visa CF)
        if (frm.doc.status === 'Envoyé CF' && !frm.doc.fiche_depense) {
            frm.add_custom_button(__('Créer Fiche Dépense'), () => {
                frappe.confirm(
                    __('Créer la Fiche Dépense pour cette convention ?'),
                    () => {
                        frappe.call({
                            method: 'gestion_financiere.gestion_financiere.doctype.convention.convention.creer_fiche_depense_convention',
                            args: { convention: frm.doc.name },
                            callback(r) {
                                if (!r.exc) {
                                    frappe.show_alert({
                                        message: __('Fiche Dépense créée avec succès !'),
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

        // Voir Situation Paiement
        if (frm.doc.situation_paiement) {
            frm.add_custom_button(__('Voir Situation de Paiement'), () => {
                frappe.set_route('Form', 'Situation Paiement', frm.doc.situation_paiement);
            });
        }

        // Créer Facture Fournisseur
        if (frm.doc.status === 'En Exécution') {
            frm.add_custom_button(__('Enregistrer Facture'), () => {
                frappe.new_doc('Facture Fournisseur', {
                    convention: frm.doc.name,
                    fournisseur: frm.doc.fournisseur,
                    budget_global: frm.doc.budget_global
                });
            }, __('Actions'));
        }
    },

    // ══════════════════════════════════════════
    //  DIALOGUES
    // ══════════════════════════════════════════

    dialog_signature(frm) {
        const d = new frappe.ui.Dialog({
            title: __('Signature de la Convention'),
            fields: [
                {
                    fieldtype: 'Date',
                    fieldname: 'date_signature',
                    label: __('Date de Signature'),
                    default: frappe.datetime.get_today(),
                    reqd: 1
                }
            ],
            primary_action_label: __('Signer'),
            primary_action(values) {
                frm.set_value('date_signature', values.date_signature);
                frm.set_value('status', 'Signé');
                frm.save();
                d.hide();
            }
        });
        d.show();
    },

    dialog_visa_cf(frm) {
        const d = new frappe.ui.Dialog({
            title: __('Enregistrement du Visa CF'),
            fields: [
                {
                    fieldtype: 'Data',
                    fieldname: 'visa_cf_numero',
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
                frm.set_value('visa_cf_numero', values.visa_cf_numero);
                frm.set_value('date_visa_cf', values.date_visa_cf);
                frm.set_value('status', 'Visé CF');
                frm.save();
                d.hide();
            }
        });
        d.show();
    },

    // ══════════════════════════════════════════
    //  CHANGEMENTS
    // ══════════════════════════════════════════

    type_convention(frm) {
        //frm.trigger('set_champs_visibles');
    },

    fournisseur(frm) {
        if (!frm.doc.fournisseur) return;
        
        frappe.db.get_value('Fournisseur', frm.doc.fournisseur, 'raison_sociale', r => {
            frm.set_value('raison_sociale', r.raison_sociale);
        });
    },


    // article(frm) {
    //     if (!frm.doc.article) return;
    //     
    //     frappe.db.get_value('Article', frm.doc.article,
    //         ['code_article', 'intitule_article', 'chapitre'], r => {
    //             frm.set_value('code_article', r.code_article);
    //             frm.set_value('intitule_article', r.intitule_article);
    //             frm.set_value('chapitre', r.chapitre);
    //         }
    //     );
    // },

    montant_convention(frm) {
        // Conversion en lettres sera faite par le Python
        if (frm.doc.montant_convention) {
            frm.save();
        }
    },

    // ══════════════════════════════════════════
    //  COLORISATION STATUT
    // ══════════════════════════════════════════

    coloriser_statut(frm) {
        const couleurs = {
            'Brouillon': 'gray',
            'Signé': 'orange',
            'Envoyé CF': 'blue',
            'Visé CF': 'green',
            'En Exécution': 'purple',
            'Soldé': 'darkgreen'
        };
        const status = frm.doc.status || 'Brouillon';
        frm.page.set_indicator(__(status), couleurs[status]);
    },

    status(frm) {
        // Vider les champs fiche_depense si status different de 'Visé CF'
       if (['Brouillon', 'Signé', 'Envoyé CF'].includes(frm.doc.status)) {
            frm.set_value('visa_cf_numero', '');
            frm.set_value('date_visa_cf', '');
            frm.set_value('fiche_depense', '');
            frm.set_value('situation_paiement', '') ;
            frm.save();
        }
    },

});
