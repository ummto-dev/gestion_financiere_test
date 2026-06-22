// mandat_paiement.js

frappe.ui.form.on('Mandat Paiement', {

    refresh(frm) {
        frm.trigger('set_queries');
        frm.trigger('set_champs_visibles');
        frm.trigger('add_custom_buttons');
		// Masquer Amend dès le refresh si Annulé Définitif
        if (frm.doc.docstatus === 2 && frm.doc.status_admission === 'Annulé Définitif') {
            masquer_bouton_amend(frm);
        }
		afficher_badge_rejets();
		frm.trigger('bloquer_table_factures');
        frm.trigger('coloriser_statut');
		if (frm.doc.type_source === 'Fiche Depense' && frm.frais_mission_beneficiaires) {
			frm.fields_dict.liste_personnes.grid.cannot_add_rows = true;
			frm.fields_dict.liste_personnes.grid.cannot_delete_rows = true;
		} else {
			frm.fields_dict.liste_personnes.grid.cannot_add_rows = false;
			frm.fields_dict.liste_personnes.grid.cannot_delete_rows = false;
		}
		if (frm.doc.type_source === 'Fiche Depense' && frm.doc.fiche_depense && frm.frais_mission_beneficiaires) {
			frm.add_custom_button(__('Choisir bénéficiaires'), () => {
				frm.trigger('dialog_choisir_beneficiaires');
			}, __('Actions'));
		}

		if (frm.doc.type_source === 'Fiche Depense' && frm.doc.fiche_depense && !frm.frais_mission_beneficiaires) {
			frappe.call({
				method: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.charger_info_fiche_depense',
				args: { fiche_depense: frm.doc.fiche_depense },
				callback(r) {
					if (!r.exc && r.message && r.message.type_engagement === 'Frais Mission' && r.message.frais_mission_apriori) {
						frappe.db.get_doc('Frais Mission', r.message.frais_mission_apriori).then(fm => {
							frm.frais_mission_beneficiaires = fm.table_beneficiaires;
							frm.frais_mission_mixtes = new Set(fm.table_beneficiaires.map(b => b.type_compte)).size > 1;
							// Recharger aussi les personnes déjà mandatées
							frappe.call({
								method: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.get_personnes_deja_mandatees',
								args: {
									fiche_depense: frm.doc.fiche_depense,
									mandat_actuel: frm.doc.name
								},
								callback(r2) {
									if (!r2.exc) {
										frm.personnes_deja_mandatees = r2.message || [];
									}
								}
							});
						});
					}
				}
			});
		}

		
    },

    onload(frm) {
        frm.trigger('set_champs_visibles');
		// Attacher l'événement au bouton
		if (frm.fields_dict.btn_choisir_beneficiaires) {
			frm.fields_dict.btn_choisir_beneficiaires.$input.off('click').click(() => {
				frm.trigger('dialog_choisir_beneficiaires');
			});
		}
    },

    // ══════════════════════════════════════════
    //  FILTRES
    // ══════════════════════════════════════════

    set_queries(frm) {
        // Filtrer Dépense Interne (A posteriori)
        frm.set_query('depense_interne', () => {
            return {
                filters: {
                    budget_global: frm.doc.budget_global,
                    status: "Validé", //["in", ["Validé", "Envoyé Comptable"]], // A posteriori
                    mandat_paiement: ['in', ['', null]]
                }
            };
        });  

        // Filtrer Fiche Dépense (A priori)
        frm.set_query('fiche_depense', () => {
            return {
                filters: {
                    budget_global: frm.doc.budget_global,
                    type_fiche: 'Dépense',
                    type_article: 'A priori',
                    //status: 'Visé CF'
					docstatus: ["!=", 2]
                }
            };
        });

		if (frm.fields_dict['factures_a_mandater']) {
			frm.fields_dict['factures_a_mandater'].grid.get_field('facture_fournisseur').get_query = function(doc, cdt, cdn) {
				let filters = {
					status: 'En Attente'
				};
				if (doc.fournisseur) {
					filters.fournisseur = doc.fournisseur;
				}
				if (doc.fiche_depense) {
					// Utiliser la query personnalisée
					return {
						query: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.get_factures_pour_mandat',
						filters: {
							fiche_depense: doc.fiche_depense,
							mandat_actuel: doc.name || '',
							fournisseur: doc.fournisseur
						}
					};
				}
				// if (doc.situation_paiement) {
				// 	// Utiliser la query personnalisée
				// 	return {
				// 		query: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.get_factures_pour_mandat',
				// 		filters: {
				// 			situation_paiement: doc.situation_paiement,
				// 			mandat_actuel: doc.name || '',
				// 			fournisseur: doc.fournisseur
				// 		}
				// 	};
				// }
				
				return { filters: filters };
			};
		}
    },

    // ══════════════════════════════════════════
    //  AFFICHAGE CONDITIONNEL
    // ══════════════════════════════════════════

    set_champs_visibles(frm) {
        const type_source = frm.doc.type_source;
        const type_creancier = frm.doc.type_creancier;

        // Sources
        frm.toggle_display('depense_interne', type_source === 'Depense Interne');
        frm.toggle_display('fiche_depense', type_source === 'Fiche Depense');
		// situation_paiement visible uniquement si Fiche Depense ET Convention 
		let show_situation = false;
		if (type_source === 'Fiche Depense' && frm._fiche_info) {
			const info = frm._fiche_info;
			show_situation = (info.type_engagement === 'Convention' );
		}
		frm.toggle_display('situation_paiement', show_situation);

		frm.toggle_display('section_factures_selection', type_creancier === 'Fournisseur Unique');
		frm.toggle_display('factures_a_mandater', type_creancier === 'Fournisseur Unique');
    
		frm.toggle_display('section_factures_selection', type_creancier === 'Fournisseur Unique');
		frm.toggle_display('factures_a_mandater', type_creancier === 'Fournisseur Unique');
        
        // Si Dépense Interne : Bloquer modification + Changer label
        if (type_source === 'Depense Interne' && type_creancier === 'Fournisseur Unique') {
            frm.set_df_property('factures_a_mandater', 'read_only', 1);
            frm.set_df_property('section_factures_selection', 'label', 
                'Factures (chargées depuis Dépense Interne - lecture seule)');
        } else if (type_creancier === 'Fournisseur Unique') {
            frm.set_df_property('factures_a_mandater', 'read_only', 0);
            frm.set_df_property('section_factures_selection', 'label', 
                'Sélection des Factures');
        }

        // Créanciers
        frm.toggle_display('fournisseur', type_creancier === 'Fournisseur Unique');
        frm.toggle_display('section_liste_personnes', 
            ['Liste Personnes', 'Divers Banque', 'Divers CCP'].includes(type_creancier));

        // Mode paiement
        const show_cheque = ['Chèque Postal', 'Caisse'].includes(frm.doc.mode_paiement);
        frm.toggle_display('numero_cheque', show_cheque);
        frm.toggle_display('date_cheque', show_cheque);
    },

    // ══════════════════════════════════════════
    //  BOUTONS PERSONNALISÉS
    // ══════════════════════════════════════════

    add_custom_buttons(frm) {
        if (frm.doc.__islocal) return;
		const statut = frm.doc.status_admission;
		const docst    = frm.doc.docstatus;
        // Nettoyer les boutons personnalisés précédents
		frm.clear_custom_buttons();
		
		// ── Annulé Définitif (docstatus=2) ──────────────────────────────
        // Cacher IMMÉDIATEMENT le bouton Amend — puis observer le DOM
        // car Frappe peut le re-rendre après le refresh
        if (docst === 2 && statut === 'Annulé Définitif') {
            masquer_bouton_amend(frm);
            return;   // aucun autre bouton
        }
		// ── Rejet simple (docstatus=2, Amend autorisé) ──────────────────
		if (frm.doc.docstatus === 2) return;   // annulé Frappe → rien
		
		// ── Draft (docstatus=0) : Envoyer au comptable ──────────────────
        if (docst === 0 && statut === 'En Attente') {
            frm.add_custom_button(__('Envoyer au Comptable'), () => {
                dialog_envoyer_au_comptable(frm);
            }, __('Actions'));
        }

        // ── Soumis (docstatus=1) : actions comptable ────────────────────
        if (docst === 1 && statut === 'Envoyé Comptable') {
            frm.add_custom_button(__('Admettre (Payé)'), () => {
                dialog_admettre_mandat(frm);
            }, __('Actions Comptable'));

            frm.add_custom_button(__('Rejeter'), () => {
                dialog_rejeter_mandat(frm, false);
            }, __('Actions Comptable'));

            frm.add_custom_button(__('Rejet Définitif'), () => {
                dialog_rejeter_mandat(frm, true);
            }, __('Actions Comptable'));
        }

        // ── Draft après Amend (docstatus=0, rejeté) : corrections ───────
        if (docst === 0 && frm.doc.amended_from) {
            frm.add_custom_button(__('Marquer Corrigé'), () => {
                dialog_marquer_corrige(frm);
            }, __('Actions'));
        }

        // ── Annulé Définitif : bloquer le bouton Amend ──────────────────
        if (docst === 2 && statut === 'Annulé Définitif') {
            // Cacher le bouton Amend natif de Frappe
            setTimeout(() => {
                frm.page.btn_secondary && frm.page.btn_secondary.hide();
                frm.page.wrapper.find('.btn-amend, [data-label="Amend"]').hide();
            }, 200);
        }

		// ── Service Budget : marquer corrigé après rejet simple ──
        if (statut === "Rejeté") {
            frm.add_custom_button(__("Marquer Corrigé"), () => {
                dialog_marquer_corrige(frm);
            }, __("Actions"));
        }
        // Marquer Payé
        // if (frm.doc.status_admission === 'Admis') {
        //     frm.add_custom_button(__('Marquer Payé'), () => {
        //         frm.trigger('dialog_payer');
        //     }, __('Actions'));
        // }

   		// // ✅ Bouton Charger Factures (seulement pour Fiche Depense + Fournisseur Unique)
    	// if (frm.doc.type_source === 'Fiche Depense' 
	    //     && frm.doc.fiche_depense
	    //     && frm.doc.type_creancier === 'Fournisseur Unique'
	    //     && frm.doc.fournisseur
	    //     && !frm.doc.__islocal) {
	    //    
	    //     frm.add_custom_button(__(' Charger Factures'), function() {
	    //         frm.trigger('dialog_charger_factures');
	    //     }, __('Actions'));
    	// }
    			
        // Voir Source
        if (frm.doc.depense_interne) {
            frm.add_custom_button(__('Voir Dépense Interne'), () => {
                frappe.set_route('Form', 'Depense Interne', frm.doc.depense_interne);
            });
        }
        if (frm.doc.situation_paiement) {
            frm.add_custom_button(__('Voir Situation Paiement'), () => {
                frappe.set_route('Form', 'Situation Paiement', frm.doc.situation_paiement);
            });
        }
        if (frm.doc.fiche_depense) {
            frm.add_custom_button(__('Voir Fiche Dépense'), () => {
                frappe.set_route('Form', 'Fiche Budgetaire', frm.doc.fiche_depense);
            });
        }

        // // Imprimer
		
		frm.add_custom_button(__('Mandat'), () => {
            frappe.utils.print(frm.doc.doctype, frm.doc.name, 'Mondat');
        }, __('Imprimer'));

        // Sous-bouton pour Facture
		if (frm.doc.fournisseur){
			frm.add_custom_button(__('Facture'), () => {
				frappe.utils.print(frm.doc.doctype, frm.doc.name, 'etat_payement_facture');
			}, __('Imprimer'));
		}
        // Sous-bouton pour Remboursement
		if (frm.doc.fiche_depense) {
			frm.add_custom_button(__('Remboursement'), () => {
				frappe.utils.print(frm.doc.doctype, frm.doc.name, 'etat_rembourcement_mission');
			}, __('Imprimer'));
		}
        // Sous-bouton pour Mission
		if (frm.doc.depense_interne) {
			frm.add_custom_button(__('Mission'), () => {
				frappe.utils.print(frm.doc.doctype, frm.doc.name, 'etat_payement_mission');
			}, __('Imprimer'));
		}
        // ordre virement banque:
		if ((frm.doc.type_compte === "Banque") && (frm.doc.type_creancier === "Fournisseur Unique") ) {
			frm.add_custom_button(__('Ordre virement'), () => {
				frappe.utils.print(frm.doc.doctype, frm.doc.name, 'ordre_virement_banque');
			}, __('Imprimer'));
		}
		// ordre virement ccp:
		if (frm.doc.type_compte === "CCP") {
			frm.add_custom_button(__('Ordre virement'), () => {
				frappe.utils.print(frm.doc.doctype, frm.doc.name, 'ordre_virement_2');
			}, __('Imprimer'));
		}

        // Sous-bouton pour Virement
        frm.add_custom_button(__('Etat virement'), () => {
            frappe.utils.print(frm.doc.doctype, frm.doc.name, 'etat_virement');
        }, __('Imprimer'));
       
    },
		
    // ══════════════════════════════════════════
    //  DIALOGUES
    // ══════════════════════════════════════════
	dialog_choisir_beneficiaires(frm) {
		if (!frm.frais_mission_beneficiaires || frm.frais_mission_beneficiaires.length === 0) {
			frappe.msgprint(__('Aucun bénéficiaire trouvé pour ce frais de mission.'));
			return;
		}

		frappe.call({
			method: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.get_personnes_deja_mandatees',
			args: {
				fiche_depense: frm.doc.fiche_depense,
				mandat_actuel: frm.doc.name
			},
			callback(r) {
				if (r.exc) return;

				let deja_pris        = r.message || [];
				let beneficiaires    = frm.frais_mission_beneficiaires;
				let selected         = (frm.doc.liste_personnes || []).map(row => row.personne);

				let benefs_disponibles = beneficiaires.filter(b =>
					!deja_pris.includes(b.personne) || selected.includes(b.personne)
				);

				if (benefs_disponibles.length === 0) {
					frappe.msgprint(__('Tous les bénéficiaires de ce frais de mission ont déjà été mandatés.'));
					return;
				}

				let options = benefs_disponibles.map(b => ({
					label:   `${b.nom_prenom} (${b.type_compte}) - ${format_currency(b.montant_mission)} DA`,
					value:   b.personne,
					checked: selected.includes(b.personne)
				}));

				const dlg = new frappe.ui.Dialog({
					title: __('Sélectionner les bénéficiaires à mandater'),
					fields: [{
						fieldtype: 'MultiCheck',
						fieldname: 'beneficiaires',
						label:     __('Bénéficiaires'),
						options:   options,
						columns:   3
					}],
					primary_action_label: __('Valider'),
					primary_action(values) {
						let selected_vals = values.beneficiaires || [];

						if (selected_vals.length === 0) {
							frappe.msgprint(__('Veuillez sélectionner au moins un bénéficiaire.'));
							return;
						}

						let selected_benefs = beneficiaires.filter(b => selected_vals.includes(b.personne));

						// Vérifier l'homogénéité des types de compte
						let types = new Set(selected_benefs.map(b => b.type_compte));
						if (types.size > 1) {
							frappe.msgprint(__(
								'Impossible de mélanger des bénéficiaires avec des types de compte différents ' +
								'(Banque et CCP) dans un même mandat.'
							));
							return;
						}

						let type_unique = Array.from(types)[0];

						// ── Cas multi-bénéficiaires ─────────────────────────────────────────────────
						if (selected_benefs.length > 1) {
							let type_creancier = type_unique === 'Banque' ? 'Divers Banque' : 'Divers CCP';
							let header = {
								nom:          'DIVERS',
								compte:       'DIVERS',
								type_compte:  type_unique,
								domicile:     type_unique === 'Banque' ? 'DIVERS Banque' : 'DIVERS CCP',
								numero_agence: ''
							};

							// Récupérer banque/agence pour chaque bénéficiaire Banque en parallèle
							let promises = selected_benefs.map(b => {
								if (b.type_compte === 'Banque') {
									return frappe.db
										.get_value(b.type_personne_doctype, b.personne, ['banque', 'numero_agence'])
										.then(res => ({
											personne:      b.personne,
											banque:        res?.message?.banque        || '',
											numero_agence: res?.message?.numero_agence || ''
										}))
										.catch(() => ({
											personne: b.personne, banque: '', numero_agence: ''
										}));
								}
								return Promise.resolve({ personne: b.personne, banque: '', numero_agence: '' });
							});

							Promise.all(promises).then(banque_data => {
								finaliser(type_creancier, header, selected_benefs, banque_data);
							});

						// ── Cas bénéficiaire unique ─────────────────────────────────────────────────
						} else {
							let b             = selected_benefs[0];
							let type_creancier = 'Liste Personnes';

							if (b.type_compte === 'CCP') {
								let header = {
									nom:          b.nom_prenom,
									compte:       b.compte,
									type_compte:  'CCP',
									domicile:     'CCP',
									numero_agence: ''
								};
								finaliser(type_creancier, header, selected_benefs, [
									{ personne: b.personne, banque: '', numero_agence: '' }
								]);

							} else if (b.type_compte === 'Banque') {
								// FIX : get_doc retourne le doc directement, pas doc.message
								frappe.db.get_doc(b.type_personne_doctype, b.personne)
									.then(doc => {
										let header = {
											nom:          b.nom_prenom,
											compte:       b.compte,
											type_compte:  'Banque',
											domicile:     doc.banque        || 'Banque',
											numero_agence: doc.numero_agence || ''
										};
										finaliser(type_creancier, header, selected_benefs, [
											{
												personne:      b.personne,
												banque:        doc.banque        || '',
												numero_agence: doc.numero_agence || ''
											}
										]);
									})
									.catch(err => {
										console.error('Erreur get_doc:', err);
										frappe.msgprint(__('Erreur lors de la récupération des données bancaires.'));
									});
							}
						}

						// ── finaliser ───────────────────────────────────────────────────────────────
						// FIX : appelée UNE SEULE FOIS, après résolution de toutes les promesses.
						// Les données bancaires sont passées en paramètre (banque_data) pour éviter
						// tout appel réseau supplémentaire et tout conflit asynchrone.
						function finaliser(type_creancier, header, benefs, banque_data) {
							frm.set_value('type_creancier',    type_creancier);
							frm.set_value('nom_raison_sociale', header.nom);
							frm.set_value('numero_compte',     header.compte);
							frm.set_value('type_compte',       header.type_compte);
							frm.set_value('domicile',          header.domicile);
							frm.set_value('numero_agence',     header.numero_agence);

							frm.clear_table('liste_personnes');

							benefs.forEach(b => {
								let info = banque_data.find(d => d.personne === b.personne) || {};
								frm.add_child('liste_personnes', {
									type_personne:  b.type_personne_doctype,
									personne:       b.personne,
									nom_prenom:     b.nom_prenom,
									grade:          b.grade,
									type_compte:    b.type_compte,
									numero_compte:  b.compte,
									montant:        b.montant_mission,
									banque:         info.banque        || '',
									numero_agence:  info.numero_agence || ''
								});
							});

							// FIX : refresh_field appelé UNE SEULE FOIS, après que tout soit prêt
							frm.refresh_field('liste_personnes');
							frm.trigger('recalcul_total');
							dlg.hide();
						}
					}
				});

				dlg.show();
			}
		});
	},

	// dialog_choisir_beneficiaires(frm) {
	// 	if (!frm.frais_mission_beneficiaires || frm.frais_mission_beneficiaires.length === 0) {
	// 		frappe.msgprint(__('Aucun bénéficiaire trouvé pour ce frais de mission.'));
	// 		return;
	// 	}

	// 	// Recharger les personnes déjà mandatées (hors mandat actuel)
	// 	frappe.call({
	// 		method: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.get_personnes_deja_mandatees',
	// 		args: {
	// 			fiche_depense: frm.doc.fiche_depense,
	// 			mandat_actuel: frm.doc.name
	// 		},
	// 		callback(r) {
	// 			if (r.exc) return;
	// 			let deja_pris = r.message || [];
	// 			let beneficiaires = frm.frais_mission_beneficiaires;
	// 			let selected = (frm.doc.liste_personnes || []).map(row => row.personne);

	// 			// Filtrer : garder ceux qui ne sont pas déjà mandatés ailleurs, ou qui sont déjà dans la sélection actuelle
	// 			let benefs_disponibles = beneficiaires.filter(b => 
	// 				!deja_pris.includes(b.personne) || selected.includes(b.personne)
	// 			);

	// 			if (benefs_disponibles.length === 0) {
	// 				frappe.msgprint(__('Tous les bénéficiaires de ce frais de mission ont déjà été mandatés.'));
	// 				return;
	// 			}

	// 			let options = benefs_disponibles.map(b => ({
	// 				label: `${b.nom_prenom} (${b.type_compte}) - ${format_currency(b.montant_mission)} DA`,
	// 				value: b.personne,
	// 				checked: selected.includes(b.personne)
	// 			}));

	// 			const dlg = new frappe.ui.Dialog({
	// 				title: __('Sélectionner les bénéficiaires à mandater'),
	// 				fields: [{
	// 					fieldtype: 'MultiCheck',
	// 					fieldname: 'beneficiaires',
	// 					label: __('Bénéficiaires'),
	// 					options: options,
	// 					columns: 3
	// 				}],
	// 				primary_action_label: __('Valider'),
	// 				primary_action(values) {
	// 					let selected_vals = values.beneficiaires || [];
	// 					if (selected_vals.length === 0) {
	// 						frappe.msgprint(__('Veuillez sélectionner au moins un bénéficiaire.'));
	// 						return;
	// 					}

	// 					// Récupérer les bénéficiaires complets
	// 					let selected_benefs = beneficiaires.filter(b => selected_vals.includes(b.personne));

	// 					// Vérifier l'homogénéité des types de compte
	// 					let types = new Set(selected_benefs.map(b => b.type_compte));
	// 					if (types.size > 1) {
	// 						frappe.msgprint(__('Impossible de mélanger des bénéficiaires avec des types de compte différents (Banque et CCP) dans un même mandat.'));
	// 						return;
	// 					}

	// 					let type_unique = Array.from(types)[0];

	// 					// Déterminer le type de créancier et l'en-tête
	// 					let type_creancier;
	// 					let header = { nom: '', compte: '', type_compte: '', domicile: '', numero_agence: ''};

	// 					// if (frm.frais_mission_mixtes) {
	// 					// 	// Si le frais mission original est mixte, on force Divers Banque ou Divers CCP
	// 					// 	type_creancier = type_unique === 'Banque' ? 'Divers Banque' : 'Divers CCP';
	// 					// 	header = {
	// 					// 		nom: 'DIVERS',
	// 					// 		compte: 'DIVERS',
	// 					// 		type_compte: type_unique,
	// 					// 		domicile: type_unique
	// 					// 	};
	// 					// } else {
	// 						// on utiliser Liste Personnes pour un seul bénéficiaire
	// 					if (selected_benefs.length === 1) {
	// 						type_creancier = 'Liste Personnes';
	// 						let b = selected_benefs[0];
	// 						// Déterminer le domicile selon le type de compte
	// 						if (b.type_compte === 'CCP') {
	// 							header = {
	// 								nom: b.nom_prenom,
	// 								compte: b.compte,
	// 								type_compte: b.type_compte,
	// 								domicile: 'CCP',
	// 								numero_agence: ''
	// 							};
	// 							finaliser();
	// 						} else if (b.type_compte === 'Banque') {
	// 							// Récupérer la banque depuis le doctype correspondant (asynchrone)
	// 							frappe.db.get_doc(b.type_personne_doctype, b.personne)
	// 								.then(doc => {
	// 									let domicile = doc.banque || 'Banque';
	// 									let num_agence = doc.numero_agence || '';
	// 									header = {
	// 										nom: b.nom_prenom,
	// 										compte: b.compte,
	// 										type_compte: b.type_compte,
	// 										domicile: domicile,
	// 										numero_agence: num_agence
	// 									};
	// 									finaliser();
	// 								});
	// 							return; // On attend la promesse avant de continuer
	// 						}
	// 					} else {
	// 						type_creancier = type_unique === 'Banque' ? 'Divers Banque' : 'Divers CCP';
	// 						header = {
	// 							nom: 'DIVERS',
	// 							compte: 'DIVERS',
	// 							type_compte: type_unique,
	// 							domicile: type_unique === 'Banque' ? 'DIVERS Banque' : 'DIVERS CCP',
	// 							numero_agence: ''
	// 						};
	// 					}
	// 					// }
						
	// 					function finaliser() {
	// 						frm.set_value('type_creancier', type_creancier);
	// 						frm.set_value('nom_raison_sociale', header.nom);
	// 						frm.set_value('numero_compte', header.compte);
	// 						frm.set_value('type_compte', header.type_compte);
	// 						frm.set_value('domicile', header.domicile);
	// 						frm.set_value('numero_agence', header.numero_agence);

	// 						frm.clear_table('liste_personnes');
	// 						selected_benefs.forEach(b => {
	// 							let row = frm.add_child('liste_personnes');
	// 							row.type_personne = b.type_personne_doctype;
	// 							row.personne = b.personne;
	// 							row.nom_prenom = b.nom_prenom;
	// 							row.grade = b.grade;
	// 							row.type_compte = b.type_compte;
	// 							row.numero_compte = b.compte;
	// 							row.montant = b.montant_mission;
	// 							if (b.type_compte === 'Banque') {
	// 								frappe.db.get_value(b.type_personne_doctype, b.personne, ['banque', 'numero_agence'])
	// 									.then(r => {
	// 										if (r && r.message) {
	// 											row.banque = r.message.banque;
	// 											row.numero_agence = r.message.numero_agence;
	// 										}
	// 									})
	// 									.catch(err => {
	// 										console.error('Erreur get_value:', err);
	// 									});
	// 							}
	// 						});
							
	// 						frm.refresh_field('liste_personnes');
	// 						frm.trigger('recalcul_total');

	// 						dlg.hide();
	// 					}

	// 					// Appeler finaliser() directement si ce n'est pas déjà fait dans le cas Banque asynchrone
	// 					if (header.nom) finaliser();
	// 				}

	// 			});
	// 			dlg.show();
	// 		}
	// 	});
	// },

	//
    // dialog_admettre(frm) {
    //     const d = new frappe.ui.Dialog({
    //         title: __('Admission du Mandat'),
    //         fields: [
    //             {
    //                 fieldtype: 'Data',
    //                 fieldname: 'numero_admission',
    //                 label: __('N° Admission'),
    //                 reqd: 1
    //             },
    //             {
    //                 fieldtype: 'Date',
    //                 fieldname: 'date_admission',
    //                 label: __('Date Admission'),
    //                 default: frappe.datetime.get_today(),
    //                 reqd: 1
    //             },
    //             {
    //                 fieldtype: 'Data',
    //                 fieldname: 'numero_jc',
    //                 label: __('N° JC')
    //             }
    //         ],
    //         primary_action_label: __('Admettre'),
    //         primary_action(values) {
    //             frm.set_value('status_admission', 'Admis');
    //             frm.set_value('numero_admission', values.numero_admission);
    //             frm.set_value('date_admission', values.date_admission);
    //             frm.set_value('numero_jc', values.numero_jc);
    //             frm.save();
    //             d.hide();
    //         }
    //     });
    //     d.show();
    // },

    // dialog_rejeter(frm) {
    //     const d = new frappe.ui.Dialog({
    //         title: __('Rejet du Mandat'),
    //         fields: [
    //             {
    //                 fieldtype: 'Small Text',
    //                 fieldname: 'motif_rejet',
    //                 label: __('Motif du Rejet'),
    //                 reqd: 1
    //             }
    //         ],
    //         primary_action_label: __('Rejeter'),
    //         primary_action(values) {
    //             frm.set_value('status_admission', 'Rejeté');
    //             frm.set_value('motif_rejet', values.motif_rejet);
    //             frm.save();
    //             d.hide();
    //         }
    //     });
    //     d.show();
    // },

    // dialog_payer(frm) {
    //     const d = new frappe.ui.Dialog({
    //         title: __('Marquer Payé'),
    //         fields: [
	// 			{
	// 				fieldtype: 'Data',
	// 				fieldname: 'numero_mandat',
	// 				label: __('N° Mandat définitif'),
	// 				reqd: 1
	// 			},
	// 			{
	// 				fieldtype: 'Date',
	// 				fieldname: 'date_mandat',
	// 				label: __('Date du Mandat'),
	// 				default: frappe.datetime.get_today(),
	// 				reqd: 1
	// 			},
    //             {
    //                 fieldtype: 'Date',
    //                 fieldname: 'date_paiement',
    //                 label: __('Date de Paiement'),
    //                 default: frappe.datetime.get_today(),
    //                 reqd: 1
    //             }
    //         ],
    //         primary_action_label: __('Confirmer'),
    //         primary_action(values) {
	// 			frm.set_value('numero_mandat', values.numero_mandat);
    //         	frm.set_value('date_mandat', values.date_mandat);
    //             frm.set_value('status_admission', 'Payé');
    //             frm.set_value('date_paiement', values.date_paiement);
    //             frm.save();
    //             d.hide();
    //         }
    //     });
    //     d.show();
    // },

	// dialog_charger_factures(frm) {
	//     if (!frm.doc.fiche_depense || !frm.doc.fournisseur) {
	//         frappe.msgprint(__('Fiche Dépense et Fournisseur requis'));
	//         return;
	//     }
	//     
	//     // ✅ Appeler l'API pour récupérer les factures disponibles
	//     frappe.call({
	//         method: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.get_factures_disponibles_mandat',
	//         args: {
	//             fiche_depense: frm.doc.fiche_depense,
	//             fournisseur: frm.doc.fournisseur
	//         },
	//         callback(r) {
	//             if (!r.exc && r.message && r.message.length > 0) {
	//                 const factures = r.message;
	//                 
	//                 // ✅ Créer dialog avec sélection multiple
	//                 let html = `
	//                     <div style="max-height: 400px; overflow-y: auto;">
	//                         <table class="table table-bordered table-hover">
	//                             <thead>
	//                                 <tr style="position: sticky; top: 0; background: white; z-index: 10;">
	//                                     <th style="width: 50px;">
	//                                         <input type="checkbox" id="select_all_factures" 
	//                                                onchange="toggle_all_factures(this.checked)">
	//                                     </th>
	//                                     <th>N° Facture</th>
	//                                     <th>Date</th>
	//                                     <th>Montant TTC</th>
	//                                     <th>Référence</th>
	//                                 </tr>
	//                             </thead>
	//                             <tbody>
	//                 `;
	//                 
	//                 factures.forEach(f => {
	//                     const ref = f.bon_commande || f.convention || '';
	//                     html += `
	//                         <tr>
	//                             <td>
	//                                 <input type="checkbox" class="facture-checkbox" 
	//                                        value="${f.name}" 
	//                                        data-numero="${f.numero_facture}"
	//                                        data-date="${f.date_facture}"
	//                                        data-montant="${f.montant_ttc}">
	//                             </td>
	//                             <td>${f.numero_facture}</td>
	//                             <td>${frappe.datetime.str_to_user(f.date_facture)}</td>
	//                             <td style="text-align: right; font-weight: bold;">
	//                                 ${format_currency(f.montant_ttc)} DA
	//                             </td>
	//                             <td><small>${ref}</small></td>
	//                         </tr>
	//                     `;
	//                 });
	//                 
	//                 html += `
	//                             </tbody>
	//                         </table>
	//                     </div>
	//                     <script>
	//                         function toggle_all_factures(checked) {
	//                             document.querySelectorAll('.facture-checkbox').forEach(cb => {
	//                                 cb.checked = checked;
	//                             });
	//                         }
	//                     </script>
	//                 `;
	//                 
	//                 const d = new frappe.ui.Dialog({
	//                     title: __('Sélection des Factures à Mandater'),
	//                     fields: [
	//                         {
	//                             fieldtype: 'HTML',
	//                             fieldname: 'factures_html',
	//                             options: html
	//                         }
	//                     ],
	//                     size: 'large',
	//                     primary_action_label: __('Ajouter les factures sélectionnées'),
	//                     primary_action() {
	//                         const checkboxes = document.querySelectorAll('.facture-checkbox:checked');
	//                         
	//                         if (checkboxes.length === 0) {
	//                             frappe.msgprint(__('Aucune facture sélectionnée'));
	//                             return;
	//                         }
	//                         
	//                         // ✅ Vérifier les doublons avant d'ajouter
	//                         const factures_existantes = (frm.doc.factures_a_mandater || [])
	//                             .map(f => f.facture_fournisseur);
	//                         
	//                         let nb_ajoutees = 0;
	//                         let nb_doublons = 0;
	//                         
	//                         checkboxes.forEach(cb => {
	//                             const facture_id = cb.value;
	//                             
	//                             // ✅ Vérifier doublon
	//                             if (factures_existantes.includes(facture_id)) {
	//                                 nb_doublons++;
	//                                 return;
	//                             }
	//                             
	//                             // Ajouter
	//                             const row = frm.add_child('factures_a_mandater', {
	//                                 facture_fournisseur: facture_id,
	//                                 numero_facture: cb.dataset.numero,
	//                                 date_facture: cb.dataset.date,
	//                                 montant: parseFloat(cb.dataset.montant)
	//                             });
	//                             
	//                             nb_ajoutees++;
	//                             factures_existantes.push(facture_id);
	//                         });
	//                         
	//                         frm.refresh_field('factures_a_mandater');
	//                         
	//                         // Message
	//                         let msg = `${nb_ajoutees} facture(s) ajoutée(s)`;
	//                         if (nb_doublons > 0) {
	//                             msg += `<br>${nb_doublons} doublon(s) ignoré(s)`;
	//                         }
	//                         
	//                         frappe.show_alert({
	//                             message: __(msg),
	//                             indicator: nb_doublons > 0 ? 'orange' : 'green'
	//                         });
	//                         
	//                         // Calculer total
	//                         frm.trigger('recalculer_montant_total');
	//                         
	//                         d.hide();
	//                     }
	//                 });
	//                 
	//                 d.show();
	//                 
	//             } else {
	//                 frappe.msgprint({
	//                     title: __('Aucune Facture Disponible'),
	//                     message: __(
	//                         'Aucune facture disponible pour :<br>' +
	//                         '- Fournisseur : {0}<br>' +
	//                         '- BC/Convention de la fiche<br>' +
	//                         '- Non déjà mandatée',
	//                         [frm.doc.fournisseur]
	//                     ),
	//                     indicator: 'orange'
	//                 });
	//             }
	//         }
	//     });
	// },
	// ══════════════════════════════════════════
	//  CHANGEMENTS : CHOIX BENEFICIAIRES
	// ══════════════════════════════════════════

	btn_choisir_beneficiaires(frm) {
   		frm.trigger('dialog_choisir_beneficiaires');
	},
	// ══════════════════════════════════════════
	//  CHANGEMENTS : TYPE SOURCE
	// ══════════════════════════════════════════
	
	type_source(frm) {
		frm._fiche_info = null;  // vider le cache
	    frm.trigger('set_champs_visibles');
		frm.trigger('bloquer_table_factures');
	    // Effacer les autres sources
	    if (frm.doc.type_source !== 'Depense Interne') {
	        frm.set_value('depense_interne', '');		
	    }
	
	    if (frm.doc.type_source !== 'Fiche Depense') {
	        frm.set_value('fiche_depense', '');
			frm.set_value('situation_paiement', '');
	    }
	},
	
	// ══════════════════════════════════════════
	//  DÉPENSE INTERNE (A POSTERIORI)
	// ══════════════════════════════════════════
	
	depense_interne(frm) {
	    if (!frm.doc.depense_interne) return;
	    
	    frappe.call({
	        method: 'frappe.client.get',
	        args: {
	            doctype: 'Depense Interne',
	            name: frm.doc.depense_interne
	        },
	        callback(r) {
	            if (!r.exc && r.message) {
	                const dep = r.message;
	                
	                // Vérifier statut
	                if (dep.status !== 'Validé' && dep.status !== 'Envoyé Comptable') {
	                    frappe.msgprint({
	                        title: __('Statut Invalide'),
	                        message: __('La Dépense Interne doit être au statut "Validé" ou "Envoyé Comptable".'),
	                        indicator: 'red'
	                    });
	                    frm.set_value('depense_interne', '');
	                    return;
	                }
	                
	                // Vérifier si déjà mandatée
	                if (dep.mandat_paiement && dep.mandat_paiement !== frm.doc.name) {
	                    frappe.msgprint({
	                        title: __('Déjà Mandatée'),
	                        message: __('Cette Dépense Interne a déjà un mandat : {0}', [dep.mandat_paiement]),
	                        indicator: 'red'
	                    });
	                    frm.set_value('depense_interne', '');
	                    return;
	                }
	                
	                // Remplir les champs immédiatement
	                frm.set_value('article', dep.article);
	                frm.set_value('chapitre', dep.chapitre);
	                frm.set_value('partition', dep.partition);
	                
	                // Charger les infos article et chapitre
					frappe.db.get_value('Budget Article', dep.article, ['code_article', 'intitule_article'], (r) => {
						frm.set_value('code_article', r.code_article);
						frm.set_value('intitule_article', r.intitule_article);
					});
					frappe.db.get_value('Budget Chapitre', dep.chapitre, ['code', 'intitule'], (r) => {
						frm.set_value('code_chapitre', r.code);
						frm.set_value('intitule_chapitre', r.intitule);
					});
							
	                // Type de dépense
	                if (dep.type_depense === 'Fournisseur') {
	                    frm.set_value('type_creancier', 'Fournisseur Unique');
	                    frm.set_value('fournisseur', dep.fournisseur);
	                    
	                    // Attendre que fournisseur soit chargé
	                    setTimeout(() => {
	                        frappe.db.get_doc('Fournisseur', dep.fournisseur).then(fourn => {
	                            frm.set_value('nom_raison_sociale', fourn.raison_sociale);
	                            frm.set_value('domicile', fourn.banque || '');
	                            frm.set_value('numero_compte', fourn.numero_compte || '');
	                            frm.set_value('type_compte', fourn.type_compte || '');
	                            frm.set_value('numero_agence', fourn.numero_agence || '');
	                        });
	                    }, 300);
	                    
	                    // Factures
	                    if (dep.factures && dep.factures.length > 0) {
	                        let factures_list = [];
	                        dep.factures.forEach(f => {
	                            factures_list.push(`Facture ${f.numero_facture} du ${f.date_facture} - ${format_currency(f.montant)} DA`);
	                        });
	                        frm.set_value('factures_concernees', factures_list.join('\n'));
	                    }
	                    
	                    frm.set_value('montant_total', dep.montant_total);
						
						frm.trigger('bloquer_table_factures');
	                    
	                } else if (dep.type_depense === 'Frais Mission') {
	                    // Frais Mission
	                    if (dep.beneficiaires.length === 1) {
	                        frm.set_value('type_creancier', 'Liste Personnes');
	                        const benef = dep.beneficiaires[0];
							// Déterminer le domicile selon le type de compte
							if (benef.type_compte === 'CCP') {
								domicile_p = 'CCP';
								frm.set_value('nom_raison_sociale', benef.nom_prenom);
								frm.set_value('numero_compte', benef.numero_compte);
								frm.set_value('type_compte', benef.type_compte);
								frm.set_value('domicile', domicile_p);
							} else if (benef.type_compte === 'Banque') {
								// Récupérer la banque et numero_agence depuis le doctype correspondant
								frappe.call({
									method: 'frappe.client.get_value',
									args: {
										doctype: benef.type_personne,
										name: benef.personne,
										fieldname: ['banque', 'numero_agence']
									}
								}).then(r => {
										domicile_p = r.message.banque || 'Banque';
										frm.set_value('nom_raison_sociale', benef.nom_prenom);
										frm.set_value('numero_compte', benef.numero_compte);
										frm.set_value('type_compte', benef.type_compte);
										frm.set_value('domicile', r.message.banque);
										frm.set_value('numero_agence', r.message.numero_agence || '');
									});
							}
							// // Déterminer le domicile selon le type de compte
							// 	let domicile_p = '';
							// 	if (benef.type_compte === 'CCP') {
							// 		domicile_p = 'CCP';
							// 	} else if (benef.type_compte === 'Banque') {
							// 		// Récupérer la banque depuis le doctype correspondant
							// 		frappe.db.get_value(benef.type_personne, benef.personne, 'banque')
							// 			.then(r => {
							// 				domicile_p = r.message.banque || 'Banque';
							// 			});
							// 	}
	                        // frm.set_value('nom_raison_sociale', benef.nom_prenom);
	                        // frm.set_value('numero_compte', benef.numero_compte);
	                        // frm.set_value('type_compte', benef.type_compte);
	                        // frm.set_value('domicile', domicile_p);
	                    } else {
	                        frm.set_value('type_creancier', `Divers ${dep.type_compte_mission}`);
	                        frm.set_value('nom_raison_sociale', 'DIVERS');
	                        frm.set_value('domicile', `Divers ${dep.type_compte_mission}`);
	                        frm.set_value('numero_compte', '');
	                        frm.set_value('type_compte', dep.type_compte_mission);
	                    }
	                    
	                    // Copier bénéficiaires
						frm.clear_table('liste_personnes');
						dep.beneficiaires.forEach(benef => {
							let row = frm.add_child('liste_personnes', {
								type_personne: benef.type_personne,
								personne: benef.personne,
								nom_prenom: benef.nom_prenom,
								grade: benef.grade,
								type_compte: benef.type_compte,
								numero_compte: benef.numero_compte,
								montant: benef.montant,
							});

							if (benef.type_compte === 'Banque') {
								frappe.db.get_value(benef.type_personne, benef.personne, ['banque', 'numero_agence'])
									.then(r => {
										if (r && r.message) {
											row.banque = r.message.banque || '';
											row.numero_agence = r.message.numero_agence || '';
											frm.refresh_field('liste_personnes');
										}
									})
									.catch(err => {
										console.error('Erreur get_value:', err);
									});
							}
						});
	                    // frm.clear_table('liste_personnes');
	                    // dep.beneficiaires.forEach(benef => {
						// 	frm.add_child('liste_personnes', {
						// 		type_personne: benef.type_personne,
						// 		personne: benef.personne,
						// 		nom_prenom: benef.nom_prenom,
						// 		grade: benef.grade,
						// 		type_compte: benef.type_compte,
						// 		numero_compte: benef.numero_compte,
						// 		montant: benef.montant,
						// 		if ( benef.type_compte === 'Banque' ) {
						// 			frappe.db.get_value(benef.type_personne, benef.personne, ['banque', 'numero_aagence'])
						// 				.then ( r => {
						// 					banque: r.message.banque || '',
						// 					numero_agence: r.message.numero_agence || ''
						// 				});
						// 		}
						// 	});
	                        // frm.add_child('liste_personnes', {
	                        //     type_personne: benef.type_personne,
	                        //     personne: benef.personne,
	                        //     nom_prenom: benef.nom_prenom,
	                        //     grade: benef.grade,
	                        //     type_compte: benef.type_compte,
	                        //     numero_compte: benef.numero_compte,
	                        //     montant: benef.montant
	                        // });
	                    //});
	                    frm.refresh_field('liste_personnes');
	                    
	                    frm.set_value('montant_total', dep.montant_total);
	                }
	                
	                // Objet
	                frm.set_value('objet_paiement', dep.objet_depense || 'Paiement Dépense Interne');
	                
	                // Afficher message
	                frappe.show_alert({
	                    message: __('Dépense Interne chargée : {0} - {1} DA', 
	                        [dep.numero_interne, format_currency(dep.montant_total)]),
	                    indicator: 'green'
	                });
					// ✅ Rafraîchir pour que les champs readonly se remplissent
					frm.refresh_fields();
				}
	        }
	    });
	},
	

	// ══════════════════════════════════════════
	//  FICHE DEPENSE (A PRIORI)
	// ══════════════════════════════════════════

	// chargement de la fiche depense
	fiche_depense(frm) {
	    if (!frm.doc.fiche_depense) return;
	    
	     // ✅ Appeler l'API pour charger toutes les infos
    	frappe.call({
        	method: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.charger_info_fiche_depense',
        	args: {
            	fiche_depense: frm.doc.fiche_depense
        	},

	        callback(r) {
	            if (!r.exc && r.message) {
	                const data = r.message;

					// Stocker les infos pour la visibilité conditionnelle
					frm._fiche_info = {
						type_engagement: data.type_engagement
					};
	                
	                // Remplir imputation
	                frm.set_value('article', data.article);
	                frm.set_value('chapitre', data.chapitre);
	                frm.set_value('partition', data.partition);
	                	                
					// ✅ Créancier
					frm.set_value('type_creancier', data.type_creancier);
					if (data.fournisseur) {
						frm.set_value('fournisseur', data.fournisseur);
					}
					if (data.frais_mission_apriori) {
						frm.set_value('frais_mission_apriori', data.frais_mission_apriori);
					}
					if (data.type_engagement === 'Frais Mission' && data.frais_mission_apriori) {
						frappe.db.get_doc('Frais Mission', data.frais_mission_apriori).then(fm => {
							frm.frais_mission_beneficiaires = fm.table_beneficiaires;

							// Déterminer si le frais mission a des types mixtes
							let types = new Set(fm.table_beneficiaires.map(b => b.type_compte).filter(t => t));
							frm.frais_mission_mixtes = types.size > 1;

							// Récupérer les personnes déjà mandatées pour cette fiche
							frappe.call({
								method: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.get_personnes_deja_mandatees',
								args: {
									fiche_depense: frm.doc.fiche_depense,
									mandat_actuel: frm.doc.name
								},
								callback(r2) {
									if (!r2.exc) {
										frm.personnes_deja_mandatees = r2.message || [];
									}
								}
							});

							//frm.clear_table('liste_personnes');
							//frm.refresh_field('liste_personnes');
							frappe.show_alert({
								message: __('Veuillez sélectionner les bénéficiaires à mandater via le bouton "Choisir bénéficiaires".'),
								indicator: 'blue'
							});
						});
					}
	                // Détection d'une convention 
					if (data.type_engagement === 'Convention' ) {
						frappe.db.get_value('Situation Paiement', { convention: data.convention }, 'name').then(res => {
                            if (res &&res.message && res.message.name) {
                                frm.set_value('situation_paiement', res.message.name);
                                // On peut aussi charger le reste à payer
                                frappe.db.get_doc('Situation Paiement', res.message.name).then(sit => {
                                    //frm.set_value('montant_total', sit.reste_a_payer);
                                    frappe.show_alert({
                                        message: __('Convention - Reste à payer : {0} DA', [format_currency(sit.reste_a_payer)]),
                                        indicator: 'blue'
                                    });
                                });
                            } else {
                                frappe.msgprint(__('Aucune situation de paiement trouvée pour cette convention.'));
                            }
                        });

					}				
					
					// ✅ Objet
					if (data.objet) {
						frm.set_value('objet_paiement', data.objet);
					}

	                // ✅ Vérifier si mandat existe déjà

					if (data.type_engagement === 'Bon Commande') {							
						frappe.call({
							method: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.verifier_mandat_existant',
							args: {
								fiche_depense: frm.doc.fiche_depense,
								type_engagement: data.type_engagement
							},
							callback(r2) {
								if (r2.message && r2.message.exists) {
									frappe.msgprint({
										title: __('⚠️ Mandat Existant'),
										message: __(
											'Un mandat existe déjà pour cette fiche :<br>' +
											'<b>{0}</b><br><br>' +
											'Règle : 1 seul mandat par Bon de Commande.',
											[r2.message.mandat]
										),
										indicator: 'orange'
									});
								}
							}	
						});

					}
					// ✅ Message de succès
					frappe.show_alert({
						message: __('Fiche Dépense chargée - {0}', [data.type_engagement]),
						indicator: 'green'
					});
                
					// ✅ Mettre à jour la visibilité des champs
					frm.trigger('set_champs_visibles');
					// ✅ Rafraîchir pour que les champs readonly se remplissent
					frm.refresh_fields();
					
	            }
	        }
	    });

	},
	
	// charger_bc(frm, bon_commande) {
	//     frappe.call({
	//         method: 'frappe.client.get',
	//         args: {
	//             doctype: 'Bon Commande',
	//             name: bon_commande
	//         },
	//         callback(r) {
	//             if (!r.exc && r.message) {
	//                 const bc = r.message;
	                
	//                 // Créancier
	//                 frm.set_value('type_creancier', 'Fournisseur Unique');
	//                 frm.set_value('fournisseur', bc.prestataire);
	                
	//                 // Fetch fournisseur
	//                 frappe.db.get_doc('Fournisseur', bc.prestataire).then(fourn => {
	//                     frm.set_value('nom_raison_sociale', fourn.raison_sociale);
	//                     frm.set_value('domicile', fourn.adresse || '');
	//                     frm.set_value('numero_compte', fourn.numero_compte || '');
	//                     frm.set_value('type_compte', fourn.type_compte || '');
	//                 });
	                
	//                 // Objet
	//                 frm.set_value('objet_paiement', `Paiement BC N° ${bc.numero_bon_commande}`);
	                
	//                 // Charger factures disponibles
	//                 frm.trigger('afficher_factures_disponibles', bon_commande, null);
	//             }
	//         }
	//     });
	// },
	
	// charger_convention(frm, convention) {
	//     frappe.call({
	//         method: 'frappe.client.get',
	//         args: {
	//             doctype: 'Convention',
	//             name: convention
	//         },
	//         callback(r) {
	//             if (!r.exc && r.message) {
	//                 const conv = r.message;
	                
	//                 // Créancier
	//                 frm.set_value('type_creancier', 'Fournisseur Unique');
	//                 frm.set_value('fournisseur', conv.fournisseur);
	                
	//                 // Fetch fournisseur
	//                 frappe.db.get_doc('Fournisseur', conv.fournisseur).then(fourn => {
	//                     frm.set_value('nom_raison_sociale', fourn.raison_sociale);
	//                     frm.set_value('domicile', fourn.adresse || '');
	//                     frm.set_value('numero_compte', fourn.numero_compte || '');
	//                     frm.set_value('type_compte', fourn.type_compte || '');
	//                 });
	                
	//                 // Objet
	//                 frm.set_value('objet_paiement', `Paiement Convention N° ${conv.numero_convention}`);
	                
	//                 // Charger factures disponibles
	//                 frm.trigger('afficher_factures_disponibles', null, convention);
	//             }
	//         }
	//     });
	// },
	
	// afficher_factures_disponibles(frm, bon_commande, convention) {
	//     let filters = {
	//         status: 'En Attente',
	//         mandat_paiement: ['in', ['', null]]
	//     };
	//     
	//     if (bon_commande) {
	//         filters.bon_commande = bon_commande;
	//     } else if (convention) {
	//         filters.convention = convention;
	//     }
	//     
	//     frappe.call({
	//         method: 'frappe.client.get_list',
	//         args: {
	//             doctype: 'Facture Fournisseur',
	//             filters: filters,
	//             fields: ['name', 'numero_facture', 'date_facture', 'montant_ttc']
	//         },
	//         callback(r) {
	//             if (!r.exc && r.message && r.message.length > 0) {
	//                 frappe.msgprint({
	//                     title: __('Factures Disponibles'),
	//                     message: __('{0} facture(s) disponible(s) pour mandatement.<br>Ajoutez-les dans le tableau "Factures à Mandater".', 
	//                         [r.message.length]),
	//                     indicator: 'blue'
	//                 });
	//             } else {
	//                 frappe.msgprint({
	//                     title: __('Aucune Facture'),
	//                     message: __('Aucune facture disponible pour ce BC/Convention.'),
	//                     indicator: 'orange'
	//                 });
	//             }
	//         }
	//     });
	// },
	
    // ══════════════════════════════════════════
    //  CHANGEMENTS : TYPE CREANCIER
    // ══════════════════════════════════════════

    type_creancier(frm) {
        frm.trigger('set_champs_visibles');	
		if (!frm.frais_mission_beneficiaires) return;
		let type = frm.doc.type_creancier;
		let personnes = frm.doc.liste_personnes || [];
		if (personnes.length === 0) return;

		// Vérifier que le type choisi correspond aux personnes présentes
		let types_personnes = new Set(personnes.map(p => p.type_compte));
		if (type === 'Liste Personnes' && personnes.length !== 1) {
			frappe.msgprint(__('Le type "Liste Personnes" nécessite exactement un bénéficiaire.'));
			frm.set_value('type_creancier', '');
			return;
		}
		if (type === 'Divers Banque' && (types_personnes.size !== 1 || !types_personnes.has('Banque'))) {
			frappe.msgprint(__('Le type "Divers Banque" nécessite que tous les bénéficiaires aient un compte Banque.'));
			frm.set_value('type_creancier', '');
			return;
		}
		if (type === 'Divers CCP' && (types_personnes.size !== 1 || !types_personnes.has('CCP'))) {
			frappe.msgprint(__('Le type "Divers CCP" nécessite que tous les bénéficiaires aient un compte CCP.'));
			frm.set_value('type_creancier', '');
			return;
		}

		// Mettre à jour les champs d'en-tête si nécessaire
		if (type === 'Liste Personnes' && personnes.length === 1) {
			let b = personnes[0];
			// Déterminer le domicile selon le type de compte
			let domicile_p = '';
			if (b.type_compte === 'CCP') {
				domicile_p = 'CCP';
			} else if (b.type_compte === 'Banque') {
				// Récupérer la banque et numero_agence depuis le doctype correspondant
				frappe.call({
					method: 'frappe.client.get_value',
					args: {
						doctype: b.type_personne,
						name: b.personne,
						fieldname: ['banque', 'numero_agence']
					}
				}).then(r => {
						domicile_p = r.message.banque || 'Banque';
						frm.set_value('numero_agence', r.message.numero_agence || '');
					});
			}
			frm.set_value('nom_raison_sociale', b.nom_prenom);
			frm.set_value('numero_compte', b.numero_compte);
			frm.set_value('type_compte', b.type_compte);
			frm.set_value('domicile', domicile_p);
		} else if (type === 'Divers Banque') {
			frm.set_value('nom_raison_sociale', 'DIVERS');
			frm.set_value('numero_compte', 'DIVERS');
			frm.set_value('type_compte', 'Banque');
			frm.set_value('domicile', 'Divers Banque');
		} else if (type === 'Divers CCP') {
			frm.set_value('nom_raison_sociale', 'DIVERS CCP');
			frm.set_value('numero_compte', 'DIVERS CCP');
			frm.set_value('type_compte', 'CCP');
			frm.set_value('domicile', 'Divers CCP');
		}

    },

    fournisseur(frm) {
        if (!frm.doc.fournisseur) return;
        
        frappe.db.get_doc('Fournisseur', frm.doc.fournisseur).then(fourn => {
            frappe.show_alert({
                message: __(`Fournisseur : ${fourn.raison_sociale || fourn.name}`),
                indicator: 'green'
            });
        });
    },

    // ══════════════════════════════════════════
    //  RECALCUL MONTANT
    // ══════════════════════════════════════════
	recalculer_montant_total(frm) {
	    if (!frm.doc.factures_a_mandater || frm.doc.factures_a_mandater.length === 0) {
	        frm.set_value('montant_total', 0);
	        frm.set_value('factures_concernees', '');
	        return;
	    }
	    
	    let total = 0;
	    let factures_list = [];
	    
	    frm.doc.factures_a_mandater.forEach(row => {
	        total += flt(row.montant);
	        factures_list.push(`${row.numero_facture} du ${frappe.datetime.str_to_user(row.date_facture)} - ${format_currency(row.montant)} DA`);
	    });
	    
	    frm.set_value('montant_total', total);
	    frm.set_value('factures_concernees', factures_list.join('\n'));
	},
	
    recalcul_total(frm) {
        if (['Liste Personnes', 'Divers Banque', 'Divers CCP'].includes(frm.doc.type_creancier)) {
            const total = (frm.doc.liste_personnes || [])
                .reduce((sum, p) => sum + flt(p.montant), 0);
            frm.set_value('montant_total', total);
        }
    },

   	// ══════════════════════════════════════════
    //  BLOQUER TABLE FACTURES
    // ══════════════════════════════════════════
    
    bloquer_table_factures(frm) {
        /**
         * Rend la table factures_a_mandater en lecture seule
         * si la source est une Dépense Interne de type Fournisseur.
         */
        
        // Vérifier si source = Dépense Interne
        if (frm.doc.type_source === 'Depense Interne' && frm.doc.depense_interne) {
            
            // Récupérer le type de dépense
            frappe.db.get_value('Depense Interne', frm.doc.depense_interne, 'type_depense')
                .then(r => {
                    if (r.message && r.message.type_depense === 'Fournisseur') {
                        
                        //  Bloquer la table factures
                        frm.set_df_property('factures_a_mandater', 'read_only', 1);
                        frm.refresh_field('factures_a_mandater');
                        
                        // Message informatif
                        if (!frm.doc.__factures_locked_msg_shown) {
                            frappe.show_alert({
                                message: __('Les factures sont chargées depuis la Dépense Interne et ne peuvent pas être modifiées.'),
                                indicator: 'blue'
                            });
                            frm.doc.__factures_locked_msg_shown = true;
                        }
                        
                    } else {
                        // Débloquer si ce n'est pas type Fournisseur
                        frm.set_df_property('factures_a_mandater', 'read_only', 0);
                        frm.refresh_field('factures_a_mandater');
                    }
                });
            
        } else {
            // Débloquer si la source n'est pas Dépense Interne
            frm.set_df_property('factures_a_mandater', 'read_only', 0);
            frm.refresh_field('factures_a_mandater');
        }
    },

    // ══════════════════════════════════════════
    //  COLORISATION STATUT
    // ══════════════════════════════════════════

    coloriser_statut(frm) {
        const couleurs = {
            'En Attente': 'orange',
            'Admis': 'blue',
            'Rejeté': 'red',
            'Payé': 'green'
        };
        const status = frm.doc.status_admission || 'En Attente';
        frm.page.set_indicator(__(status), couleurs[status]);
    },

    mode_paiement(frm) {
        frm.trigger('set_champs_visibles');
    }
});


