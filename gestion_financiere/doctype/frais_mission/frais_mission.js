frappe.ui.form.on('Frais Mission', {
    
    refresh(frm) {
        frm.trigger('set_queries');
        frm.trigger('recalcul_total');
        frm.trigger('setup_charger_button');
    },
    
    onload(frm) {
        frm.trigger('set_queries');
    },
    
    // ══════════════════════════════════════════
    //  FILTRES
    // ══════════════════════════════════════════
    
    set_queries(frm) {
        // Filtrer Année Budgétaire par Faculté
        // frm.set_query('annee_budgetaire', () => {
        //     if (!frm.doc.faculte) {
        //         frappe.msgprint(__('Veuillez d\'abord sélectionner la Faculté'));
        //         return { filters: { name: ['=', ''] } };
        //     }
        //     return {
        //         filters: {
        //             faculte: frm.doc.faculte
        //         }
        //     };
        // });
        
        // Filtrer Article par Année Budgétaire
        frm.set_query('article', () => {
            if (!frm.doc.annee_budgetaire) {
                frappe.msgprint(__('Veuillez d\'abord sélectionner l\'Année Budgétaire'));
                return { filters: { name: ['=', ''] } };
            }
            return {
                filters: {
                    annee_budgetaire: frm.doc.annee_budgetaire,
                    cost_center: frm.doc.faculte
                }
            };
        });
        
        // ✅ FILTRE CRITIQUE : Personnes dans la child table
        if (frm.fields_dict['table_beneficiaires']) {
            frm.fields_dict['table_beneficiaires'].grid.get_field('personne').get_query = function(doc, cdt, cdn) {
                const row = locals[cdt][cdn];
                
                if (!doc.faculte) {
                    frappe.msgprint(__('Veuillez d\'abord sélectionner la Faculté'));
                    return { filters: { name: ['=', ''] } };
                }
                
                if (!row.type_personne_doctype) {
                    frappe.msgprint(__('Type de personne non défini'));
                    return { filters: { name: ['=', ''] } };
                }
                
                console.log('🔍 Filtre appliqué:', {
                    doctype: row.type_personne_doctype,
                    faculte: doc.faculte
                });
                
                return {
                    filters: {
                        faculte: doc.faculte
                    }
                };
            };
        }
    },
    
    // ══════════════════════════════════════════
    //  CHANGEMENTS EN CASCADE
    // ══════════════════════════════════════════
    
    faculte(frm) {
        frm.trigger('set_queries');
        if (frm.doc.annee_budgetaire || frm.doc.article) {
            frm.set_value('annee_budgetaire', '');
            frm.set_value('article', '');
            frappe.show_alert({
                message: __('Année et Article effacés'),
                indicator: 'orange'
            });
        }
    },
    
    annee_budgetaire(frm) {
        frm.trigger('set_queries');
        if (frm.doc.article) {
            frm.set_value('article', '');
            frappe.show_alert({
                message: __('Article effacé'),
                indicator: 'orange'
            });
        }
    },
    
    type_missionnaire(frm) {
        if (frm.doc.table_beneficiaires && frm.doc.table_beneficiaires.length > 0) {
            frappe.confirm(
                __('Changer le type de missionnaire va vider la liste. Continuer ?'),
                () => {
                    frm.clear_table('table_beneficiaires');
                    frm.refresh_field('table_beneficiaires');
                }
            );
        }
        // Rafraîchir le grid pour appliquer le nouveau filtre
        frm.trigger('set_queries');
    },
    
    // ══════════════════════════════════════════
    //  BOUTON CHARGER
    // ══════════════════════════════════════════
    
    setup_charger_button(frm) {
        if (!frm.doc.__islocal && frm.doc.type_missionnaire && frm.doc.faculte) {
            frm.fields_dict.charger_beneficiaires.$input.on('click', () => {
                frm.trigger('dialog_charger_beneficiaires');
            });
        }
    },
    
    dialog_charger_beneficiaires(frm) {
        if (!frm.doc.faculte) {
            frappe.msgprint(__('Veuillez d\'abord sélectionner la Faculté'));
            return;
        }
        
        if (!frm.doc.type_missionnaire) {
            frappe.msgprint(__('Veuillez d\'abord sélectionner le Type Missionnaire'));
            return;
        }
        
        frappe.call({
            method: 'gestion_financiere.gestion_financiere.doctype.frais_mission.frais_mission.get_doctype_from_type_missionnaire',
            args: { type_missionnaire: frm.doc.type_missionnaire },
            callback(r) {
                if (!r.exc && r.message) {
                    const doctype = r.message;
                    
                    const d = new frappe.ui.Dialog({
                        title: __('Charger {0} - {1}', [frm.doc.type_missionnaire, frm.doc.faculte]),
                        fields: [
                            {
                                fieldtype: 'HTML',
                                options: `<div class="alert alert-info">
                                    <b>🔍 Filtres :</b><br>
                                    - Type : <b>${frm.doc.type_missionnaire}</b><br>
                                    - Faculté : <b>${frm.doc.faculte}</b>
                                </div>`
                            },
                            {
                                fieldtype: 'Link',
                                fieldname: 'personne_unique',
                                label: __('Sélectionner une personne'),
                                options: doctype,
                                get_query: function() {
                                    return {
                                        filters: {
                                            faculte: frm.doc.faculte
                                        }
                                    };
                                }
                            },
                            {
                                fieldtype: 'Button',
                                fieldname: 'ajouter',
                                label: __('➕ Ajouter'),
                                click: function() {
                                    const personne = d.get_value('personne_unique');
                                    if (!personne) {
                                        frappe.msgprint(__('Sélectionnez une personne'));
                                        return;
                                    }
                                    
                                    frappe.call({
                                        method: 'frappe.client.get',
                                        args: {
                                            doctype: doctype,
                                            name: personne
                                        },
                                        callback(r) {
                                            if (!r.exc && r.message) {
                                                frm.trigger('ajouter_beneficiaire', [r.message, doctype]);
                                                d.set_value('personne_unique', '');
                                                frappe.show_alert({
                                                    message: __('✅ Ajouté'),
                                                    indicator: 'green'
                                                });
                                            }
                                        }
                                    });
                                }
                            },
                            {
                                fieldtype: 'Section Break'
                            },
                            {
                                fieldtype: 'Button',
                                fieldname: 'charger_tout',
                                label: __('📥 Charger Tous'),
                                click: function() {
                                    frappe.call({
                                        method: 'frappe.client.get_list',
                                        args: {
                                            doctype: doctype,
                                            filters: {
                                                faculte: frm.doc.faculte
                                            },
                                            fields: ['name'],
                                            limit_page_length: 500
                                        },
                                        callback(r) {
                                            if (!r.exc && r.message && r.message.length > 0) {
                                                frappe.confirm(
                                                    __('Charger {0} personne(s) ?', [r.message.length]),
                                                    () => {
                                                        r.message.forEach(p => {
                                                            frappe.call({
                                                                method: 'frappe.client.get',
                                                                args: {
                                                                    doctype: doctype,
                                                                    name: p.name
                                                                },
                                                                callback(r2) {
                                                                    if (!r2.exc && r2.message) {
                                                                        frm.trigger('ajouter_beneficiaire', [r2.message, doctype]);
                                                                    }
                                                                }
                                                            });
                                                        });
                                                        
                                                        d.hide();
                                                        frappe.show_alert({
                                                            message: __('⏳ Chargement...'),
                                                            indicator: 'blue'
                                                        });
                                                    }
                                                );
                                            } else {
                                                frappe.msgprint(__('Aucune personne trouvée pour cette faculté'));
                                            }
                                        }
                                    });
                                }
                            }
                        ],
                        primary_action_label: __('Fermer'),
                        primary_action() {
                            d.hide();
                        }
                    });
                    
                    d.show();
                }
            }
        });
    },
    
    ajouter_beneficiaire(frm, data) {
        const [pers, doctype] = data;
        
        const existe = (frm.doc.table_beneficiaires || []).find(
            b => b.personne === pers.name
        );
        
        if (existe) {
            return;
        }
        
        const row = frm.add_child('table_beneficiaires');
        row.type_personne_doctype = doctype;
        row.personne = pers.name;
        row.nom_prenom = pers.nom_prenom || pers.name;
        row.grade = pers.grade || '';
        row.type_compte = pers.type_compte || '';
        row.compte = pers.numero_compte || '';
        row.montant_mission = 0;
        
        frm.refresh_field('table_beneficiaires');
    },
    
    recalcul_total(frm) {
        if (!frm.doc.table_beneficiaires) return;
        
        const total = frm.doc.table_beneficiaires.reduce((sum, b) => {
            return sum + flt(b.montant_mission);
        }, 0);
        
        frm.set_value('montant_total', total);
    }
});

