// fiche_transfert_credit.js

frappe.ui.form.on('Fiche Transfert Credit', {

    refresh(frm) {
        frm.trigger('set_queries');
        frm.trigger('set_readonly_fields');
        frm.trigger('add_custom_buttons');
        frm.trigger('coloriser_statut');
    },
    // ══════════════════════════════════════════
    //  FILTRES EN CASCADE
    // ══════════════════════════════════════════
    set_queries(frm) {
        //Filter Chapitre par Exercice Budgetaire
        frm.set_query('chapitre', () => {
            if (!frm.doc.budget_global) {
                frappe.msgprint(__('Veuillez d\'abord l\'Exercice Budgetaire'));
                return { filters: { name: ['=', ''] } };
            }
            return {
                filters: {
                    budget_global: frm.doc.budget_global
                }
            };
        }); 
        //Filter Article Source par Chapitre
        frm.set_query('article_source', () => {
            if (!frm.doc.chapitre) {
                frappe.msgprint(__('Veuillez d\'abord le Chapitre'));
                return { filters: { name: ['=', ''] } };
            }
            return {
                filters: {
                    budget_chapitre: frm.doc.chapitre
                }
            };      
        });
        //Filter Article Destination par Chapitre
        frm.set_query('article_destination', () => {
            if (!frm.doc.chapitre) {
                frappe.msgprint(__('Veuillez d\'abord le Chapitre'));
                return { filters: { name: ['=', ''] } };
            }
            return {
                filters: {
                    budget_chapitre: frm.doc.chapitre
                }
            };      
        });
    },

    // ══════════════════════════════════════════
    //  EVENEMENTS
    // ══════════════════════════════════════════
    budget_global(frm) {
        frm.set_value('chapitre', '');
        frm.set_value('article_source', '');
        frm.set_value('article_destination', '');
        frm.trigger('set_queries');
    },
    chapitre(frm) {
        frm.set_value('article_source', '');
        frm.set_value('article_destination', '');
        frm.trigger('set_queries');        
    }, 
    /**
     * Set read-only fields for Fiche Transfert Credit
     * Champs toujours readonly:
     * - type_article_source
     * - type_article_destination
     * - intitule_article_source
     * - intitule_article_destination
     * - intitule_partition_source
     * - intitule_partition_destination
     * - intitule_chapitre
     * - solde_disponible_source
     * - provision_1_visee
     * - fiche_source
     * - fiche_destination
     * - date_execution
     * Champs readonly après soumission
     */
    set_readonly_fields(frm) {
        // Champs toujours readonly
        ['type_article_source', 'type_article_destination',
         'intitule_article_source', 'intitule_article_destination',
         'intitule_partition_source', 'intitule_partition_destination',
         'intitule_chapitre',
         'solde_disponible_source', 'provision_1_visee',
         'fiche_source', 'fiche_destination', 'date_execution',
        ].forEach(f => frm.set_df_property(f, 'read_only', 1));

        // Readonly après soumission
        if (frm.doc.docstatus === 1) {
            frm.disable_form();
        }
    },

    add_custom_buttons(frm) {
        frm.clear_custom_buttons();

        // Workflow
        if (frm.doc.status === 'Brouillon' && frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Signer (Doyen)'), () => {
                frm.trigger('dialog_signer_doyen');   
            }, __('Workflow'));
        }

        if (frm.doc.status === 'Signé Doyen') {
            frm.add_custom_button(__('Envoyer au CF'), () => {
                frm.set_value('status', 'Envoyé CF');
            }, __('Workflow'));
        }

        if (frm.doc.status === 'Envoyé CF') {
            frm.add_custom_button(__('Enregistrer Visa CF'), () => {
                frm.trigger('dialog_visa_cf');
            }, __('Workflow'));
            frm.add_custom_button(__('Rejeter'), () => {
                frm.trigger('dialog_rejeter');
            }, __('Workflow'));
        }
        // ✅ AJOUTER : Bouton pour créer les fiches après visa CF
	    //if (frm.doc.status === 'Visé CF' && !frm.doc.fiche_source && !frm.doc.fiche_destination) {
        if (frm.doc.status != 'Rejeté' && !frm.doc.fiche_source && !frm.doc.fiche_destination) {
    		frm.add_custom_button(__('Créer les Fiches Budgétaires'), () => {
            	frappe.confirm(
                	__('Créer les 2 fiches budgétaires (source et destination) en brouillon ?'),
                	() => {
                    	frappe.call({
                        	method: 'gestion_financiere.gestion_financiere.doctype.fiche_transfert_credit.fiche_transfert_credit.creer_fiches_transfert',
                        	args: { fiche_transfert: frm.doc.name },
                        	callback(r) {
                            	if (!r.exc) {
                                	frappe.show_alert({
                                    	message: __('Fiches créées en brouillon avec succès !'),
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


        // Voir fiches créées
        if (frm.doc.fiche_source) {
            frm.add_custom_button(__('Voir Fiche Source'), () => {
                frappe.set_route('Form', 'Fiche Budgetaire', frm.doc.fiche_source);
            });
        }
        if (frm.doc.fiche_destination) {
            frm.add_custom_button(__('Voir Fiche Destination'), () => {
                frappe.set_route('Form', 'Fiche Budgetaire', frm.doc.fiche_destination);
            });
        }
    },

    dialog_signer_doyen(frm) {
        const d = new frappe.ui.Dialog({
            title: __('Signature du Doyen'),
            fields: [{ fieldtype: 'Date', fieldname: 'date_signature',
                label: __('Date de signature'), reqd: 1,
                   default: frappe.datetime.get_today() }],
            primary_action_label: __('Signer'),
            primary_action(values) {
                frm.set_value('date_signature_doyen', values.date_signature);
                frm.set_value('status', 'Signé Doyen');
                frm.save();
                d.hide();
            }
                
        });
        d.show();
    },
    dialog_rejeter(frm) {
        const d = new frappe.ui.Dialog({
            title: __('Rejeter le Transfert'),
            fields: [{ fieldtype: 'Small Text', fieldname: 'motif_rejet',
                label: __('Motif du rejet'), reqd: 1 }],        
            primary_action_label: __('Rejeter'),
            primary_action(values) {
                frm.set_value('motif_rejet', values.motif_rejet);
                frm.set_value('status', 'Rejeté');
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
                { fieldtype: 'Data', fieldname: 'visa_cf_numero',
                  label: __('Numéro de Visa CF'), reqd: 1 },
                { fieldtype: 'Date', fieldname: 'date_visa_cf',
                  label: __('Date du Visa CF'), reqd: 1,
                  default: frappe.datetime.get_today() },
            ],
            primary_action_label: __('Valider'),
            primary_action(values) {
                frm.set_value('visa_cf_numero', values.visa_cf_numero);
                frm.set_value('date_visa_cf',   values.date_visa_cf);
                frm.set_value('status', 'Visé CF');
                frm.save().then(() => {
                    frappe.show_alert({
                        message: __('Visa CF enregistré. Les fiches budgétaires seront créées automatiquement.'),
                        indicator: 'green'
                    });
                });
                d.hide();
            }
        });
        d.show();
    },

    coloriser_statut(frm) {
        const couleurs = {
            'Brouillon':   'gray',
            'Signé Doyen': 'orange',
            'Envoyé CF':   'blue',
            'Visé CF':     'green',
            'Exécuté':     'darkgreen',
        };
        frm.page.set_indicator(__(frm.doc.status || 'Brouillon'),
            couleurs[frm.doc.status] || 'gray');
    },

    // ══════════════════════════════════════════
    //  CHANGEMENTS
    // ══════════════════════════════════════════

    article_source(frm) {
        frm.trigger('update_solde_source');
        frm.trigger('verifier_articles_differents');
        frm.trigger('verifier_meme_chapitre');
    },

    article_destination(frm) {
        frm.trigger('verifier_articles_differents');
        frm.trigger('verifier_meme_chapitre');
    },

    annee_budgetaire(frm) {
        frm.trigger('update_solde_source');
    },

    // ══════════════════════════════════════════
    //  VÉRIFICATION : ARTICLES DIFFÉRENTS
    // ══════════════════════════════════════════

    verifier_articles_differents(frm) {
        if (!frm.doc.article_source || !frm.doc.article_destination) return;

        if (frm.doc.article_source === frm.doc.article_destination) {
            frappe.msgprint({
                title: __('❌ Articles Identiques'),
                message: __(
                    `L'article source et l'article destination doivent être <b>différents</b>.<br><br>
                    Article sélectionné : <b>${frm.doc.article_source}</b><br><br>
                    Veuillez choisir un article destination différent.`
                ),
                indicator: 'red',
            });
            // Effacer l'article destination
            frm.set_value('article_destination', '');
            return;
        }
    },

    update_solde_source(frm) {
        if (!frm.doc.article_source || !frm.doc.budget_global) return;

        frappe.call({
            method: 'gestion_financiere.gestion_financiere.doctype.fiche_transfert_credit.fiche_transfert_credit.get_solde_article_pour_transfert',
            args: {
                article: frm.doc.article_source,
                budget_global: frm.doc.budget_global,
            },
            callback(r) {
                if (!r.exc && r.message) {
                    frm.set_value('solde_disponible_source', r.message.solde);
                    
                    const couleur = r.message.solde > 0 ? '#28a745' : '#dc3545';
                    frm.dashboard.add_comment(
                        `<b>Article source :</b> ${frm.doc.article_source}<br>
                         <b>Solde disponible :</b>
                         <span style="color:${couleur};font-size:1.1em">
                             ${format_currency(r.message.solde)} DA
                         </span>`,
                        'blue', true
                    );

                    // Alerte si solde insuffisant
                    if (frm.doc.montant_transfere > r.message.solde) {
                        frappe.show_alert({
                            message: __('⚠ Solde insuffisant pour ce transfert !'),
                            indicator: 'red'
                        });
                    }
                }
            }
        });
    },

    verifier_meme_chapitre(frm) {
        if (!frm.doc.article_source || !frm.doc.article_destination) return;

        frappe.call({
            method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.verifier_meme_chapitre',
            args: {
                article_source: frm.doc.article_source,
                article_destination: frm.doc.article_destination,
            },
            callback(r) {
                if (r.exc) return;
                const { meme_chapitre, chapitre_source, chapitre_destination } = r.message;
                
                if (!meme_chapitre) {
                    frappe.msgprint({
                        title: __('Transfert Invalide'),
                        message: __(
                            `Le transfert est uniquement autorisé entre articles du même chapitre.<br>
                            Article source → <b>${chapitre_source}</b><br>
                            Article destination → <b>${chapitre_destination}</b>`
                        ),
                        indicator: 'red',
                    });
                } else {
                    frm.set_value('chapitre', chapitre_source);
                    frappe.show_alert({
                        message: __(`Articles validés (même chapitre ${chapitre_source}).`),
                        indicator: 'green'
                    });
                }
            }
        });
    },

    montant_transfere(frm) {
        // Vérifier solde suffisant
        if (frm.doc.solde_disponible_source) {
            if (frm.doc.montant_transfere > frm.doc.solde_disponible_source) {
                frappe.show_alert({
                    message: __('⚠ Montant supérieur au solde disponible !'),
                    indicator: 'red'
                });
            }
        }
    },
});

function format_currency(val) {
    return new Intl.NumberFormat('fr-DZ', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(parseFloat(val) || 0);
}