// ══════════════════════════════════════════════
//  DIALOGUES WORKFLOW — FONCTIONS GLOBALES
//  (pas méthodes d'instance — évite le problème
//   frm._methode() qui ne fonctionne pas)
// ══════════════════════════════════════════════
// ══════════════════════════════════════════════
//  MASQUER LE BOUTON AMEND — Annulé Définitif
// ══════════════════════════════════════════════

function masquer_bouton_amend(frm) {
    /**
     * Cache le bouton Amend natif de Frappe de façon robuste.
     * Frappe peut rendre ce bouton après le refresh : on utilise
     * un MutationObserver pour le cacher dès qu'il (ré)apparaît.
     * Le verrou Python (before_amend) garantit qu'un clic éventuel
     * qui passerait quand même serait bloqué côté serveur.
     */
    const do_hide = () => {
        // Bouton principal de la page (btn_secondary = Amend dans Frappe v14-15)
        if (frm.page.btn_secondary) {
            frm.page.btn_secondary.hide();
        }
        // Sélecteurs CSS couvrant différentes versions de Frappe
        frm.page.wrapper.find([
            '.btn-amend',
            '[data-label="Amend"]',
            'button:contains("Amend")',
            '.page-actions button.btn-default',
        ].join(', ')).each(function() {
            if ($(this).text().trim() === 'Amend') {
                $(this).hide();
            }
        });
    };

    // Première passe immédiate
    do_hide();

    // Observer les changements DOM : si Frappe re-rend le bouton, on le cache
    if (frm._amend_observer) {
        frm._amend_observer.disconnect();
    }
    frm._amend_observer = new MutationObserver(() => do_hide());
    frm._amend_observer.observe(
        frm.page.wrapper.find('.page-actions')[0] || frm.page.wrapper[0],
        { childList: true, subtree: true }
    );

    // Sécurité : arrêter l'observation après 5 secondes (le DOM est stable)
    setTimeout(() => {
        if (frm._amend_observer) {
            frm._amend_observer.disconnect();
            frm._amend_observer = null;
        }
    }, 5000);

    // Afficher un indicateur clair
    frm.page.set_indicator(__('Annulé Définitif'), 'red');
    frm.set_read_only(true);
}
function afficher_badge_rejets(frm) {
    const nb = frm.doc.nb_rejets || 0;
    if (nb > 0 && !frm._rejet_badge_ajoute) {
        const couleur = frm.doc.status_admission === 'Annulé Définitif' ? 'red' : 'orange';
        const msg = nb === 1
            ? __('Ce mandat a subi 1 rejet.')
            : __('Ce mandat a subi {0} rejets.', [nb]);
        frm.dashboard.add_comment(msg, couleur, true);
        frm._rejet_badge_ajoute = true;
    }
}

