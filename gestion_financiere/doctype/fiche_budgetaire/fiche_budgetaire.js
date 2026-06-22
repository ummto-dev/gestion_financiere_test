// fiche_budgetaire.js  — version complète avec transfert de crédit

frappe.ui.form.on('Fiche Budgetaire', {

    // ══════════════════════════════════════════
    //  CHARGEMENT
    // ══════════════════════════════════════════

    refresh(frm) {
	    frm.trigger('set_queries');
        frm.trigger('set_champs_visibles');
        frm.trigger('setup_indicateur_solde');
        frm.trigger('add_boutons_action');
        frm.trigger('set_champs_readonly');
        frm.trigger('coloriser_statut');
        frm.trigger('bind_ajouter_depenses_button');
        // if (frm.doc.docstatus === 2 ) {
        //     frm.page.hide_menu_item('Amender');
        // }
        if (frm.fields_dict['depenses_regularisees']) {
            frm.fields_dict['depenses_regularisees'].grid.cannot_add_rows = true;
            // ou
            frm.fields_dict['depenses_regularisees'].grid.wrapper.find('.grid-add-row').hide();
        }

    },

    onload(frm) {
        frm.trigger('set_champs_visibles');
    },

    
    // ══════════════════════════════════════════
    //  FILTRES EN CASCADE
    // ══════════════════════════════════════════
    
    set_queries(frm) {
        // 1. Filtrer Titre par Année Budgétaire
        frm.set_query('titre', () => {
            if (!frm.doc.budget_global) {
                frappe.msgprint(__('Veuillez d\'abord sélectionner l\'exercice budgétaire'));
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
	
	    // Filtrer Frais Mission A Priori
    	frm.set_query('frais_mission_apriori', () => {
        	if (!frm.doc.article) {
            	frappe.msgprint(__('Veuillez d\'abord sélectionner l\'article'));
            	return { filters: { name: ['=', ''] } };
       		}
        
        	return {
            	query: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.get_frais_mission_apriori',
            	filters: {
                	article: frm.doc.article,
                    fiche_actuelle: frm.doc.__islocal ? '' : (frm.doc.name || '')
            	}
        	};
    	});
        //Filtrer fiche_budgetaire 
        frm.set_query('fiche_transfert', () => {
            return {
                filters: {
                    annee_budgetaire: frm.doc.annee_budgetaire,
                    budget_global: frm.doc.budget_global,
                    status: ["in", ['Brouillon', 'Signé Doyen', 'Envoyé CF', 'Visé CF']],  // ✅ Seulement les fiches 'Visé CF'
                    docstatus: ['!=', 2]
                }
            };
        });

        // ✅ Ajout du filtre pour S2
        frm.set_query('provision_s1_reference', () => {
            return {
                filters: {
                    article: frm.doc.article,
                    annee_budgetaire: frm.doc.annee_budgetaire,
                    budget_global: frm.doc.budget_global,
                    type_fiche: 'Provision',
                    semestre: 'S1'  // ✅ Seulement les fiches S1
                }
            };
        });
        
        // filtrer provision_reference
        frm.set_query('provision_reference', () => {
			if (!frm.doc.article) {
				frappe.msgprint(__('Veuillez d\'abord sélectionner l\'article'));
				return { filters: { name: ['=', ''] } };
			}
			if (!frm.doc.semestre) {
				frappe.msgprint(__('Veuillez d\'abord sélectionner le semestre'));
				return { filters: { name: ['=', ''] } };
			}
			
			return {
				filters: {
					article: frm.doc.article,
					annee_budgetaire: frm.doc.annee_budgetaire,
                    budget_global: frm.doc.budget_global,
					type_fiche: 'Provision',
					semestre: frm.doc.semestre,
					status: [ "in", ['Brouillon', 'Signé Doyen', 'Envoyé CF', 'Visé CF']], //'Visé CF'
                    docstatus: ['!=', 2]
				}
			};
		});

        // ✅ FILTRE BON COMMANDE : Article + Non utilisé + Visé CF
        frm.set_query('bon_commande', () => {
            if (!frm.doc.article) {
                frappe.msgprint(__('Veuillez d\'abord sélectionner l\'article'));
                return { filters: { name: ['=', ''] } };
            }
            
            return {
                query: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.get_bon_commande_disponibles',
                filters: {
                    article: frm.doc.article,
                    //fiche_actuelle: frm.doc.name || ''
                    fiche_actuelle: frm.doc.__islocal ? '' : (frm.doc.name || '')
                }
            };
        });

         // ✅ FILTRE CONVENTION : Article + Non utilisée + Visée CF
        frm.set_query('convention', () => {
            if (!frm.doc.article) {
                frappe.msgprint(__('Veuillez d\'abord sélectionner l\'article'));
                return { filters: { name: ['=', ''] } };
            }
            
            return {
                query: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.get_convention_disponibles',
                filters: {
                    article: frm.doc.article,
                    fiche_actuelle: frm.doc.name || ''
                }
            };
        }); 

		// Filtrer les dépenses internes pour la table de régularisation
		if (frm.fields_dict['depenses_regularisees']) {
            frm.fields_dict['depenses_regularisees'].grid.get_field('depense_interne').get_query = function(doc, cdt, cdn) {
                let filters = {
                    article: doc.article,
                    annee_budgetaire: doc.annee_budgetaire,
                    semestre: doc.semestre,
                };
                // Exclure les dépenses déjà présentes dans la table (pour éviter les doublons)
                let already_selected = (doc.depenses_regularisees || [])
                    .map(d => d.depense_interne)
                    .filter(v => v);
                if (already_selected.length) {
                    filters.exclude = already_selected;
                }
                return {
                    query: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.get_depenses_interne_pour_regularisation',
                    filters: filters
                };
            };
        }
            
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

	    // Mettre à jour les champs ordonnateur
        // if (frm.doc.annee_budgetaire) {
        //     frappe.call({
        //         method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.get_ordonnateur_from_annee',
        //         args: { annee_budgetaire: frm.doc.annee_budgetaire },
        //         callback(r) {
        //             if (!r.exc && r.message) {
        //                 frm.set_value('code_ordonnateur', r.message.code_ordonnateur);
        //                 frm.set_value('intitule_ordonnateur', r.message.intitule_ordonnateur);
        //             } else {
        //                 // En cas d'erreur, on vide les champs
        //                 frm.set_value('code_ordonnateur', '');
        //                 frm.set_value('intitule_ordonnateur', '');
        //             }
        //         }
        //     });    
	    // } else {
	    //     // Si l'année est effacée, on vide les champs
	    //     frm.set_value('code_ordonnateur', null);
	    //     frm.set_value('intitule_ordonnateur', null);
	    //     frm.refresh_field('code_ordonnateur');
	    //     frm.refresh_field('intitule_ordonnateur');
	    // } 

        frm.trigger('setup_indicateur_solde');
        frm.trigger('set_filters');
        if (frm.doc.annee_budgetaire) {
            frappe.db.get_value('Annee Budgetaire', frm.doc.annee_budgetaire, 'active', r => {
                if (!r.active) {
                    frappe.show_alert({
                        message: __('Cet exercice budgétaire n\'est pas actif.'),
                        indicator: 'orange'
                    });
                }
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

    
    // ══════════════════════════════════════════
    //  VISIBILITÉ CONDITIONNELLE
    // ══════════════════════════════════════════

    set_champs_visibles(frm) {
        const tf   = frm.doc.type_fiche;
        const ta   = frm.doc.type_article;
        const tr   = frm.doc.is_transfert;
        const sens = frm.doc.sens_transfert;
        const sem  = frm.doc.semestre;
        const teng = frm.doc.type_engagement_apriori;

        // ── Semestre ──
        frm.toggle_display('semestre',
            tf === 'Provision' || tf === 'Régularisation'
        );

        // ── Section Transfert ──
        frm.toggle_display('section_transfert', tr == 1);
        frm.toggle_display('sens_transfert',          tr == 1);
        frm.toggle_display('fiche_transfert',         tr == 1);
        frm.toggle_display('article_contrepartie',    tr == 1);

        // Couleur indicateur transfert selon sens
        if (tr == 1 && sens) {
            const couleur = sens === 'Crédit Reçu' ? 'green' : 'red';
            const libelle = sens === 'Crédit Reçu'
                ? '↑ Crédit Reçu (+)'
                : '↓ Crédit Donné (–)';
            frm.dashboard.add_comment(
                `<b>Transfert de crédit :</b> <span style="color:${couleur}">
                    ${libelle}
                </span>`,
                couleur === 'green' ? 'green' : 'red', true
            );
        }

        // ── Section Dépense A priori normale ──
        const is_dep_apriori = (tf === 'Dépense' && ta === 'A priori' && !tr);
        frm.toggle_display('section_depense_apriori', is_dep_apriori);
        frm.toggle_display('type_engagement_apriori', is_dep_apriori);
        frm.toggle_display('bon_commande',
            is_dep_apriori && teng === 'Bon Commande');
        frm.toggle_display('bc_numero',
            is_dep_apriori && teng === 'Bon Commande');
        frm.toggle_display('bc_date',
            is_dep_apriori && teng === 'Bon Commande');
        frm.toggle_display('bc_montant',
            is_dep_apriori && teng === 'Bon Commande');
        frm.toggle_display('convention',
            is_dep_apriori && teng === 'Convention');
        frm.toggle_display('conv_numero',
            is_dep_apriori && teng === 'Convention');
        frm.toggle_display('conv_date',
            is_dep_apriori && teng === 'Convention');
        frm.toggle_display('conv_montant',
            is_dep_apriori && teng === 'Convention');
        frm.toggle_display('reference_convention',
            is_dep_apriori && teng === 'Convention');
        frm.toggle_display('fournisseur',
            is_dep_apriori && (teng === 'Bon Commande' || teng === 'Convention'));
        frm.toggle_display('raison_sociale',
            is_dep_apriori && (teng === 'Bon Commande' || teng === 'Convention'));
        frm.toggle_display('frais_mission_apriori',
            is_dep_apriori && teng === 'Frais Mission');

        // ── Section Provision ──
        frm.toggle_display('section_provision_s1', tf === 'Provision');
        frm.toggle_display('provision_s1_reference',
            tf === 'Provision' && sem === 'S2');

        // ── Section Régularisation ──
        const is_regu = (tf === 'Régularisation');
        const is_provision = (tf === 'Provision');
        const is_provision_or_regu = is_provision || is_regu;
        
        frm.toggle_display('section_provision_reference', is_regu);
        frm.toggle_display('provision_reference', is_regu);
        
        // Ligne Provision (read-only) - visible pour Provision et Régularisation
        frm.toggle_display('section_provision_ligne', is_provision_or_regu);
        frm.toggle_display('provision_ancien_solde', is_provision_or_regu);
        frm.toggle_display('provision_montant', is_provision_or_regu);
        frm.toggle_display('provision_nouveau_solde', is_provision_or_regu);
        
        // Ligne Crédit (read-only) - visible pour Provision et Régularisation
        frm.toggle_display('section_provision_credit', is_provision_or_regu);
        frm.toggle_display('credit_ancien_solde', is_provision_or_regu);
        frm.toggle_display('credit_montant', is_provision_or_regu);
        frm.toggle_display('credit_nouveau_solde', is_provision_or_regu);
        
        // Table des dépenses - uniquement pour Régularisation
        frm.toggle_display('section_regularisation',    is_regu);
        frm.toggle_display('depenses_regularisees',     is_regu);
        frm.toggle_display('total_regularisation',      is_regu);
        frm.toggle_display('provision_reference',       is_regu);

        // ── Situation paiement ──
        frm.toggle_display('section_suivi',
            !!(tf === 'Dépense' && ta === 'A priori'
               && !tr && frm.doc.situation_paiement)
        );
    },

    // ══════════════════════════════════════════
    //  CHAMPS READONLY
    // ══════════════════════════════════════════

    set_champs_readonly(frm) {
        const always_ro = [
            'code_ordonnateur', 'intitule_ordonnateur',
            'type_article', 'code_article', 'code_partition',
            'intitule_partition', 'code_chapitre',
            'intitule_chapitre', 'intitule_article',
            'ancien_solde', 'nouveau_solde', 'numero_fiche',
            'provision_ancien_solde', 'provision_montant', 'provision_nouveau_solde',
            'credit_ancien_solde', 'credit_montant', 'credit_nouveau_solde',
            'total_regularisation', 
            'situation_paiement',
            // Champs auto-remplis depuis Fiche Transfert
            'article_contrepartie', 'montant_operation',
        ];

        // montant_operation = readonly si transfert (fetch depuis Fiche Transfert)
        // mais éditable si pas transfert
        always_ro.forEach(f => frm.set_df_property(f, 'read_only', 1));

        if (!frm.doc.is_transfert) {
            frm.set_df_property('montant_operation', 'read_only', 0);
        }

        if (frm.doc.docstatus === 1) {
            ['article', 'annee_budgetaire', 'type_fiche', 'chapitre',
             'code_partition', 'semestre', 'is_transfert', 'sens_transfert']
                .forEach(f => frm.set_df_property(f, 'read_only', 1));
        }
        // table depenses_regularisees en lecture seule
        if (frm.fields_dict['depenses_regularisees']) {
            frm.fields_dict['depenses_regularisees'].grid.get_field('depense_interne').read_only = 1;
        }
    },

    // ══════════════════════════════════════════
    //  INDICATEUR SOLDE
    // ══════════════════════════════════════════

    setup_indicateur_solde(frm) {
        if (!frm.doc.article || !frm.doc.budget_global) return;
        frappe.call({
            method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.get_solde_article',
            args: {
                article: frm.doc.article,
                budget_global: frm.doc.budget_global,
                code_partition: frm.doc.code_partition || null,
            },
            callback(r) {
                if (r.exc || !r.message) return;
                const { solde, derniere_fiche } = r.message;
                const couleur = solde > 0 ? '#28a745' : '#dc3545';
                frm.dashboard.add_comment(
                    `<b>Solde disponible :</b>
                     <span style="color:${couleur};font-size:1.1em">
                         ${fmt_money(solde)} DA
                     </span>
                     &nbsp;|&nbsp;
                     <b>Dernière fiche :</b>
                     N° ${String(derniere_fiche || 0).padStart(4,'0')}`,
                    'blue', true
                );
            }
        });
    },

    // ══════════════════════════════════════════
    //  BOUTONS D'ACTION
    // ══════════════════════════════════════════

    add_boutons_action(frm) {
        //
        // MAPPAGE DOCSTATUS :
        //   docstatus=0 : Brouillon, Signé Doyen, Rejeté (après Amend avant correction)
        //   docstatus=1 : Envoyé CF, Visé CF
        //   docstatus=2 : Rejeté (cancel), Rejeté Définitif
        //
        if (frm.doc.__islocal) return;
        frm.clear_custom_buttons();
        const st    = frm.doc.status;
        const docst = frm.doc.docstatus;

        // ── docstatus=2 : Rejeté ou Rejeté Définitif ────────────────────
        if (docst === 2) {
            if (st === 'Rejeté Définitif') {
                // Bloquer Amend côté JS (before_amend bloque aussi côté serveur)
                masquer_amend_fiche(frm);
            }
            // Rejeté simple → Amend natif Frappe disponible, pas de bouton custom
            fb_afficher_badge_rejets(frm);
            return;
        }

        // ── docstatus=1 : Envoyé CF ou Visé CF ──────────────────────────
        if (docst === 1 && st === 'Envoyé CF') {
            // La fiche est soumise et en attente du visa CF
            frm.add_custom_button(__('Viser (CF)'), () =>
                fb_dialog_viser_cf(frm), __('Workflow'));
            frm.add_custom_button(__('Rejeter'), () =>
                fb_dialog_rejeter(frm, false), __('Workflow'));
            frm.add_custom_button(__('Rejet Définitif'), () =>
                fb_dialog_rejeter(frm, true), __('Workflow'));
        }
        // Visé CF (st === 'Visé CF') → aucun bouton workflow
        
        // ── docstatus=0 : Brouillon après Amend → Marquer Corrigé ───────
        // Pattern identique au Mandat Paiement
        if (docst === 0 && frm.doc.amended_from) {
            frm.add_custom_button(__('Marquer Corrigé'), () =>
                fb_dialog_marquer_corrige(frm), __('Actions'));
        }
        
        // ── docstatus=0 : Brouillon (nouvelle fiche ou après correction) ─
        if (docst === 0 && st === 'Brouillon') {
            if (!frm.doc.amended_from && frm.doc.type_fiche === 'Régularisation') {
                frm.add_custom_button(__('Ajouter dépenses'), () =>
                    frm.trigger('dialog_ajouter_depenses'), __('Actions'));
            }
            frm.add_custom_button(__('Signer (Doyen)'), () =>
                fb_dialog_signer_doyen(frm), __('Actions'));
        }

            // ── docstatus=0 : Signé Doyen → Envoyer au CF ───────────────────
        if (docst === 0 && st === 'Signé Doyen') {
            frm.add_custom_button(__('Envoyer au CF'), () =>
                fb_dialog_envoyer_cf(frm), __('Actions'));
        }

        // ── Navigation (tous états) ──────────────────────────────────────
        if (frm.doc.situation_paiement) {
            frm.add_custom_button(__('Situation Paiement'), () =>
                frappe.set_route('Form', 'Situation Paiement', frm.doc.situation_paiement));
        }
        if (frm.doc.fiche_transfert) {
            frm.add_custom_button(__('Fiche Transfert'), () =>
                frappe.set_route('Form', 'Fiche Transfert Credit', frm.doc.fiche_transfert));
        }

        fb_afficher_badge_rejets(frm);
        
    },

    // ══════════════════════════════════════════
    //  DIALOGUE AJOUTER DÉPENSES RÉGULARISATION
    // ══════════════════════════════════════════
    dialog_ajouter_depenses(frm) {
        if (!frm.doc.article || !frm.doc.semestre) {
            frappe.msgprint(__('Sélectionnez l\'article et le semestre d\'abord.'));
            return;
        }

        // Récupérer les dépenses déjà dans la table
        let depenses_exclues = (frm.doc.depenses_regularisees || [])
            .map(row => row.depense_interne)
            .filter(v => v);

        frappe.call({
            method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.get_depenses_non_regularisees',
            args: {
                article: frm.doc.article,
                budget_global: frm.doc.budget_global,
                semestre: frm.doc.semestre,
                fiche_actuelle: frm.doc.name || '',
                depenses_exclues: depenses_exclues
            },
            callback(r) {
                if (r.exc || !r.message?.length) {
                    frappe.msgprint(__('Aucune dépense mandatée disponible.'));
                    return;
                }

                const depenses = r.message;
                const options = depenses.map(d => ({
                    label: `N° ${String(d.numero_interne).padStart(4, '0')}  |  ${
                        d.type_depense === 'Fournisseur' ? d.fournisseur : 'Frais Mission'
                    }  |  ${fmt_money(d.montant_total)} DA  |  Mandat : ${d.numero_mandat || '—'}`,
                    value: d.name,
                }));

                const dlg = new frappe.ui.Dialog({
                    title: __('Sélectionner les dépenses à régulariser'),
                    fields: [{
                        fieldtype: 'MultiCheck',
                        fieldname: 'sel',
                        label: __('Dépenses disponibles'),
                        options,
                    }],
                    primary_action_label: __('Ajouter'),
                    primary_action(vals) {
                        const selected = vals.sel || [];
                        if (!selected.length) {
                            frappe.msgprint(__('Aucune dépense sélectionnée.'));
                            return;
                        }
                        Promise.all(selected.map(name =>
                            frappe.call({
                                method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.get_info_depense_interne',
                                args: { depense_interne: name },
                            })
                        )).then(results => {
                            results.forEach(res => {
                                if (!res.exc && res.message) {
                                    res.message.forEach(info => {
                                        frm.add_child('depenses_regularisees', {
                                            depense_interne: info.depense_interne,
                                            facture_numero: info.facture_numero,
                                            facture_date: info.facture_date,
                                            nom_prenom: info.nom_prenom,
                                            grade: info.grade,
                                            mandat_numero: info.mandat_numero,
                                            mandat_date: info.mandat_date,
                                            montant: info.montant,
                                            fournisseur: info.fournisseur,
                                            raison_sociale: info.raison_sociale,
                                        });
                                    });
                                }
                            });
                            frm.refresh_field('depenses_regularisees');
                            frm.trigger('recalcul_total_regularisation');
                            frm.trigger('calculer_lignes_provision_credit');
                            dlg.hide();
                        });
                    }
                });
                dlg.show();
            }
        });
    },


    // ══════════════════════════════════════════
    //  RECALCUL TOTAL RÉGULARISATION
    // ══════════════════════════════════════════

    recalcul_total_regularisation(frm) {
        const total = (frm.doc.depenses_regularisees || [])
            .reduce((s, r) => s + flt(r.montant), 0);
        frm.set_value('total_regularisation', total);
        frm.set_value('montant_operation', total);
    },

    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : TYPE DE FICHE
    // ══════════════════════════════════════════

    type_fiche(frm) {
        frm.trigger('set_champs_visibles');
        frm.trigger('set_champs_readonly');
        frm.trigger('auto_remplir_montant');
        frm.trigger('charger_ancien_solde');
        frm.trigger('add_boutons_action');
        frm.trigger('bind_ajouter_depenses_button');
    },

    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : IS_TRANSFERT
    // ══════════════════════════════════════════

    is_transfert(frm) {
        frm.trigger('set_champs_visibles');
        frm.trigger('set_champs_readonly');

        if (!frm.doc.is_transfert) {
            // Effacer les champs de transfert si décoché
            frm.set_value('sens_transfert',         '');
            frm.set_value('fiche_transfert',         null);
            frm.set_value('article_contrepartie',   null);
            return;
        }

        // Vérifier immédiatement si le transfert est possible
        if (frm.doc.article && frm.doc.budget_global) {
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.verifier_transfert_possible',
                args: {
                    article: frm.doc.article,
                    budget_global: frm.doc.budget_global,
                    code_partition: frm.doc.code_partition || null,
                },
                callback(r) {
                    if (r.exc) return;
                    if (!r.message.possible) {
                        frappe.msgprint({
                            title: __('Transfert impossible'),
                            message: __(r.message.motif),
                            indicator: 'red',
                        });
                        frm.set_value('is_transfert', 0);
                        frm.trigger('set_champs_visibles');
                    }
                }
            });
        }
    },

    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : SENS DU TRANSFERT
    // ══════════════════════════════════════════

    sens_transfert(frm) {
        const sens = frm.doc.sens_transfert;

        // Forcer le type_fiche selon le sens
        if (sens === 'Crédit Reçu' && frm.doc.type_fiche !== 'Économie') {
            frm.set_value('type_fiche', 'Économie');
            frappe.show_alert({
                message: __('Type de fiche forcé à "Économie" pour un Crédit Reçu.'),
                indicator: 'blue'
            });
        }
        if (sens === 'Crédit Donné' && frm.doc.type_fiche !== 'Dépense') {
            frm.set_value('type_fiche', 'Dépense');
            frappe.show_alert({
                message: __('Type de fiche forcé à "Dépense" pour un Crédit Donné.'),
                indicator: 'blue'
            });
        }

        frm.trigger('set_champs_visibles');
        // Rafraîchir le montant si la fiche transfert est déjà choisie
        if (frm.doc.fiche_transfert) frm.trigger('fiche_transfert');
    },

    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : FICHE TRANSFERT CREDIT
    // ══════════════════════════════════════════

    fiche_transfert(frm) {
        if (!frm.doc.fiche_transfert) return;

        frappe.db.get_doc('Fiche Transfert Credit', frm.doc.fiche_transfert).then(trans => {

            // // Vérifier statut
            // if (trans.status !== 'Visé CF') {
            //     frappe.msgprint({
            //         title: __('Fiche Transfert non visée'),
            //         message: __('La Fiche Transfert Crédit doit être visée par le CF.'),
            //         indicator: 'red',
            //     });
            //     frm.set_value('fiche_transfert', null);
            //     return;
            // }

            // Pré-remplir le montant (readonly)
            frm.set_value('montant_operation', trans.montant_transfere);
            //chapitre et titre
            //titre =frappe.db.get_value('Budget Chapitre', trans.chapitre, 'titre');
            frm.set_value('chapitre', trans.chapitre);
            //frm.set_value('titre', titre);
            // Pré-remplir l'article contrepartie selon le sens
            const sens = frm.doc.sens_transfert;
            if (sens === 'Crédit Reçu') {
                frm.set_value('article_contrepartie', trans.article_source);
                frm.set_value('article', trans.article_destination);
            } else if (sens === 'Crédit Donné') {
                frm.set_value('article_contrepartie', trans.article_destination);
                frm.set_value('article', trans.article_source);
                frm.set_value
            }

            //charger l'ancien solde par l'evenement article
            //frm.trigger('update_nouveau_solde');

            frappe.show_alert({
                message: __(`Transfert de ${fmt_money(trans.montant_transfere)} DA chargé.`),
                indicator: 'green'
            });
        });
    },

    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : ARTICLE
    // ══════════════════════════════════════════

    article(frm) {
        if (!frm.doc.article) return;

        frappe.db.get_doc('Budget Article', frm.doc.article).then(art => {
            frm.set_value('type_article',     art.type);
            frm.set_value('code_article',         art.code_article);
            frm.set_value('intitule_article', art.intitule_article);
            frm.set_value('chapitre',         art.budget_chapitre);

            if (art.has_partition) {
                frm.set_value('code_partition',           art.code_partition);
                frm.set_value('intitule_partition', art.intitule_partition);
            }

            frm.trigger('setup_indicateur_solde');
            frm.trigger('set_champs_visibles');
            frm.trigger('auto_remplir_montant');
            frm.trigger('charger_ancien_solde');
        });
        // ✅ Charger l'ancien solde dès que l'article est sélectionné
        if (frm.doc.article && frm.doc.budget_global) {
            frm.trigger('charger_ancien_solde');
        }
        if (frm.doc.type_article ==  'A posteriori') {
            frm.trigger('calculer_lignes_provision_credit');
            frm.trigger('set_champs_visibles');
        }
    },

    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : CHAPITRE
    // ══════════════════════════════════════════

    chapitre(frm) {
        if (!frm.doc.chapitre) return;
        // Ajouter filtre article par chapitre
        frm.set_query('article', () => {
            return {
                filters: {
                    budget_chapitre: frm.doc.chapitre
                }
            };
        });
        frappe.db.get_value('Budget Chapitre', frm.doc.chapitre,
            ['code', 'intitule'], r => {
                frm.set_value('code_chapitre',     r.code);
                frm.set_value('intitule_chapitre', r.intitule);
            }
        );
    },

    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : SEMESTRE
    // ══════════════════════════════════════════

    semestre(frm) {
        frm.trigger('set_champs_visibles');
        frm.trigger('auto_remplir_montant');
        frm.trigger('charger_ancien_solde');
        frm.trigger('calculer_lignes_provision_credit');
    },

    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : MONTANT OPERATION
    // ══════════════════════════════════════════
    montant_operation(frm) {
        // ✅ Calculer nouveau_solde en temps réel
        if (!frm.doc.ancien_solde && frm.doc.ancien_solde !== 0) {
            frm.trigger('charger_ancien_solde');
            return;
        }
        
        let nouveau = 0;
        const ancien = flt(frm.doc.ancien_solde);
        const montant = flt(frm.doc.montant_operation);
        
        // Crédit
        if (['Économie', 'Provision'].includes(frm.doc.type_fiche)) {
            nouveau = ancien + montant;
        }
        // Débit
        else if (['Dépense', 'Régularisation'].includes(frm.doc.type_fiche)) {
            nouveau = ancien - montant;
        }
        
        // Transfert
        if (frm.doc.is_transfert) {
            if (frm.doc.sens_transfert === 'Crédit Reçu') {
                nouveau = ancien + montant;
            } else if (frm.doc.sens_transfert === 'Crédit Donné') {
                nouveau = ancien - montant;
            }
        }
        
        frm.set_value('nouveau_solde', nouveau);
        
        // Alerte si négatif
        if (nouveau < 0) {
            frappe.show_alert({
                message: __('⚠️ Solde négatif : {0} DA', [format_currency(nouveau)]),
                indicator: 'red'
            }, 10);
        }
        frm.trigger('calculer_lignes_provision_credit');
    },
    //══════════════════════════════════════════
    //bouton ajouter depenses internes
    //══════════════════════════════════════════
    bind_ajouter_depenses_button(frm) {
        if (frm.fields_dict.btn_ajouter_depenses) {
            $(frm.fields_dict.btn_ajouter_depenses.$input).off('click').on('click', () => {
                frm.trigger('dialog_ajouter_depenses');
            });
        }
    },
    // // ══════════════════════════════════════════
    // //  AUTO-REMPLISSAGE MONTANT
    // // ══════════════════════════════════════════

    auto_remplir_montant(frm) {
        const tf = frm.doc.type_fiche;
        const tr = frm.doc.is_transfert;
        if (!frm.doc.article || !frm.doc.budget_global) return;

        // Économie initiale → montant alloué
        if (tf === 'Économie' && !tr) {
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.get_montant_alloue',
                args: { article: frm.doc.article },
                callback(r) {
                    if (!r.exc) {
                        frm.set_value('montant_operation', r.message);
                        frm.set_value('ancien_solde', 0);
                        frm.trigger('update_nouveau_solde');
                    }
                }
            });
            return;
        }

        // Provision → 50% du total crédit (Économie initiale + transferts reçus ou donnés)
        if (tf === 'Provision') {
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.get_total_credit_article',
                args: {
                    article: frm.doc.article,
                    budget_global: frm.doc.budget_global,
                    code_partition: frm.doc.code_partition || null,
                },
                callback(r) {
                    if (!r.exc && r.message) {
                        frm.set_value('montant_operation', r.message.provision_50);
                        frm.set_value('ancien_solde', 0);
                        frm.trigger('update_nouveau_solde');
                        frappe.show_alert({
                            message: __(`Crédit total : ${fmt_money(r.message.total_credit)} DA → Provision : ${fmt_money(r.message.provision_50)} DA`),
                            indicator: 'blue'
                        });
                    }
                }
            });
        }
    },

    // ══════════════════════════════════════════
    //  CHARGER ANCIEN SOLDE
    // ══════════════════════════════════════════
    charger_ancien_solde(frm) {
        // Ne pas charger pour Économie initiale 
        if (frm.doc.type_fiche === 'Économie' && !frm.doc.is_transfert) {
            frm.set_value('ancien_solde', 0);
            frm.trigger('montant_operation'); //recalculer
            return;
        }
        
        if (frm.doc.type_fiche === 'Provision' && !frm.doc.is_transfert && frm.doc.semestre === 'S1')   {
            frm.set_value('ancien_solde', 0);
            return;
        }
        
        if (!frm.doc.article || !frm.doc.budget_global) {
            return;
        }
        
         // Pour les autres fiches, on a besoin du numéro de la fiche courante
        if (!frm.doc.numero_fiche) {
            // Si c'est une nouvelle fiche, pas encore de numéro, on prend le dernier solde global
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.get_solde_article',
                args: {
                    article: frm.doc.article,
                    budget_global: frm.doc.budget_global,
                    code_partition: frm.doc.code_partition || null
                },
                callback(r) {
                    if (!r.exc && r.message) {
                        frm.set_value('ancien_solde', r.message.solde);
                        frm.trigger('montant_operation');
                    }
                }
            });
        } else {
            // Fiche existante : on prend le solde de la fiche précédente
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.get_ancien_solde_fiche',
                args: {
                    article: frm.doc.article,
                    type_article: frm.doc.article,
                    budget_global: frm.doc.budget_global,
                    numero_fiche: frm.doc.numero_fiche,
                    code_partition: frm.doc.code_partition || null
                },
                callback(r) {
                    if (!r.exc && r.message) {
                        frm.set_value('ancien_solde', r.message.solde);
                        frm.trigger('montant_operation');
                    }
                }
            });
        }
    },

    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : TYPE ENGAGEMENT A PRIORI
    // ══════════════════════════════════════════

    type_engagement_apriori(frm) {
        frm.trigger('set_champs_visibles');
        frm.set_value('bon_commande',         null);
        frm.set_value('convention',           null);
        frm.set_value('frais_mission_apriori', null);
        frm.set_value('fournisseur',           null);
        frm.set_value('raison_sociale',        null);
        frm.set_value('reference_convention',  null);
    },

    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : BON DE COMMANDE
    // ══════════════════════════════════════════

    bon_commande(frm) {
        if (!frm.doc.bon_commande) return;
        frappe.db.get_doc('Bon Commande', frm.doc.bon_commande).then(bc => {
            frm.set_value('bc_numero',        bc.numero_bon_commande);
            frm.set_value('bc_date',          bc.date_bon_commande);
            frm.set_value('bc_montant',       bc.total_ttc);
            frm.set_value('fournisseur',      bc.prestataire);
            frm.set_value('montant_operation', bc.total_ttc);
            if (bc.prestataire) {
                frappe.db.get_value('Fournisseur', bc.prestataire, 'raison_sociale', r =>
                    frm.set_value('raison_sociale', r.raison_sociale)
                );
            }
            frm.trigger('update_nouveau_solde');
        });
    },

    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : CONVENTION
    // ══════════════════════════════════════════

    convention(frm) {
        if (!frm.doc.convention) return;
        frappe.db.get_doc('Convention', frm.doc.convention).then(conv => {
            frm.set_value('conv_numero',          conv.numero_convention);
            frm.set_value('conv_date',            conv.date_convention);
            frm.set_value('conv_montant',         conv.montant_convention);
            frm.set_value('reference_convention', conv.numero_convention);
            frm.set_value('fournisseur',          conv.fournisseur);
            frm.set_value('montant_operation',    conv.montant_convention);
            if (conv.fournisseur) {
                frappe.db.get_value('Fournisseur', conv.fournisseur, 'raison_sociale', r =>
                    frm.set_value('raison_sociale', r.raison_sociale)
                );
            }
           
            frappe.show_alert({
                message: __('Une Situation de Paiement sera créée après visa CF.'),
                indicator: 'blue'
            });
            
            frm.trigger('update_nouveau_solde');
        });
    },

    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : FRAIS MISSION A PRIOIRI
    // ══════════════════════════════════════════

	frais_mission_apriori(frm) {
	    if (!frm.doc.frais_mission_apriori) return;
	    
	    frappe.call({
	        method: 'frappe.client.get',
	        args: {
	            doctype: 'Frais Mission',
	            name: frm.doc.frais_mission_apriori
	        },
	        callback(r) {
	            if (!r.exc && r.message) {
	                const fm = r.message;
	                
	                // Vérifier article
	                if (fm.article !== frm.doc.article) {
	                    frappe.msgprint({
	                        title: __('❌ Incohérence Article'),
	                        indicator: 'red',
	                        message: __(
	                            'Le Frais Mission appartient à l\'article {0}, pas à {1}.'
	                        ).format(fm.article, frm.doc.article)
	                    });
	                    frm.set_value('frais_mission_apriori', '');
	                    return;
	                }
	                
	                // Définir le montant
	                frm.set_value('montant_operation', fm.montant_total);
	                
	                // Info sur types de compte
	                const types = new Set(
	                    (fm.table_beneficiaires || [])
	                        .map(b => b.type_compte)
	                        .filter(t => t)
	                );
	                
	                if (types.size > 1) {
	                    const nb_banque = fm.table_beneficiaires.filter(b => b.type_compte === 'Banque').length;
	                    const nb_ccp = fm.table_beneficiaires.filter(b => b.type_compte === 'CCP').length;
	                    
	                    frappe.msgprint({
	                        title: __('ℹ️ Types Compte Mixtes'),
	                        indicator: 'blue',
	                        message: __(
	                            'Ce Frais Mission contient :<br>' +
	                            '- {0} personne(s) avec compte <b>Banque</b><br>' +
	                            '- {1} personne(s) avec compte <b>CCP</b><br><br>' +
	                            '💡 <i>Au moment du mandatement, vous devrez créer 2 mandats séparés.</i>'
	                        ).format(nb_banque, nb_ccp)
	                    });
	                }
	                
	                frappe.show_alert({
	                    message: __('Frais Mission chargé : {0} DA', [format_currency(fm.montant_total)]),
	                    indicator: 'green'
	                });
	            }
	        }
	    });
	},
    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : PROVISION REFERENCE
    // ══════════════════════════════════════════

    provision_reference(frm) {
        if (!frm.doc.provision_reference) return;
        frappe.db.get_doc('Fiche Budgetaire', frm.doc.provision_reference).then(prov => {
            frm.set_value('provision_ancien_solde',  prov.ancien_solde);
            frm.set_value('provision_montant',       prov.montant_operation);
            frm.set_value('provision_nouveau_solde', prov.nouveau_solde);
            frm.set_value('semestre', prov.semestre);

            if (prov.status !== 'Visé CF') {
                frappe.show_alert({
                    message: __('Cette Provision n\'est pas encore visée par le CF !'),
                    indicator: 'orange'
                });
            }
        });
        frm.trigger('calculer_lignes_provision_credit');
    },

    // ══════════════════════════════════════════
    //  ÉVÉNEMENT : MONTANT OPÉRATION
    // ══════════════════════════════════════════

    montant_operation(frm) {
        frm.trigger('update_nouveau_solde');
    },

    update_nouveau_solde(frm) {
        const tf    = frm.doc.type_fiche;
        const tr    = frm.doc.is_transfert;
        const sens  = frm.doc.sens_transfert;
        const ancien = flt(frm.doc.ancien_solde);
        const montant = flt(frm.doc.montant_operation);
        const semestre =flt(frm.doc.semestre)

        let nouveau;
        if ((tf === 'Économie' && !tr) || (tf === 'Provision' && semestre === 'S1' ) ) {
            nouveau = montant; // ancien_solde = 0
        } else if (tf === 'Économie' && tr && sens === 'Crédit Reçu') {
            nouveau = ancien + montant;
        } else if (tf === 'Dépense' || tf === 'Régularisation') {
            nouveau = ancien - montant;
        } else {
            nouveau = ancien + montant;
        }

        // // Transfert (peut surcharger selon le sens)
        // if (frm.doc.is_transfert) {
        //     if (frm.doc.sens_transfert === 'Crédit Reçu') {
        //         nouveau = ancien + montant;
        //     } else if (frm.doc.sens_transfert === 'Crédit Donné') {
        //         nouveau = ancien - montant;
        //     }
        // }

        frm.set_value('nouveau_solde', nouveau);

        if (nouveau < 0) {
            frappe.show_alert({
                message: __('⚠ Solde négatif ! Vérifiez le montant.'),
                indicator: 'red'
            });
        }
    },

    // ══════════════════════════════════════════
    //  FILTRES (NOUVEAU)
    // ══════════════════════════════════════════
    
    set_filters(frm) {
        // Filtrer chapitre par titre et année budgétaire
        if (frm.doc.budget_global) {
            frm.set_query('chapitre', () => {
                return {
                    filters: {
                        budget_global: frm.doc.budget_global
                    }
                };
            });
        }
    },    
    // ══════════════════════════════════════════
    //  CALCULER LIGNE PROVISION CREDIT
    // ══════════════════════════════════════════

    calculer_lignes_provision_credit(frm) {
        if (!frm.doc.article || !frm.doc.budget_global) return;
        if (!['Provision', 'Régularisation'].includes(frm.doc.type_fiche)) return;

        let args = {
            name: frm.doc.name, // pour exclure la fiche courante
            article: frm.doc.article,
            budget_global: frm.doc.budget_global,
            type_fiche: frm.doc.type_fiche,
            semestre: frm.doc.semestre,
            provision_reference: frm.doc.provision_reference,
            montant_operation: frm.doc.montant_operation,
        };

        // Pour la régularisation, le montant est la somme des dépenses de la table
        if (frm.doc.type_fiche === 'Régularisation') {
            let total = 0;
            (frm.doc.depenses_regularisees || []).forEach(row => {
                total += flt(row.montant);
            });
            args.montant_operation = total;
        }

        frappe.call({
            method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.calculer_lignes_provision_credit',
            args: { args: args },
            callback(r) {
                if (!r.exc && r.message) {
                    frm.set_value('provision_ancien_solde', r.message.provision_ancien_solde);
                    frm.set_value('provision_montant', r.message.provision_montant);
                    frm.set_value('provision_nouveau_solde', r.message.provision_nouveau_solde);
                    frm.set_value('credit_ancien_solde', r.message.credit_ancien_solde);
                    frm.set_value('credit_montant', r.message.credit_montant);
                    frm.set_value('credit_nouveau_solde', r.message.credit_nouveau_solde);
                }
            }
        });
    },

    // ══════════════════════════════════════════
    //  COLORISATION STATUT
    // ══════════════════════════════════════════

    coloriser_statut(frm) {
        const map = {
            'Brouillon'   : 'gray',
            'Signé Doyen' : 'orange',
            'Envoyé CF'   : 'blue',
            'Visé CF'     : 'green',
            'Rejeté'            : 'red',
            'Rejeté Définitif'  : 'red',
            'Archivé'     : 'darkgrey',
        };
        frm.page.set_indicator(__(frm.doc.status), map[frm.doc.status] || 'gray');
    },

});

