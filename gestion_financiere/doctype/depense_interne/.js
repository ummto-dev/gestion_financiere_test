// depense_interne.js

frappe.ui.form.on('Depense Interne', {

    refresh(frm) {
        frm.trigger('set_queries');
        frm.trigger('set_champs_visibles');
        frm.trigger('add_custom_buttons');
        frm.trigger('afficher_solde_provision');
        frm.trigger('coloriser_statut');

        if (frm.doc.article) {
            // Recharger l'info de partition si nécessaire
            frappe.db.get_value('Article', frm.doc.article, 'has_partition', (r) => {
                frm.has_partition = r.has_partition ? true : false;
                frm.trigger('toggle_partition_fields');
            });
        }
    },

    onload(frm) {
		frm.trigger('set_queries');
        frm.trigger('set_champs_visibles');
    },

    // ══════════════════════════════════════════
    //  FILTRES
    // ══════════════════════════════════════════
   
    set_queries(frm) {
        // Filtrer Chapitre par Année Budgétaire
        frm.set_query('chapitre', () => {
            return {
                filters: {
                    annee_budgetaire: frm.doc.annee_budgetaire
                }
            };
        });
		// Filtrer Article A posteriori uniquement
		frm.set_query('article', () => {
			return {
				filters: {
					type: 'A posteriori',
		            annee_budgetaire: frm.doc.annee_budgetaire,
                    chapitre: frm.doc.chapitre
				}
			};
		});

        frm.set_query('provision_reference', () => {
            return {
                filters: {
                    article: frm.doc.article,
                    annee_budgetaire: frm.doc.annee_budgetaire,
                    type_fiche: 'Provision',
                    semestre: frm.doc.semestre,
                    //status: 'Visé CF',
                    docstatus: ["!=", 2],
                    status: ["in", [ "Signé Doyen", "Envoyé CF", "Visé CF"]], // 'Visé CF'
                }
            };
        });

        // Filtrer Frais Mission par article A posteriori
        frm.set_query('frais_mission', () => {
            if (!frm.doc.article) {
                frappe.msgprint(__('Veuillez d\'abord sélectionner l\'article'));
                return { filters: { name: ['=', ''] } };
            }

			// Vérifier d'abord que l'article est A posteriori
			frappe.db.get_value('Article', frm.doc.article, 'type', r => {
				if (r.type !== 'A posteriori') {
			    	return { filters: { name: ['=', ''] } };
			    }
			});
        
        	return {
            	query: 'gestion_financiere.gestion_financiere.doctype.depense_interne.depense_interne.get_frais_mission_aposteriori',
            	filters: {
                	article: frm.doc.article,
                	annee_budgetaire: frm.doc.annee_budgetaire
            	}
        	};			        
        });
         // ✅ FILTRE FACTURES : Via BC → Article + Fournisseur + En Attente
        if (frm.fields_dict['factures']) {
            frm.fields_dict['factures'].grid.get_field('facture_fournisseur').get_query = function(doc) {
                if (!doc.fournisseur) {
                    frappe.msgprint(__('Veuillez d\'abord sélectionner le fournisseur'));
                    return { filters: { name: ['=', ''] } };
                }
                
                if (!doc.article) {
                    frappe.msgprint(__('Veuillez d\'abord sélectionner l\'article'));
                    return { filters: { name: ['=', ''] } };
                }
                
                return {
                    query: 'gestion_financiere.gestion_financiere.doctype.depense_interne.depense_interne.get_factures_fournisseur_pour_depense',
                    filters: {
                        fournisseur: doc.fournisseur,
                        article: doc.article,
                        annee_budgetaire: frm.doc.annee_budgetaire
                    }
                };
            };
        }   
    },


    // ══════════════════════════════════════════
    //  AFFICHAGE CONDITIONNEL
    // ══════════════════════════════════════════

    set_champs_visibles(frm) {
        const type = frm.doc.type_depense;
        
        frm.toggle_display('section_fournisseur', type === 'Fournisseur');
        frm.toggle_display('section_mission', type === 'Frais Mission');
        
    
    },

 
    // ══════════════════════════════════════════
    //  BOUTONS PERSONNALISÉS
    // ══════════════════════════════════════════

    add_custom_buttons(frm) {
        if (frm.doc.__islocal) return;

        frm.clear_custom_buttons();

        // ✅ NOUVEAU : Bouton Charger Factures
        if (frm.doc.type_depense === 'Fournisseur' 
            && frm.doc.fournisseur 
            && frm.doc.article
            && frm.doc.status === 'Brouillon') {
            
            frm.add_custom_button(__('📥 Charger Factures'), () => {
                frm.trigger('dialog_charger_factures');
            }, __('Actions'));
        }
        // Bouton : Valider
        if (frm.doc.status === 'Brouillon') {
            frm.add_custom_button(__('Valider'), () => {
                frm.set_value('status', 'Validé');
                frm.save();
            }, __('Actions'));
        }

        // Bouton : Envoyer au Comptable
        if (frm.doc.status === 'Validé') {
            frm.add_custom_button(__('Envoyer au Comptable'), () => {
                frappe.confirm(
                    __('Envoyer cette dépense au service comptable pour mandatement ?'),
                    () => {
                        frm.set_value('status', 'Envoyé Comptable');
                        frm.set_value('date_envoi_comptable', frappe.datetime.get_today());
                        frm.save();
                    }
                );
            }, __('Actions'));
        }

        // Bouton : Voir Mandat
        if (frm.doc.mandat_paiement) {
            frm.add_custom_button(__('Voir Mandat Paiement'), () => {
                frappe.set_route('Form', 'Mandat Paiement', frm.doc.mandat_paiement);
            });
        }

        // Bouton : Voir Provision
        if (frm.doc.provision_reference) {
            frm.add_custom_button(__('Voir Provision'), () => {
                frappe.set_route('Form', 'Fiche Budgetaire', frm.doc.provision_reference);
            });
        }

        // Bouton : Voir Régularisation
        if (frm.doc.fiche_regularisation) {
            frm.add_custom_button(__('Voir Fiche Régularisation'), () => {
                frappe.set_route('Form', 'Fiche Budgetaire', frm.doc.fiche_regularisation);
            });
        }
    },

    // ══════════════════════════════════════════
    //  DIALOG CHARGER FACTURES
    // ══════════════════════════════════════════

    dialog_charger_factures(frm) {
        frappe.call({
            method: 'gestion_financiere.gestion_financiere.doctype.depense_interne.depense_interne.get_factures_disponibles',
            args: {
                fournisseur: frm.doc.fournisseur,
                article: frm.doc.article,
                annee_budgetaire: frm.doc.annee_budgetaire,
                depense_actuelle: frm.doc.name
            },
            callback(r) {
                if (!r.exc && r.message && r.message.length > 0) {
                    const factures = r.message;
                    
                    // Exclure celles déjà ajoutées
                    const deja_ajoutees = (frm.doc.factures || []).map(f => f.facture_fournisseur);
                    const factures_dispo = factures.filter(f => !deja_ajoutees.includes(f.name));
                    
                    if (factures_dispo.length === 0) {
                        frappe.msgprint(__('Toutes les factures disponibles sont déjà ajoutées.'));
                        return;
                    }
                    
                    const d = new frappe.ui.Dialog({
                        title: __('Factures Disponibles ({0})', [factures_dispo.length]),
                        fields: [
                            {
                                fieldtype: 'HTML',
                                options: `<div class="alert alert-info">
                                    <b>Fournisseur :</b> ${frm.doc.fournisseur}<br>
                                    <b>Article :</b> ${frm.doc.article}<br>
                                    <b>Status :</b> En Attente
                                </div>`
                            },
                            {
                                fieldtype: 'HTML',
                                fieldname: 'factures_list',
                                options: generate_factures_html(factures_dispo)
                            }
                        ],
                        primary_action_label: __('Ajouter Sélectionnées'),
                        primary_action() {
                            const selected = [];
                            d.$wrapper.find('input[type="checkbox"]:checked').each(function() {
                                selected.push($(this).data('facture'));
                            });
                            
                            if (selected.length === 0) {
                                frappe.msgprint(__('Veuillez sélectionner au moins une facture'));
                                return;
                            }
                            
                            selected.forEach(facture_name => {
                                const facture = factures_dispo.find(f => f.name === facture_name);
                                if (facture) {
                                    const row = frm.add_child('factures');
                                    row.facture_fournisseur = facture.name;
                                    row.numero_facture = facture.numero_facture;
                                    row.date_facture = facture.date_facture;
                                    row.montant = facture.montant_ttc;
                                    row.reference = facture.bon_commande;
                                }
                            });
                            
                            frm.refresh_field('factures');
                            frm.trigger('recalcul_montant_total');
                            
                            d.hide();
                            frappe.show_alert({
                                message: __('✅ {0} facture(s) ajoutée(s)', [selected.length]),
                                indicator: 'green'
                            });
                        }
                    });

                    // Handler pour Select All
                    setTimeout(() => {
                        d.$wrapper.find('#select_all_factures').on('change', function() {
                            d.$wrapper.find('.facture-checkbox').prop('checked', this.checked);
                        });
                    }, 500);
                                     
                    d.show();
                } else {
                    frappe.msgprint(__('Aucune facture disponible pour ce fournisseur et cet article.'));
                }
            }
        });
    },

    // ══════════════════════════════════════════
    //  AFFICHAGE SOLDE PROVISION
    // ══════════════════════════════════════════

    afficher_solde_provision(frm) {
        if (!frm.doc.provision_reference) return;

        frappe.call({
            method: 'gestion_financiere.gestion_financiere.doctype.depense_interne.depense_interne.get_solde_provision',
            args: { provision_reference: frm.doc.provision_reference },
            callback(r) {
                if (!r.exc && r.message) {
                    const { montant_provision, depenses_engagees, solde_disponible, numero_fiche } = r.message;
                    const taux = montant_provision > 0 
                        ? ((depenses_engagees / montant_provision) * 100).toFixed(1)
                        : 0;
                    
                    let couleur = '#28a745'; // Vert
                    if (taux > 90) couleur = '#dc3545';      // Rouge
                    else if (taux > 75) couleur = '#ffc107'; // Orange
                    
                    frm.dashboard.add_comment(
                        `<b>Provision N° ${String(numero_fiche).padStart(4, '0')}</b><br>
                         Montant provision : <b>${format_currency(montant_provision)} DA</b><br>
                         Déjà engagé : <b>${format_currency(depenses_engagees)} DA</b> (${taux}%)<br>
                         <span style="color:${couleur};font-size:1.1em;font-weight:bold">
                             Solde disponible : ${format_currency(solde_disponible)} DA
                         </span>`,
                        'blue', true
                    );

                    // Alerte si solde insuffisant
                    // if (frm.doc.montant_total > solde_disponible) {
                    //     frappe.show_alert({
                    //         message: __('⚠️ Le montant dépasse le solde disponible de la provision !'),
                    //         indicator: 'red'
                    //     }, 10);
                    // }
                }
            }
        });
    },

    // ══════════════════════════════════════════
    //  CHANGEMENTS - ARTICLE - CHAPITRE
    // ══════════════════════════════════════════
    chapitre(frm) {
        if (frm.doc.chapitre) {
            frappe.db.get_value('Chapitre', frm.doc.chapitre, 'intitule', r => {
                frm.set_value('intitule_chapitre', r.intitule);
            });
        } else {
            frm.set_value('intitule_chapitre', '');
        }
        frm.set_value('article', '');
        frm.trigger('set_queries');
    },
    article(frm) {
        if (!frm.doc.article) return;
        
        frappe.db.get_value('Article', frm.doc.article,
        	['code_article', 'intitule_article', 'chapitre', 'type'], r => {
        		// Vérifier type A posteriori
            	if (r.type !== 'A posteriori') {
            		frappe.msgprint({
                		title: __('❌ Article Invalide'),
                    	message: __(
                    		'Les Dépenses Internes sont réservées aux articles <b>À Posteriori</b>.<br>' +
                        	'Article sélectionné : <b>{0}</b><br><br>' +
                        	'Pour les articles À Priori, utilisez les Fiches Dépense.'
						).format(r.type),
                    	indicator: 'red'
					});
                    frm.set_value('code_article', r.code_article);
                    frm.set_value('intitule_article', r.intitule_article);
                    frm.set_value('chapitre', r.chapitre);
                    frm.set_value('code_partition', r.code_partie || '');
                    frm.set_value('intitule_partition', r.intitule_partie || '');
    
                }
	            // Effacer provision et frais mission si article change
	            if (frm.doc.provision_reference || frm.doc.frais_mission) {
	            	frm.set_value('provision_reference', '');
	                frm.set_value('frais_mission', '');
	                frm.clear_table('beneficiaires');
	                frm.refresh_field('beneficiaires');
				}
	                
	            frappe.show_alert({
	                message: __('✅ Article A posteriori validé'),
	                indicator: 'green'
	            });
			}
		);
    },

    annee_budgetaire(frm) {
        frm.trigger('set_queries');
        // Effacer chapitre et article si année change
        frm.set_value('chapitre', '');
        frm.set_value('intitule_chapitre', '');
        frm.set_value('article', '');
        frm.set_value('code_article', '');
        frm.set_value('intitule_article', '');
        frm.set_value('intitule_partition', '');
        frm.set_value('partition', '');
        frm.set_value('provision_reference', '');
        frm.set_value('frais_mission', '');
        frm.clear_table('beneficiaires');
        frm.refresh_field('beneficiaires');
    },

    semestre(frm) {
        frm.trigger('set_queries');
        // Effacer provision si semestre change
        if (frm.doc.provision_reference) {
            frm.set_value('provision_reference', '');
        }
    },

    // ══════════════════════════════════════════
    //  CHANGEMENTS : PROVISION
    // ══════════════════════════════════════════

    provision_reference(frm) {
        frm.trigger('afficher_solde_provision');
        frm.trigger('charger_ancien_solde');
    },

    // ══════════════════════════════════════════
    //  CHANGEMENTS : TYPE DEPENSE
    // ══════════════════════════════════════════

    type_depense(frm) {
        frm.trigger('set_champs_visibles');
              
        // Effacer les données de l'autre type
        if (frm.doc.type_depense === 'Fournisseur') {
            frm.set_value('frais_mission', '');
            frm.set_value('type_compte_mission', '');
            frm.clear_table('beneficiaires');
            frm.refresh_field('beneficiaires');
        } else if (frm.doc.type_depense === 'Frais Mission') {
            frm.set_value('fournisseur', '');
            frm.clear_table('factures');
            frm.refresh_field('factures');
        }
        
    },

    // ══════════════════════════════════════════
    //  CHANGEMENTS : FOURNISSEUR
    // ══════════════════════════════════════════

    fournisseur(frm) {
        if (!frm.doc.fournisseur) return;
        
        frappe.db.get_value('Fournisseur', frm.doc.fournisseur, 'raison_sociale', r => {
            frm.set_value('raison_sociale', r.raison_sociale);
        });
        // Rafraîchir les boutons pour afficher "Charger Factures"
        //frm.trigger('add_custom_buttons');  
    },
    // ══════════════════════════════════════════
    //  CHANGEMENTS : FRAIS MISSION
    // ══════════════════════════════════════════

    frais_mission(frm) {
        if (!frm.doc.frais_mission) return;
        
        frappe.call({
            method: 'frappe.client.get',
            args: {
                doctype: 'Frais Mission',
                name: frm.doc.frais_mission
            },
            callback(r) {
                if (!r.exc && r.message) {
                    const fm = r.message;
                    
                    // Vérifier article
                    if (fm.article !== frm.doc.article) {
                        frappe.msgprint({
                            title: __('❌ Incohérence Article'),
                            message: __(
                                'Le Frais Mission appartient à l\'article <b>{0}</b>, ' +
                                'pas à l\'article <b>{1}</b>.'
                            ).format(fm.article, frm.doc.article),
                            indicator: 'red'
                        });
                        frm.set_value('frais_mission', '');
                        return;
                    }
                    
               		// Vérifier qu'il y a des bénéficiaires
                	if (!fm.table_beneficiaires || fm.table_beneficiaires.length === 0) {
                    	frappe.msgprint({
                        	title: __('Aucun Bénéficiaire'),
                        	message: __('Ce Frais Mission ne contient aucun bénéficiaire.'),
                        	indicator: 'orange'
                    	});
                    	frm.set_value('frais_mission', '');
                    	return;
                	}
						
					// ✅ VALIDATION STRICTE : Un seul type de compte pour A posteriori
					const types_compte = new Set(
						fm.table_beneficiaires
					    	.map(b => b.type_compte)
					    	.filter(t => t)
						);
					                
					if (types_compte.size > 1) {
						const nb_banque = fm.table_beneficiaires.filter(b => b.type_compte === 'Banque').length;
					    const nb_ccp = fm.table_beneficiaires.filter(b => b.type_compte === 'CCP').length;
					                    
					    frappe.msgprint({
					    	title: __('❌ Types Compte Mixtes'),
					        message: __(
					           	'<b>RÈGLE Articles A posteriori</b><br><br>' +
					            'Ce Frais Mission contient :<br>' +
					            '- {0} personne(s) avec compte <b>Banque</b><br>' +
					            '- {1} personne(s) avec compte <b>CCP</b><br><br>' +
					            'Pour les articles <b>À Posteriori</b>, tous les bénéficiaires ' +
					            'doivent avoir le <b>même type de compte</b>.<br><br>' +
					            '💡 <i>Solution : Créez 2 Frais Mission séparés.</i>'
							).format(nb_banque, nb_ccp),
					        indicator: 'red'
					    });
					    frm.set_value('frais_mission', '');
					    return;
					}
					                
					if (types_compte.size === 0) {
					   	frappe.msgprint({
							title: __('⚠️ Type Compte Manquant'),
					        message: __('Aucun type de compte n\'est renseigné pour les bénéficiaires.'),
					        indicator: 'orange'
						});
					    frm.set_value('frais_mission', '');
					    return;
					}
					                
					
                	// Tout est OK → Charger les bénéficiaires
                	frm.clear_table('beneficiaires');
                	
                	// Mapping depuis votre structure
                	fm.table_beneficiaires.forEach(benef => {
                    	// Déterminer type_personne depuis type_missionnaire
                    	let type_personne = '';
                    	if (fm.type_missionnaire === 'Etudiants') {
                        	type_personne = 'Etudiants';
                    	} else if (fm.type_missionnaire === 'Enseignant') {
                        	type_personne = 'Enseignant';
                    	} else if (fm.type_missionnaire === 'Personnel Administratif') {
                        	type_personne = 'Personnel Administratif';
                    	}

	                    frm.add_child('beneficiaires', {
                        	type_personne: type_personne,
                        	personne: benef.personne, 
                        	nom_prenom: benef.nom_prenom,
                        	grade: '',  // Pas dans votre structure
                        	type_compte: benef.type_compte,
                        	numero_compte: benef.compte,
                        	montant: benef.montant_mission
                    	});
                	});	   

	                frm.refresh_field('beneficiaires');
                
                	// Définir type de compte
                	if (types_compte.size === 1) {
                    	const type_compte = Array.from(types_compte)[0];
                    	frm.set_value('type_compte_mission', type_compte);
                	}
                	
                	// Objet
                	if (!frm.doc.objet_depense && fm.objet_mission) {
                    	frm.set_value('objet_depense', fm.objet_mission);
                	}
                	                              
                    // Recalculer total
                    frm.trigger('recalcul_montant_total');
                    
                    frappe.show_alert({
                    	message: __(
                        	'✅ {0} bénéficiaire(s) chargé(s) - Type compte : {1}',
                        	[fm.beneficiaires.length, type_compte]
                    	),
                    	indicator: 'green'
                	});
				}
			} 
		});
	},

    // ══════════════════════════════════════════
    //  RCHARGER L'ANCIEN SOLDE DANS LE FORMULAIRE
    // ══════════════════════════════════════════
    charger_ancien_solde(frm) {
        // Vérifier que tous les champs nécessaires sont renseignés
        if (!frm.doc.article || !frm.doc.annee_budgetaire || !frm.doc.provision_reference) {
            return;
        }

        frappe.call({
            method: 'gestion_financiere.gestion_financiere.doctype.depense_interne.depense_interne.get_ancien_solde_article',
            args: {
                article: frm.doc.article,
                annee_budgetaire: frm.doc.annee_budgetaire,
                provision_reference: frm.doc.provision_reference,
                semestre: frm.doc.semestre,
                depense_actuelle: frm.doc.name
            },
            callback(r) {
                if (!r.exc) {
                    frm.set_value('ancien_solde', r.message);
                    frm.trigger('recalcul_montant_total');
                }
            }
        });
    },
    // charger_ancien_solde(frm) {
    //     if (!frm.doc.article || !frm.doc.annee_budgetaire) return;

    //     frappe.call({
    //         method: 'gestion_financiere.gestion_financiere.doctype.depense_interne.depense_interne.get_ancien_solde_article',
    //         args: {
    //             article: frm.doc.article,
    //             annee_budgetaire: frm.doc.annee_budgetaire,
    //             depense_actuelle: frm.doc.name  // pour exclure la dépense en cours en mode édition
    //         },
    //         callback(r) {
    //             if (!r.exc) {
    //                 frm.set_value('ancien_solde', r.message);
    //                 // Recalculer le nouveau solde après mise à jour de l'ancien
    //                 frm.trigger('recalcul_montant_total');
    //             }
    //         }
    //     });
    // },
    // ══════════════════════════════════════════
    //  RECALCUL MONTANT TOTAL
    // ══════════════════════════════════════════

    recalcul_montant_total(frm) {
        let total = 0;
        
        if (frm.doc.type_depense === 'Fournisseur') {
            total = (frm.doc.factures || [])
                .filter(f => f.inclure)  // Seulement les factures cochées
                .reduce((sum, f) => sum + flt(f.montant), 0);
        } else if (frm.doc.type_depense === 'Frais Mission') {
            total = (frm.doc.beneficiaires || []).reduce((sum, b) => sum + flt(b.montant), 0);
        }
        
        frm.set_value('montant_total', total);
        frm.set_value('montant_operation', total);

        // Calculer nouveau_solde = ancien_solde - montant_operation
        const ancien = flt(frm.doc.ancien_solde);
        const nouveau = ancien - total;
        frm.set_value('nouveau_solde', nouveau);

	    // Rafraîchir l'affichage de la provision              
        frm.trigger('afficher_solde_provision');
    },

    //display partition
    toggle_partition_fields(frm) {
        if (frm.has_partition) {
            frm.set_df_property('partition', 'hidden', 0);
            frm.set_df_property('intitule_partition', 'hidden', 0);
        } else {
            frm.set_df_property('partition', 'hidden', 1);
            frm.set_df_property('intitule_partition', 'hidden', 1);
        }
    },
    // ══════════════════════════════════════════
    //  COLORISATION STATUT
    // ══════════════════════════════════════════

    coloriser_statut(frm) {
        const couleurs = {
            'Brouillon': 'gray',
            'Validé': 'orange',
            'Envoyé Comptable': 'blue',
            'Mandaté': 'purple',
            'Réglé': 'green',
            'Régularisé': 'darkgreen'
        };
        const status = frm.doc.status || 'Brouillon';
        frm.page.set_indicator(__(status), couleurs[status]);
    },
});