// ── Envoyer au comptable ──────────────────────
function dialog_envoyer_au_comptable(frm) {
	const d = new frappe.ui.Dialog({
		title: __('Envoyer au comptable'),
		fields: [
			{ fieldname: 'date_envoi_comptable', fieldtype: 'Date', label: __('Date d\'envoi') , default: frappe.datetime.get_today(), reqd: 1 }, 
		],
		primary_action_label: __('Envoyer'),
		primary_action(values) {
			frappe.call({
				method: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.envoyer_au_comptable',
				args: {
					mandat_name: frm.doc.name,
					date_envoi_comptable: values.date_envoi_comptable
				},
				callback(r) {
					if (!r.exc) {
						d.hide();
						frm.reload_doc();
						frappe.show_alert({ message: __('Mandat envoyé au comptable.'), indicator: 'green' });
					}
				}
			});
		}
	});
	d.show();
}

// ── Admettre (Payé) ──────────────────────────

function dialog_admettre_mandat(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Admettre le Mandat'),
        fields: [ 
			{ fieldname: 'references_mandat', fieldtype: 'Section Break', label: __('Références Mandat') },
			{ fieldname: 'numero_mandat',   fieldtype: 'Int',   label: __('Mandat N° '), reqd: 1 },
			{ fieldname: 'date_mandat',   fieldtype: 'Date',   label: __('Date Mandat'), default: frappe.datetime.get_today(), reqd: 1 },
            { fieldname: 'numero_admission', fieldtype: 'Data',   label: __('N° Admission'),   reqd: 1 },
            { fieldname: 'date_admission',   fieldtype: 'Date',   label: __('Date Admission'), default: frappe.datetime.get_today(), reqd: 1 },
			{ fieldname: 'references_paiement', fieldtype: 'Section Break', label: __('Références Paiement') },
			{ fieldname: 'mode_paiement', fieldtype: 'Select', label: __('Mode de Paiement'), options: 'Trésor\nChèque Postal\nCaisse', default: 'Trésor', reqd: 1 },
			{ fieldname: 'numero_cheque', fieldtype: 'Data', label: __('N° Chèque') },
			{ fieldname: 'date_cheque', fieldtype: 'Date', label: __('Date Chèque') },
			{ fieldtype: 'Column Break' },
			{ fieldname: 'date_paiement',    fieldtype: 'Date',   label: __('Date de Paiement'), default: frappe.datetime.get_today(), reqd: 1 },
            { fieldname: 'numero_jc',        fieldtype: 'Data',   label: __('N° JC') },
            { fieldtype: 'Section Break', label: __('Comptabilité') },
            { fieldname: 'folio',  fieldtype: 'Data', label: __('Folio') },
            { fieldname: 'mois',   fieldtype: 'Data', label: __('Mois') },
            { fieldtype: 'Column Break' },
            { fieldname: 'ordre',  fieldtype: 'Data', label: __('Ordre') },
        ],
        primary_action_label: __('Admettre et Payer'),
        primary_action(values) {
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.admettre_mandat',
                args: {
                    mandat_name: frm.doc.name,
					numero_mandat: values.numero_mandat,
					date_mandat: values.date_mandat,
                    numero_admission: values.numero_admission,
                    date_admission:   values.date_admission,
					mode_paiement: values.mode_paiement,
					numero_cheque: values.numero_cheque,
					date_cheque: values.date_cheque,
                    date_paiement:    values.date_paiement,
                    folio:  values.folio,
                    mois:   values.mois,
                    ordre:  values.ordre,
                    numero_jc: values.numero_jc,
                },
                callback(r) {
                    if (!r.exc) {
                        d.hide();
                        frm.reload_doc();
                        frappe.show_alert({ message: __('Mandat admis et payé.'), indicator: 'green' });
                    }
                }
            });
        }
    });
    d.show();
}