// ══════════════════════════════════════════════
//  CHILD TABLE : Dépenses Régularisées
// ══════════════════════════════════════════════

frappe.ui.form.on('Depense Regularisee Element', {

    depenses_regularisees_remove(frm) {
        frm.trigger('recalcul_total_regularisation');
        frm.trigger('calculer_lignes_provision_credit');
    },
});

// ══════════════════════════════════════════════
//  UTILITAIRES
// ══════════════════════════════════════════════

function fmt_money(val) {
    return new Intl.NumberFormat('fr-DZ', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(parseFloat(val) || 0);
}

function flt(val) { return parseFloat(val) || 0; }

// ══════════════════════════════════════════════════════════
//  FONCTIONS GLOBALES — Workflow Fiche Budgetaire
// ══════════════════════════════════════════════════════════

function fb_afficher_badge_rejets(frm) {
    const nb = frm.doc.nb_rejets || 0;
    if (nb > 0 && !frm._fb_rejet_badge) {
        const def = frm.doc.status === 'Rejeté Définitif';
        const msg = nb === 1
            ? __('Cette fiche a subi 1 rejet CF.')
            : __('Cette fiche a subi {0} rejets CF.', [nb]);
        frm.dashboard.add_comment(msg, def ? 'red' : 'orange', true);
        frm._fb_rejet_badge = true;
    }
}

function masquer_amend_fiche(frm) {
    /**
     * Cache le bouton Amend natif de Frappe (Rejeté Définitif).
     * Utilise un MutationObserver car Frappe peut re-rendre le bouton après le refresh.
     * Le verrou Python (before_amend) garantit le blocage côté serveur également.
     * Pattern identique à masquer_bouton_amend() dans mandat_paiement.js
     */
    const do_hide = () => {
        if (frm.page.btn_secondary) frm.page.btn_secondary.hide();
        frm.page.wrapper.find([
            '.btn-amend',
            '[data-label="Amend"]',
            'button:contains("Amend")',
            '.page-actions button.btn-default',
        ].join(', ')).each(function() {
            if ($(this).text().trim() === 'Amend') $(this).hide();
        });
    };

    do_hide();

    if (frm._fb_amend_obs) frm._fb_amend_obs.disconnect();
    frm._fb_amend_obs = new MutationObserver(() => do_hide());
    frm._fb_amend_obs.observe(
        frm.page.wrapper.find('.page-actions')[0] || frm.page.wrapper[0],
        { childList: true, subtree: true }
    );
    setTimeout(() => {
        if (frm._fb_amend_obs) { frm._fb_amend_obs.disconnect(); frm._fb_amend_obs = null; }
    }, 5000);

    frm.set_read_only(true);
}

function fb_dialog_signer_doyen(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Signature du Doyen'),
        fields: [{ fieldtype: 'Date', fieldname: 'date_signature',
                label: __('Date de signature'), reqd: 1,
                   default: frappe.datetime.get_today() }],
        primary_action_label: __('Signer'),
        primary_action(v) {
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.signer_doyen',
                args: { fiche_name: frm.doc.name, date_signature: v.date_signature },
                callback(r) { if (!r.exc) { d.hide(); frm.reload_doc();
                    frappe.show_alert({ message: __('Fiche signée par le Doyen.'), indicator: 'blue' }); } }
            });
        }
    });
    d.show();
}