// ══════════════════════════════════════════════
//  CHILD TABLE : Facture Depense Element
// ══════════════════════════════════════════════

frappe.ui.form.on('Facture Depense Element', {
    
    facture_fournisseur(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.facture_fournisseur) return;
        
        // ✅ VÉRIFIER LES DOUBLONS
        const doublons = (frm.doc.factures || []).filter(f => 
            f.facture_fournisseur === row.facture_fournisseur && f.name !== row.name
        );
        
        if (doublons.length > 0) {
            frappe.msgprint({
                title: __('❌ Doublon Détecté'),
                message: __(
                    'La facture <b>{0}</b> est déjà présente dans la liste.<br><br>' +
                    'Chaque facture ne peut être ajoutée qu\'une seule fois.'
                ).format(row.facture_fournisseur),
                indicator: 'red'
            });
            
            // Effacer la sélection
            frappe.model.set_value(cdt, cdn, 'facture_fournisseur', '');
            
            // Supprimer la ligne
            setTimeout(() => {
                frm.get_field('factures').grid.grid_rows_by_docname[cdn].remove();
            }, 100);
            
            return;
        }
        
        // Charger les infos de la facture
        frappe.call({
            method: 'frappe.client.get',
            args: {
                doctype: 'Facture Fournisseur',
                name: row.facture_fournisseur
            },
            callback(r) {
                if (!r.exc && r.message) {
                    const fact = r.message;
                    
                    // ✅ Vérifier le status
                    if (fact.status !== 'En Attente') {
                        frappe.msgprint({
                            title: __('❌ Statut Invalide'),
                            message: __(
                                'La facture <b>{0}</b> a le statut <b>{1}</b>.<br><br>' +
                                'Seules les factures <b>En Attente</b> peuvent être ajoutées.'
                            ).format(fact.numero_facture, fact.status),
                            indicator: 'red'
                        });
                        frappe.model.set_value(cdt, cdn, 'facture_fournisseur', '');
                        return;
                    }
                    
                    // Vérifier le fournisseur
                    if (fact.fournisseur !== frm.doc.fournisseur) {
                        frappe.msgprint({
                            title: __('⚠️ Fournisseur Différent'),
                            message: __(
                                'Cette facture appartient à <b>{0}</b>, ' +
                                'pas à <b>{1}</b>.'
                            ).format(fact.fournisseur, frm.doc.fournisseur),
                            indicator: 'orange'
                        });
                        frappe.model.set_value(cdt, cdn, 'facture_fournisseur', '');
                        return;
                    }
                    
                    // Tout OK → Remplir les champs
                    frappe.model.set_value(cdt, cdn, 'numero_facture', fact.numero_facture);
                    frappe.model.set_value(cdt, cdn, 'date_facture', fact.date_facture);
                    frappe.model.set_value(cdt, cdn, 'montant', fact.montant_ttc);
                    frappe.model.set_value(cdt, cdn, 'reference', fact.bon_commande || fact.convention || '');
                    
                    // Recalculer le total
                    frm.trigger('recalcul_montant_total');
                    
                    frappe.show_alert({
                        message: __('✅ Facture {0} ajoutée - {1} DA', 
                            [fact.numero_facture, format_currency(fact.montant_ttc)]),
                        indicator: 'green'
                    });
                }
            }
        });
    },
    
    montant(frm) {
        frm.trigger('recalcul_montant_total');
    },
    
    factures_remove(frm) {
        frm.trigger('recalcul_montant_total');
    }
});