// ── Rejeter (simple ou définitif) ────────────

function dialog_rejeter_mandat(frm, definitif) {
    const titre = definitif ? __('Rejet Définitif du Mandat') : __('Rejeter le Mandat');
    const avertissement_html = definitif
        ? `<div style="color:var(--red-600);font-weight:500;margin-bottom:8px;padding:8px;border:1px solid var(--red-300);border-radius:4px;">
            ⚠️ ${__('ATTENTION : Ce rejet est définitif. Le mandat et la dépense interne seront annulés et conservés pour traçabilité.')}
           </div>`
        : '';

    const d = new frappe.ui.Dialog({
        title: titre,
        fields: [
            { fieldname: 'html_avert',    fieldtype: 'HTML',       options: avertissement_html },
            { fieldname: 'date_rejet',    fieldtype: 'Date',       label: __('Date du Rejet'),  default: frappe.datetime.get_today(),   reqd: 1 },
            { fieldtype: 'Column Break' },
            { fieldname: 'motif',         fieldtype: 'Small Text', label: __('Motif de Rejet'),    reqd: 1 },
        ],
        primary_action_label: definitif ? __('Confirmer Rejet Définitif') : __('Rejeter'),
        primary_action(values) {
            if (!values.motif || !values.motif.trim()) {
                frappe.msgprint(__('Le motif de rejet est obligatoire.'));
                return;
            }
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.rejeter_mandat',
                args: {
                    mandat_name: frm.doc.name,
                    motif:       values.motif.trim(),
                    date_rejet:  values.date_rejet,
                    definitif:   definitif ? 1 : 0,
                },
                callback(r) {
                    if (!r.exc) {
                        d.hide();
                        frm.reload_doc();
                        frappe.show_alert({
                            message: r.message && r.message.message ? r.message.message : __('Rejet enregistré.'),
                            indicator: definitif ? 'red' : 'orange'
                        });
                    }
                }
            });
        }
    });
    d.show();
}