// ══════════════════════════════════════════════
//  CHILD TABLE
// ══════════════════════════════════════════════

frappe.ui.form.on('Etat Frais Mission Elements', {
    
    table_beneficiaires_add(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        
        if (frm.doc.type_missionnaire && !row.type_personne_doctype) {
            frappe.call({
                method: 'gestion_financiere.gestion_financiere.doctype.frais_mission.frais_mission.get_doctype_from_type_missionnaire',
                args: { type_missionnaire: frm.doc.type_missionnaire },
                callback(r) {
                    if (!r.exc && r.message) {
                        frappe.model.set_value(cdt, cdn, 'type_personne_doctype', r.message);
                    }
                }
            });
        }
    },
    
    personne(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.personne || !row.type_personne_doctype) return;
        
        // ✅ VÉRIFIER LES DOUBLONS
        const doublons = (frm.doc.table_beneficiaires || []).filter(b => 
            b.personne === row.personne && b.name !== row.name
        );
        
        if (doublons.length > 0) {
            frappe.msgprint({
                title: __('❌ Doublon Détecté'),
                message: __(
                    '<b>{0}</b> est déjà présent(e) dans la liste.<br><br>' +
                    'Chaque personne ne peut être ajoutée qu\'une seule fois.'
                ).format(row.personne),
                indicator: 'red'
            });
            
            // Effacer la sélection
            frappe.model.set_value(cdt, cdn, 'personne', '');
            
            // Optionnel : Supprimer la ligne vide
            setTimeout(() => {
                frm.get_field('table_beneficiaires').grid.grid_rows_by_docname[cdn].remove();
            }, 100);
            
            return;
        }
        
        // Charger les infos de la personne
        frappe.call({
            method: 'frappe.client.get',
            args: {
                doctype: row.type_personne_doctype,
                name: row.personne
            },
            callback(r) {
                if (!r.exc && r.message) {
                    const pers = r.message;
                    
                    // Vérifier faculté
                    if (pers.faculte && frm.doc.faculte && pers.faculte !== frm.doc.faculte) {
                        frappe.msgprint({
                            title: __('❌ Faculté Différente'),
                            message: __(
                                '{0} appartient à <b>{1}</b>, pas à <b>{2}</b>'
                            ).format(pers.nom_complet || pers.name, pers.faculte, frm.doc.faculte),
                            indicator: 'red'
                        });
                        frappe.model.set_value(cdt, cdn, 'personne', '');
                        return;
                    }
                    
                    // Remplir les champs
                    frappe.model.set_value(cdt, cdn, 'nom_prenom', pers.nom_prenom || pers.name);
                    frappe.model.set_value(cdt, cdn, 'grade', pers.grade || '');
                    frappe.model.set_value(cdt, cdn, 'type_compte', pers.type_compte || '');
                    frappe.model.set_value(cdt, cdn, 'compte', pers.numero_compte || '');
                    
                    frappe.show_alert({
                        message: __('✅ {0} ajouté(e)', [pers.nom_prenom || pers.name]),
                        indicator: 'green'
                    });
                }
            }
        });
    },
    
    montant_mission(frm) {
        frm.trigger('recalcul_total');
    },
    
    table_beneficiaires_remove(frm) {
        frm.trigger('recalcul_total');
    },
    
    type_compte(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.type_compte) return;
        
        const types_compte = new Set();
        (frm.doc.table_beneficiaires || []).forEach(b => {
            if (b.type_compte) types_compte.add(b.type_compte);
        });
        
        if (types_compte.size > 1 && frm.doc.article) {
            frappe.db.get_value('Budget Article', frm.doc.article, 'type', r => {
                if (r.type === 'A posteriori') {
                    frappe.msgprint({
                        title: __('⚠️ Article A Posteriori'),
                        message: __('Tous doivent avoir le même type de compte'),
                        indicator: 'red'
                    });
                }
            });
        }
    }
});

function flt(val) {
    return parseFloat(val) || 0;
}