function fb_dialog_envoyer_cf(frm) {
    // Envoyer au CF = Submit (docstatus 0→1)
    frappe.confirm(__("Envoyer la fiche au CF et la soumettre ?"), () => {
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.envoyer_cf',
                args: { fiche_name: frm.doc.name },
            callback(r) {
                if (!r.exc) {
                    frm.reload_doc();
                    frappe.show_alert({ message: __('Fiche envoyée au CF (soumise, docstatus=1).'), indicator: 'green' });
                }
            }
            });
    });
}

function fb_dialog_viser_cf(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Enregistrement Visa CF'),
        fields: [
            { fieldtype: 'Data', fieldname: 'visa_cf_numero', label: __('N° Visa CF'), reqd: 1 },
            { fieldtype: 'Date', fieldname: 'date_visa_cf',   label: __('Date Visa CF'), reqd: 1,
              default: frappe.datetime.get_today() }
        ],
        primary_action_label: __('Valider le Visa CF'),
        primary_action(v) {
            // Visa CF : la fiche est déjà soumise (docstatus=1),
            // on met à jour status='Visé CF' via allow_on_submit
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.viser_cf',
                args: { fiche_name: frm.doc.name, visa_cf_numero: v.visa_cf_numero, date_visa_cf: v.date_visa_cf },
                callback(r) {
                    if (!r.exc) {
                        d.hide();
                        frm.reload_doc();
                        frappe.show_alert({ message: __('Visa CF enregistré.'), indicator: 'green' });
                    }
                }
            });
        }
    });
    d.show();
}