// ── Marquer corrigé ──────────────────────────

function dialog_marquer_corrige(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Marquer les Corrections Effectuées'),
        fields: [
            { fieldname: 'date_correction',    fieldtype: 'Date',       label: __('Date de Correction'), default: frappe.datetime.get_today(), reqd: 1 },
            { fieldtype: 'Column Break' },
            { fieldname: 'corrections',        fieldtype: 'Small Text', label: __('Corrections apportées'), reqd: 1 },
        ],
        primary_action_label: __('Confirmer et Renvoyer'),
        primary_action(values) {
            if (!values.corrections || !values.corrections.trim()) {
                frappe.msgprint(__('Veuillez décrire les corrections apportées.'));
                return;
            }
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.mandat_paiement.mandat_paiement.marquer_corrige',
                args: {
                    mandat_name:      frm.doc.name,
                    date_correction:  values.date_correction,
                    corrections:      values.corrections.trim(),
                },
                callback(r) {
                    if (!r.exc) {
                        d.hide();
                        frm.reload_doc();
                        frappe.show_alert({ message: __("Corrections enregistrées. Mandat remis en 'En Attente'."), indicator: 'blue' });
                    }
                }
            });
        }
    });
    d.show();
}

// ══════════════════════════════════════════════
//  CHILD TABLE : Facture Mandat Element
// ══════════════════════════════════════════════