// ══════════════════════════════════════════════
//  CHILD TABLE : Beneficiaire Depense Element
// ══════════════════════════════════════════════

frappe.ui.form.on('Beneficiaire Depense Element', {
    
    type_personne(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        // Vérifier si un Frais Mission est sélectionné
        if (frm.doc.type_depense === 'Frais Mission' && frm.doc.frais_mission) {
            frappe.msgprint({
                title: __('❌ Modification non autorisée'),
                message: __(
                    'Les bénéficiaires ne peuvent pas être modifiés lorsque ' +
                    'un Frais Mission est sélectionné.<br><br>' +
                    'Pour modifier, changez le Frais Mission ou le type de dépense.'
                ),
                indicator: 'red'
            });
            // Annuler la modification
            frappe.model.set_value(cdt, cdn, 'type_personne', row.__oldvalue || '');
            return;
        }
        // Effacer personne si type change
        frappe.model.set_value(cdt, cdn, 'personne', '');
    },
    
    personne(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        // Vérifier si un Frais Mission est sélectionné
        if (frm.doc.type_depense === 'Frais Mission' && frm.doc.frais_mission) {
            frappe.msgprint({
                title: __('❌ Modification non autorisée'),
                message: __(
                    'Les bénéficiaires ne peuvent pas être modifiés lorsque ' +
                    'un Frais Mission est sélectionné.<br><br>' +
                    'Pour modifier, changez le Frais Mission ou le type de dépense.'
                ),
                indicator: 'red'
            });
            // Annuler la modification
            frappe.model.set_value(cdt, cdn, 'personne', row.__oldvalue || '');
            return;
        }
        
        if (!row.personne || !row.type_personne) return;

        frappe.db.get_doc(row.type_personne, row.personne).then(pers => {
        	//frappe.model.set_value(cdt, cdn, '', pers.nom_prenom || pers.name);
            frappe.model.set_value(cdt, cdn, 'nom_prenom', pers.nom_prenom || pers.name);
            frappe.model.set_value(cdt, cdn, 'grade', pers.grade || '');
            frappe.model.set_value(cdt, cdn, 'type_compte', pers.type_compte || '');
            frappe.model.set_value(cdt, cdn, 'numero_compte', pers.numero_compte || '');
        });
    },

    montant(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        // Vérifier si un Frais Mission est sélectionné
        if (frm.doc.type_depense === 'Frais Mission' && frm.doc.frais_mission) {
            frappe.msgprint({
                title: __('❌ Modification non autorisée'),
                message: __(
                    'Les montants ne peuvent pas être modifiés lorsque ' +
                    'un Frais Mission est sélectionné.<br><br>' +
                    'Pour modifier, changez le Frais Mission ou le type de dépense.'
                ),
                indicator: 'red'
            });
            // Annuler la modification
            frappe.model.set_value(cdt, cdn, 'montant', row.__oldvalue || '');
            return;
        }
        
        frm.trigger('recalcul_montant_total');
    },

    beneficiaires_add(frm, cdt, cdn) {
        // Vérifier si un Frais Mission est sélectionné
        if (frm.doc.type_depense === 'Frais Mission' && frm.doc.frais_mission) {
            frappe.msgprint({
                title: __('❌ Ajout non autorisé'),
                message: __(
                    'Impossible d\'ajouter des bénéficiaires lorsque ' +
                    'un Frais Mission est sélectionné.<br><br>' +
                    'Les bénéficiaires sont automatiquement chargés depuis le Frais Mission.'
                ),
                indicator: 'red'
            });
            // Supprimer la ligne ajoutée
            setTimeout(() => {
                const grid = frm.fields_dict.beneficiaires.grid;
                const row = grid.grid_rows_by_docname[cdn];
                if (row) {
                    row.remove();
                }
            }, 100);
            return;
        }
    },

    beneficiaires_remove(frm) {
        // Vérifier si un Frais Mission est sélectionné
        if (frm.doc.type_depense === 'Frais Mission' && frm.doc.frais_mission) {
            frappe.msgprint({
                title: __('❌ Suppression non autorisée'),
                message: __(
                    'Impossible de supprimer des bénéficiaires lorsque ' +
                    'un Frais Mission est sélectionné.<br><br>' +
                    'Pour modifier, changez le Frais Mission ou le type de dépense.'
                ),
                indicator: 'red'
            });
            // Empêcher la suppression en rafraîchissant
            setTimeout(() => {
                frm.reload_doc();
            }, 100);
            return;
        }
        
        frm.trigger('recalcul_montant_total');
    }
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

function generate_factures_html(factures) {
    let html = '<table class="table table-bordered" style="margin-top:10px">';
    html += '<thead><tr>';
    html += '<th width="5%"><input type="checkbox" id="select_all_factures"></th>';
    html += '<th width="20%">N° Facture</th>';
    html += '<th width="15%">Date</th>';
    html += '<th width="20%">Montant (DA)</th>';
    html += '<th width="40%">BC</th>';
    html += '</tr></thead><tbody>';
    
    factures.forEach(f => {
        html += `<tr>
            <td><input type="checkbox" class="facture-checkbox" data-facture="${f.name}"></td>
            <td><b>${f.numero_facture}</b></td>
            <td>${frappe.datetime.str_to_user(f.date_facture)}</td>
            <td style="text-align:right"><b>${format_currency(f.montant_ttc)}</b></td>
            <td>${f.bon_commande || '-'}</td>
        </tr>`;
    });
    
    html += '</tbody></table>';
    
    html += `<script>
        $('#select_all_factures').on('change', function() {
            $('.facture-checkbox').prop('checked', this.checked);
        });
    </script>`;
    
    return html;
}