function fb_dialog_rejeter(frm, force_definitif) {
    const d = new frappe.ui.Dialog({
        title: force_definitif ? __('Rejet Définitif CF') : __('Rejet CF'),
        fields: [
            { fieldname: 'html_avert', fieldtype: 'HTML',
                options: force_definitif
                ? '<div style="color:var(--red-600);font-weight:500;padding:8px;border:1px solid var(--red-300);border-radius:4px;margin-bottom:8px;">⚠️ Rejet définitif : docstatus=2, Amend bloqué.</div>'
                : '' },
            { fieldtype: 'Date', fieldname: 'date_rejet', label: __('Date du Rejet'),
              reqd: 1, default: frappe.datetime.get_today() },
            { fieldtype: 'Column Break' },
            { fieldtype: 'Small Text', fieldname: 'motif', label: __('Motif du Rejet CF'), reqd: 1 },
            ...(!force_definitif ? [{ fieldtype: 'Check', fieldname: 'definitif',
                label: __('Rejet Définitif') }] : []),
        ],
        primary_action_label: force_definitif ? __('Confirmer Rejet Définitif') : __('Rejeter'),
        primary_action(v) {
            const est_def = force_definitif || v.definitif;
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.rejeter_fiche',
                args: { fiche_name: frm.doc.name, motif: v.motif.trim(),
                        date_rejet: v.date_rejet, definitif: est_def ? 1 : 0 },
                callback(r) { if (!r.exc) { d.hide(); frm.reload_doc();
                        frappe.show_alert({
                        message: r.message && r.message.message ? r.message.message : __('Rejet enregistré.'),
                        indicator: est_def ? 'red' : 'orange' }); } }
            });
        }
    });
    d.show();
}

function fb_dialog_marquer_corrige(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Enregistrer les Corrections'),
        fields: [
            { fieldtype: 'Date', fieldname: 'date_correction', label: __('Date de Correction'),
              reqd: 1, default: frappe.datetime.get_today() },
            { fieldtype: 'Column Break' },
            { fieldtype: 'Small Text', fieldname: 'corrections',
              label: __('Corrections apportées'), reqd: 1 }
        ],
        primary_action_label: __('Confirmer'),
        primary_action(v) {
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire.marquer_corrige_fiche',
                args: { fiche_name: frm.doc.name, date_correction: v.date_correction,
                        corrections: v.corrections.trim() },
                callback(r) {
                    if (!r.exc) {
                        d.hide();
                        frm.reload_doc();
                        frappe.show_alert({
                            message: __('Corrections enregistrées. La fiche est maintenant en Brouillon.'),
                            indicator: 'blue'
                        });
                    }
                }
            });
        }
    });
    d.show();
}