frappe.ui.form.on('Facture Mandat Element', {
    
    facture_fournisseur(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.facture_fournisseur) return;
		// Vérifier doublon
        const existants = (frm.doc.factures_a_mandater || []).filter(f => f.facture_fournisseur === row.facture_fournisseur && f.name !== row.name);
        if (existants.length > 0) {
            frappe.msgprint(__('Cette facture est déjà dans la liste.'));
            frappe.model.set_value(cdt, cdn, 'facture_fournisseur', '');
            return;
        }
        // Charger les infos
        frappe.db.get_doc('Facture Fournisseur', row.facture_fournisseur).then(fact => {
            frappe.model.set_value(cdt, cdn, 'numero_facture', fact.numero_facture);
            frappe.model.set_value(cdt, cdn, 'date_facture', fact.date_facture);
            frappe.model.set_value(cdt, cdn, 'montant', fact.montant_ttc);
             frm.trigger('recalculer_montant_total');
            // Recalculer total
            frm.trigger('recalcul_factures');
        });
    },

    factures_a_mandater_remove(frm) {
        frm.trigger('recalcul_factures');
    }
});

frappe.ui.form.on('Mandat Paiement', {
    recalcul_factures(frm) {
        if (frm.doc.type_creancier === 'Fournisseur Unique' && frm.doc.factures_a_mandater) {
            const total = (frm.doc.factures_a_mandater || [])
                .reduce((sum, f) => sum + flt(f.montant), 0);
            frm.set_value('montant_total', total);
        }
    }
});

// ══════════════════════════════════════════════
//  CHILD TABLE : Mandat Personne Element
// ══════════════════════════════════════════════

frappe.ui.form.on('Mandat Personne Element', {

    personne(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.personne || !row.type_personne) return;

        frappe.db.get_doc(row.type_personne, row.personne).then(pers => {
            frappe.model.set_value(cdt, cdn, 'nom_prenom', pers.nom_personne || pers.name);
            frappe.model.set_value(cdt, cdn, 'grade', pers.grade || '');
            frappe.model.set_value(cdt, cdn, 'type_compte', pers.type_compte || '');
            frappe.model.set_value(cdt, cdn, 'numero_compte', pers.numero_compte || '');
        });
    },

    montant(frm) {
        frm.trigger('recalcul_total');
    },

    liste_personnes_remove(frm) {
        frm.trigger('recalcul_total');
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

// Stockage temporaire des bénéficiaires du Frais Mission
// function update_beneficiaires_from_frais_mission(frm) {
//     if (!frm.frais_mission_beneficiaires) return;

//     let type = frm.doc.type_creancier;
//     let filtered = [];
//     let header = { nom: '', compte: '', type_compte: '', domicile: '' };

//     if (type === 'Liste Personnes') {
//         if (frm.frais_mission_beneficiaires.length === 1) {
//             filtered = frm.frais_mission_beneficiaires;
//             let b = filtered[0];
//             header = {
//                 nom: b.nom_prenom,
//                 compte: b.compte,
//                 type_compte: b.type_compte,
//                 domicile: b.type_compte
//             };
//         } else {
//             frappe.msgprint(__('Le type "Liste Personnes" ne peut être utilisé que pour un seul bénéficiaire.'));
//             return;
//         }
//     } else if (type === 'Divers Banque') {
//         filtered = frm.frais_mission_beneficiaires.filter(b => b.type_compte === 'Banque');
//         header = {
//             nom: 'DIVERS',
//             compte: 'DIVERS',
//             type_compte: 'Banque',
//             domicile: 'Banque'
//         };
//     } else if (type === 'Divers CCP') {
//         filtered = frm.frais_mission_beneficiaires.filter(b => b.type_compte === 'CCP');
//         header = {
//             nom: 'DIVERS',
//             compte: 'DIVERS',
//             type_compte: 'CCP',
//             domicile: 'CCP'
//         };
//     } else {
//         // Aucun type sélectionné : vider la table
//         frm.clear_table('liste_personnes');
//         frm.set_value('nom_raison_sociale', '');
//         frm.set_value('numero_compte', '');
//         frm.set_value('type_compte', '');
//         frm.set_value('domicile', '');
//         frm.refresh_field('liste_personnes');
//         return;
//     }

//     // Mettre à jour les champs d'en-tête
//     frm.set_value('nom_raison_sociale', header.nom);
//     frm.set_value('numero_compte', header.compte);
//     frm.set_value('type_compte', header.type_compte);
//     frm.set_value('domicile', header.domicile);

//     // Repeupler la table
//     frm.clear_table('liste_personnes');
//     filtered.forEach(b => {
//         let row = frm.add_child('liste_personnes');
//         row.type_personne = b.type_personne_doctype;
//         row.personne = b.personne;
//         row.nom_prenom = b.nom_prenom;
//         row.grade = b.grade;
//         row.type_compte = b.type_compte;
//         row.numero_compte = b.compte;
//         row.montant = b.montant_mission;
//     });
//     frm.refresh_field('liste_personnes');
// }
