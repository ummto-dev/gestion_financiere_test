import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate
from num2words import num2words


class MandatPaiement(Document):
    def validate(self):
        """Validations lors de la sauvegarde."""
        self._validate_date_mandat()
        self._validate_numero_mandat()
        self._set_readonly_fields()
        self._validate_source()
        self._validate_creancier()
        self._calculate_montant_total()
        self._convert_montant_lettres()
        self._bloquer_si_definitif()
        # if self.status_admission == "Payé" and not self.is_new():
        #     # Vérifier si des champs ont changé (sauf le statut lui-même)
        #     # Pour simplifier, on interdit toute modification
        #     frappe.throw(_("Un mandat déjà payé ne peut pas être modifié."))
        if self.type_source == "Fiche Depense" and self.situation_paiement:
            #self._add_ligne_situation_paiement()
            self._mettre_a_jour_situation_paiement()

    def on_update(self):
        """Après sauvegarde - mettre à jour la source."""
        self._update_source_reference()

    def before_submit(self):
        """
        Submit = le mandat est envoyé au comptable.
        Valider que status_admission est cohérent.
        """
        if self.status_admission not in ("En Attente", "Envoyé Comptable"):
            frappe.throw(_(
                "Le mandat doit être au statut 'En Attente' ou 'Envoyé Comptable' "
                "avant soumission. Statut actuel : {0}"
            ).format(self.status_admission))

        # Passer automatiquement en Envoyé Comptable si ce n'est pas encore fait
        if self.status_admission == "En Attente":
            self.status_admission = "Envoyé Comptable"
            if self.type_source == "Depense Interne" and self.depense_interne:
                date_envoi = getattr(self, '_date_envoi_comptable', nowdate())
                frappe.db.set_value("Depense Interne", self.depense_interne, {
                    "status": "Envoyé Comptable",
                    "date_envoi_comptable": date_envoi,
                })

    def on_submit(self):
        """docstatus passe à 1 — mandat soumis au comptable."""
        pass

    def before_cancel(self):
        """
        Cancel Frappe est utilisé dans deux cas :
          1.  Rejet simple    → status_admission = "Rejeté"         → Amend possible
          2. Rejet définitif → status_admission = "Annulé Définitif" → Amend BLOQUÉ

        Si status_admission == "Admis" ou "Payé" → on bloque le cancel.
        """
        if self.status_admission in ("Admis", "Payé"):
            frappe.throw(_(
                "Un mandat admis ou payé ne peut pas être annulé."
            ))
    def on_trash(self):
        """Suppression du draft — délier la dépense et les factures."""
        if self.type_source == "Depense Interne" and self.depense_interne:
            dep_status = frappe.db.get_value(
                "Depense Interne", self.depense_interne, "status"
            ) or ""
            if dep_status not in ("Rejeté Définitif", "Régularisé"):
                frappe.db.set_value("Depense Interne", self.depense_interne, {
                    "mandat_paiement": None, "numero_mandat": 0,
                    "date_mandat": None, "status": "Validé",
                })
        self._liberer_factures()
        if self.type_source == "Fiche Depense" and self.situation_paiement:
            self._retirer_ligne_situation()
            
    def on_cancel(self):
        """
        Appelé après le cancel Frappe (docstatus 1→2).
        - Rejet simple    : dépense remise en "Mandaté" (prête pour correction via Amend)
        - Rejet définitif : dépense en "Rejeté Définitif", factures libérées
        """
        if self.status_admission == "Annulé Définitif":
            self._traiter_annulation_definitive()
        else:
            # Rejet simple ou cancel utilisateur : restaurer la dépense
            self._restaurer_depense_pour_correction()
    def before_amend(self):
        """
        Frappe appelle ce hook avant de créer le document amendé.
        Si le mandat est "Annulé Définitif" → bloquer l'Amend côté serveur.
        C'est le verrou Python infaillible, indépendant du JS.
        """
        if self.status_admission == "Annulé Définitif":
            frappe.throw(_(
                "Ce mandat a été annulé définitivement. "
                "Il ne peut pas être amendé ou repris."
            ))

    def on_amend(self):
        """
        Appelé quand l'utilisateur clique Amend (crée un nouveau draft).
        Réinitialiser status_admission pour le nouveau mandat.
        """
        self.status_admission = "En Attente"
        self.nb_rejets = 0
        # Vider l'historique des rejets (nouveau mandat propre)
        self.historique_rejets = []
        # La dépense interne sera re-liée via validate/on_update

    # ══════════════════════════════════════════
    #  BLOQUER MODIFICATION SI DÉFINITIF OU PAYÉ
    # ══════════════════════════════════════════

    def _bloquer_si_definitif(self):
        if self.is_new():
            return
        statut_actuel = frappe.db.get_value(
            "Mandat Paiement", self.name, "status_admission"
        )
        if statut_actuel in ("Payé", "Annulé Définitif"):
            frappe.throw(_(
                "Un mandat au statut « {0} » ne peut plus être modifié."
            ).format(statut_actuel))
    # ══════════════════════════════════════════
    #  TRAITEMENT ON_CANCEL
    # ══════════════════════════════════════════

    def _traiter_annulation_definitive(self):
        """
        Rejet définitif : la dépense passe en 'Réjeté Définitif'.
        Depense Interne est NON-submittable → docstatus reste 0
        (mettre docstatus=2 activerait le bouton Amend qui planterait).
        """
        if self.type_source == "Depense Interne" and self.depense_interne:
            frappe.db.set_value("Depense Interne", self.depense_interne, {
                "status": "Rejeté Définitif",
                "mandat_paiement": None,
                "numero_mandat": 0,
                "date_mandat": None,
                # docstatus intentionnellement NON modifié (reste 0)
            })
        self._liberer_factures()

    def _restaurer_depense_pour_correction(self):
        """
        Rejet simple ou cancel : la dépense repasse en 'Mandaté'
        pour que le service budget puisse corriger via Amend.
        """
        if self.type_source == "Depense Interne" and self.depense_interne:
            dep_status = frappe.db.get_value(
                "Depense Interne", self.depense_interne, "status"
            ) or ""
            if dep_status not in ("Rejeté Définitif", "Régularisé"):
                frappe.db.set_value("Depense Interne", self.depense_interne, {
                    "mandat_paiement": None,
                    "numero_mandat": 0,
                    "date_mandat": None,
                    "status": "Validé",
                })
                frappe.msgprint(_(
                    "Dépense interne {0} remise à l'état 'Validé'."
                ).format(self.depense_interne))
        self._liberer_factures()
        if self.type_source == "Fiche Depense" and self.situation_paiement:
            self._retirer_ligne_situation()

    def _liberer_factures(self):
        if self.factures_a_mandater:
            for row in self.factures_a_mandater:
                if row.get("facture_fournisseur"):
                    frappe.db.set_value("Facture Fournisseur", row.facture_fournisseur, {
                        "mandat_paiement": None, "numero_mandat": 0,
                        "date_mandat": None, "status": "En Attente",
                    })

    def _retirer_ligne_situation(self):
        if not self.situation_paiement:
            return
        sit = frappe.get_doc("Situation Paiement", self.situation_paiement)
        for i, ligne in enumerate(sit.paiements):
            if ligne.mandat_paiement == self.name:
                sit.paiements.pop(i)
                sit.save(ignore_permissions=True)
                break

#    def _validate_modification_interdite(self):
#         if self.is_new():
#             return
#         # Lire le statut actuel en base (avant le validate)
#         statut_actuel = frappe.db.get_value("Mandat Paiement", self.name, "status_admission")
#         if statut_actuel in ("Payé", "Annulé Définitif"):
#             frappe.throw(_(
#                 "Un mandat au statut « {0} » ne peut plus être modifié."
#             ).format(statut_actuel))
    def _validate_date_mandat(self):
        """Valide la date de mandat."""
        from gestion_financiere.gestion_financiere.doctype.fiche_budgetaire.fiche_budgetaire import valider_date_mandat
        valider_date_mandat(self.date_mandat)

    def _validate_numero_mandat(self):
        if self.numero_mandat:
            # Vérifier l'unicité (sauf ce document et hors annulés)
            existing = frappe.db.exists("Mandat Paiement", {
                "numero_mandat": self.numero_mandat,
                "name": ["!=", self.name or ""],
                #"docstatus": ["!=", 2]
            })
            if existing:
                frappe.throw(_("Le numéro de mandat {0} est déjà utilisé.").format(self.numero_mandat))
    def _set_readonly_fields(self):
        """Remplit les champs calculés depuis les liaisons."""
        
        # Chapitre
        if self.chapitre:
            chap = frappe.get_doc("Budget Chapitre", self.chapitre)
            self.code_chapitre = chap.code
            self.intitule_chapitre = chap.intitule

        # Article
        if self.article:
            art = frappe.get_doc("Budget Article", self.article)
            self.code_article = art.code_article
            self.intitule_article = art.intitule_article
            
            if not self.chapitre:
                self.chapitre = art.budget_chapitre

        # Fournisseur (si type Fournisseur Unique)
        if self.type_creancier == "Fournisseur Unique" and self.fournisseur:
            fourn = frappe.get_doc("Fournisseur", self.fournisseur)
            self.nom_raison_sociale = fourn.raison_sociale or fourn.name
            #self.domicile = fourn.adresse or ""
            self.numero_compte = fourn.numero_compte or ""
            self.type_compte = fourn.type_compte or ""
            if fourn.type_compte == "CCP":
                self.domicile = "CCP"
            elif fourn.type_compte == "Banque":
                self.domicile = fourn.banque or "Banque"
                self.numero_agence = fourn.numero_agence or ""

    def _validate_source(self):
        """Valide qu'une source est sélectionnée et charge les données."""
        
        if not self.type_source:
            frappe.throw(_("Veuillez sélectionner le type de source du mandat."))

        # DÉPENSE INTERNE (A POSTERIORI)
        if self.type_source == "Depense Interne":
            self._load_from_depense_interne()

        # FICHE DEPENSE (A PRIORI)
        elif self.type_source == "Fiche Depense":
            self._load_from_fiche_depense()

    def _load_from_depense_interne(self):
        """Charge depuis Dépense Interne (A posteriori) - 1 mandat par dépense."""
        if not self.depense_interne:
            frappe.throw(_("Veuillez sélectionner une Dépense Interne."))
        
        dep = frappe.get_doc("Depense Interne", self.depense_interne)
        
        # Vérifier statut
        if self.status_admission == "En Attente" :
            if (dep.status != "Envoyé Comptable" and dep.status != "Validé" and dep.status != "Mandaté"):   
                frappe.throw(_(
                    "La Dépense Interne doit être au statut 'Envoyé Comptable'."
                ))
        
        # Règle : 1 seul mandat par dépense
        if dep.mandat_paiement and dep.mandat_paiement != self.name:
            frappe.throw(_(
                "Un mandat existe déjà pour cette Dépense Interne.<br>"
                "<b>Règle : 1 seul mandat par Dépense Interne.</b>"
            ))
        
        # Auto-remplir imputation
        self.article = dep.article
        self.chapitre = dep.chapitre
        #self.partition = dep.partition
        
        # Selon type de dépense
        if dep.type_depense == "Fournisseur":
            self.type_creancier = "Fournisseur Unique"
            self.fournisseur = dep.fournisseur
            
            # Factures
            if dep.factures:
                self.factures_a_mandater = []  # Vider la table d'abord
                factures_list = []
                total = 0
            
                for f_row in dep.factures:
                    # Récupérer la facture fournisseur
                    fact = frappe.get_doc("Facture Fournisseur", f_row.facture_fournisseur)
                    
                    # Ajouter dans la table
                    self.append("factures_a_mandater", {
                        "facture_fournisseur": fact.name,
                        "numero_facture": fact.numero_facture,
                        "date_facture": fact.date_facture,
                        "montant": fact.montant_ttc
                    })
                    
                    # Pour affichage texte
                    factures_list.append(
                        f"Facture N° {fact.numero_facture} du {fact.date_facture} - {flt(fact.montant_ttc):,.2f} DA"
                    )
                    total += flt(fact.montant_ttc)
                
                self.factures_concernees = "\n".join(factures_list)
                self.montant_total = total
            else:
                # Pas de factures dans la dépense
                self.factures_a_mandater = []
                self.factures_concernees = ""
                self.montant_total = dep.montant_total
            
        elif dep.type_depense == "Frais Mission":
            # Vérifier type de compte
            if not dep.type_compte_mission:
                frappe.throw(_("Type de compte des bénéficiaires non défini."))
            
            if len(dep.beneficiaires) == 1:
                # 1 seul bénéficiaire → Afficher ses infos
                benef = dep.beneficiaires[0]
                self.type_creancier = "Liste Personnes"
                self.nom_raison_sociale = benef.nom_prenom
                self.numero_compte = benef.numero_compte
                self.type_compte = benef.type_compte
                if benef.type_compte == "CCP":
                    self.domicile = "CCP"
                    self.numero_agence = ""
                elif benef.type_compte == "Banque":
                    el_benef = frappe.get_doc(benef.type_personne, benef.personne)
                    self.domicile = el_benef.banque 
                    self.numero_agence = el_benef.numero_agence
            else:
                # Plusieurs → DIVERS
                self.type_creancier = f"Divers {dep.type_compte_mission}"
                self.nom_raison_sociale = "DIVERS"
                self.domicile = f"Divers {dep.type_compte_mission}"
                self.numero_compte = "DIVERS"
                self.type_compte = dep.type_compte_mission
                self.numero_agence = ""
            
            self.montant_total = dep.montant_total
            
            # Copier liste
            self.liste_personnes = []
            for benef in dep.beneficiaires:
                row = {
                    "type_personne": benef.type_personne,
                    "personne": benef.personne,
                    "nom_prenom": benef.nom_prenom,
                    "grade": benef.grade,
                    "type_compte": benef.type_compte,
                    "numero_compte": benef.numero_compte,
                    "montant": benef.montant,
                    "banque": "",
                    "numero_agence": "",
                }
                if benef.type_compte == "Banque" :
                    el_benef = frappe.get_doc(benef.type_personne, benef.personne)
                    row["banque"] = el_benef.banque or ""
                    row["numero_agence"] = el_benef.numero_agence or ""
                self.append("liste_personnes", row)
       
        # Objet
        if not self.objet_paiement:
            self.objet_paiement = dep.objet_depense or "Paiement {self.intitule_article}"

    def _load_from_fiche_depense(self):
        """Charge depuis Fiche Dépense (A priori)."""
        if not self.fiche_depense:
            frappe.throw(_("Veuillez sélectionner une Fiche Dépense."))
        
        fiche = frappe.get_doc("Fiche Budgetaire", self.fiche_depense)
        
        # Vérifier type A priori
        if fiche.type_fiche != "Dépense" or fiche.type_article != "A priori":
            frappe.throw(_("La fiche doit être une Dépense A priori."))
        
        # if fiche.status != "Visé CF":
        #     frappe.throw(_("La fiche doit être visée par le CF."))
        
        self.article = fiche.article
        self.chapitre = fiche.chapitre
        self.partition = fiche.code_partition if hasattr(fiche, 'code_partition') else ""
        
        # Selon type d'engagement
        if fiche.type_engagement_apriori == "Bon Commande":
            self._load_from_bon_commande(fiche)
        elif fiche.type_engagement_apriori == "Convention":
            conv = frappe.get_doc("Convention", fiche.convention)
            #if conv.type_convention == "Prestation":
            if not self.situation_paiement:
                frappe.throw(_("Une situation de paiement doit être associée à ce mandat."))
            sit = frappe.get_doc("Situation Paiement", self.situation_paiement)
            if sit.convention != conv.name:
                frappe.throw(_("La situation de paiement ne correspond pas à la convention."))
            # Vérifier que le montant saisi (ou à venir) ne dépasse pas le reste
            if self.is_new():
                reste = flt(sit.reste_a_payer)
            else:
                # Récupérer l'ancien solde de la ligne de ce mandat dans la situation
                ancien_solde = frappe.db.get_value("Paiement Situation Element",
                    {"parent": self.situation_paiement, "mandat_paiement": self.name},
                    "ancien_solde")
                if ancien_solde:
                    reste = flt(ancien_solde)
                else:
                    # Si pas trouvé (devrait pas arriver), on utilise le reste actuel + montant
                    reste = flt(sit.reste_a_payer) + flt(self.montant_total)

            if flt(self.montant_total) > reste + 0.01:
                frappe.throw(_("Le montant du mandat ne peut pas dépasser le reste à payer de la situation."))
           
            # else:
            #     # Convention acquisition
            #     self._load_from_convention(fiche)
        elif fiche.type_engagement_apriori == "Frais Mission":
            #self._load_from_frais_mission_apriori(fiche)
            pass

    def _load_from_bon_commande(self, fiche):
        """BC A priori - 1 seul mandat par BC."""
        if not fiche.bon_commande:
            frappe.throw(_("Aucun Bon de Commande lié."))
        
        bc = frappe.get_doc("Bon Commande", fiche.bon_commande)
        
        # Règle : 1 seul mandat par BC
        mandat_existant = frappe.db.exists(
            "Mandat Paiement",
            {"type_source": "Fiche Depense", "fiche_depense": fiche.name}
        )
        if mandat_existant and mandat_existant != self.name:
            frappe.throw(_(
                "Un mandat existe déjà pour ce BC.<br>"
                "<b>Règle : 1 seul mandat par Bon de Commande.</b>"
            ))
        
        self.type_creancier = "Fournisseur Unique"
        self.fournisseur = bc.prestataire
        
        # Factures sélectionnées
        if self.factures_a_mandater:
            total = 0
            factures_list = []
            for row in self.factures_a_mandater:
                fact = frappe.get_doc("Facture Fournisseur", row.facture_fournisseur)
                if self.type_source == "Fiche Depense" and self.fiche_depense:
                    fiche = frappe.get_doc("Fiche Budgetaire", self.fiche_depense)
                    if fiche.type_engagement_apriori == "Bon Commande":
                        if fact.bon_commande != fiche.bon_commande:
                            frappe.throw(_("La facture {0} n'appartient pas à ce bon de commande.").format(fact.numero_facture))
                    elif fiche.type_engagement_apriori == "Convention":
                        if fact.convention != fiche.convention:
                            frappe.throw(_("La facture {0} n'appartient pas à cette convention.").format(fact.numero_facture))
                row.numero_facture = fact.numero_facture
                row.date_facture = fact.date_facture
                row.montant = fact.montant_ttc
                total += flt(fact.montant_ttc)
                factures_list.append(f"Facture N° {fact.numero_facture} du {fact.date_facture} : {flt(fact.montant_ttc):,.2f} DA")
            
            self.montant_total = total
            self.factures_concernees = "\n".join(factures_list)
            
            if total > flt(bc.total_ttc):
                frappe.throw(_(
                    "Total factures ({0} DA) > Montant BC ({1} DA)"
                ).format(total, bc.total_ttc))
        
        if not self.objet_paiement:
            self.objet_paiement = f"Paiement BC N° {bc.numero_bon_commande}"

    def _load_from_convention(self, fiche):
        """Convention A priori."""
        if not fiche.convention:
            frappe.throw(_("Aucune Convention liée."))
        
        conv = frappe.get_doc("Convention", fiche.convention)
        
        # Convention Acquisition = 1 seul mandat
        # if conv.type_convention == "Acquisition":
        #     mandat_existant = frappe.db.exists(
        #         "Mandat Paiement",
        #         {"type_source": "Fiche Depense", "fiche_depense": fiche.name}
        #     )
        #     if mandat_existant and mandat_existant != self.name:
        #         frappe.throw(_(
        #             "Un mandat existe déjà pour cette Convention Acquisition.<br>"
        #             "<b>Règle : 1 seul mandat par Convention Acquisition.</b>"
        #         ))
        
        self.type_creancier = "Fournisseur Unique"
        self.fournisseur = conv.fournisseur
        
        # Factures
        if self.factures_a_mandater:
            total = 0
            factures_list = []
            for row in self.factures_a_mandater:
                fact = frappe.get_doc("Facture Fournisseur", row.facture_fournisseur)
                if self.type_source == "Fiche Depense" and self.fiche_depense:
                    fiche = frappe.get_doc("Fiche Budgetaire", self.fiche_depense)
                    if fiche.type_engagement_apriori == "Bon Commande":
                        if fact.bon_commande != fiche.bon_commande:
                            frappe.throw(_("La facture {0} n'appartient pas à ce bon de commande.").format(fact.numero_facture))
                    elif fiche.type_engagement_apriori == "Convention":
                        if fact.convention != fiche.convention:
                            frappe.throw(_("La facture {0} n'appartient pas à cette convention.").format(fact.numero_facture))
                row.numero_facture = fact.numero_facture
                row.date_facture = fact.date_facture
                row.montant = fact.montant_ttc
                total += flt(fact.montant_ttc)
                factures_list.append(f"{fact.numero_facture} - {flt(fact.montant_ttc):,.2f} DA")
            
            self.montant_total = total
            self.factures_concernees = "\n".join(factures_list)
            
            if total > flt(conv.montant_convention):
                frappe.throw(_(
                    "Total factures ({0} DA) > Montant Convention ({1} DA)"
                ).format(total, conv.montant_convention))

    def _load_from_frais_mission_apriori(self, fiche):
        """Frais Mission A priori - Diviser par type compte si nécessaire."""
        if not fiche.frais_mission_apriori:
            frappe.throw(_("Aucun Frais Mission lié."))
        
        fm = frappe.get_doc("Frais Mission", fiche.frais_mission_apriori)
        
        # Types de compte présents
        types_compte = set([b.type_compte for b in fm.table_beneficiaires if b.type_compte])
        
        if len(types_compte) == 0:
            frappe.throw(_("Aucun type de compte renseigné."))
        
        # ✅ CAS 1 : Types mixtes (Banque ET CCP) → Scinder en 2 mandats
        if len(types_compte) > 1:
            # L'utilisateur doit choisir quel type pour ce mandat
            if not self.type_creancier or self.type_creancier not in ["Divers Banque", "Divers CCP"]:
                nb_banque = len([b for b in fm.table_beneficiaires if b.type_compte == "Banque"])
                nb_ccp = len([b for b in fm.table_beneficiaires if b.type_compte == "CCP"])
                
                frappe.throw(_(
                    "<b>Frais Mission avec types de compte mixtes</b><br><br>"
                    "Ce Frais Mission contient :<br>"
                    "- {0} bénéficiaire(s) avec compte <b>Banque</b><br>"
                    "- {1} bénéficiaire(s) avec compte <b>CCP</b><br><br>"
                    "<b>Vous devez créer 2 mandats séparés :</b><br>"
                    "1. Un mandat avec <b>Type Créancier = Divers Banque</b><br>"
                    "2. Un mandat avec <b>Type Créancier = Divers CCP</b><br><br>"
                    "Veuillez sélectionner le type pour ce mandat."
                ).format(nb_banque, nb_ccp))
            
            # Filtrer selon le type choisi
            type_filtre = "Banque" if self.type_creancier == "Divers Banque" else "CCP"
            benefs_filtres = [b for b in fm.table_beneficiaires if b.type_compte == type_filtre]
            
            if not benefs_filtres:
                frappe.throw(_(
                    "Aucun bénéficiaire avec compte {0} dans cette liste."
                ).format(type_filtre))
            
            # Vérifier qu'un mandat n'existe pas déjà pour ce type
            mandat_existant = frappe.db.exists(
                "Mandat Paiement",
                {
                    "fiche_depense": fiche.name,
                    "type_creancier": self.type_creancier
                }
            )
            if mandat_existant and mandat_existant != self.name:
                frappe.throw(_(
                    "Un mandat {0} existe déjà pour ce Frais Mission : {1}"
                ).format(self.type_creancier, mandat_existant))
            
            # Type Divers
            self.nom_raison_sociale = "DIVERS"
            self.domicile = f"Divers {type_filtre}"
            self.numero_compte = "DIVERS"
            self.type_compte = type_filtre
            self.numero_agence = ""
            
            # Copier bénéficiaires filtrés
            self.liste_personnes = []
            for benef in benefs_filtres:
                # Mapping depuis votre structure
                type_personne = ''
                if fm.type_missionnaire == 'Etudiants':
                    type_personne = 'Etudiants'
                elif fm.type_missionnaire == 'Enseignant':
                    type_personne = 'Enseignant'
                elif fm.type_missionnaire == 'Personnel Administratif':
                    type_personne = 'Personnel Administratif'
                
                row = {
                    "type_personne": benef.type_personne,
                    "personne": benef.personne,
                    "nom_prenom": benef.nom_prenom,
                    "grade": benef.grade,
                    "type_compte": benef.type_compte,
                    "numero_compte": benef.compte,
                    "montant": benef.montant_mission,
                    "banque": "",
                    "numero_agence": "",
                }
                if benef.type_compte == "Banque" :
                    el_benef = frappe.get_doc(benef.type_personne, benef.personne)
                    row["banque"] = el_benef.banque or ""
                    row["numero_agence"] = el_benef.numero_agence or ""
                self.append("liste_personnes", row)
                # self.append("liste_personnes", {
                #     "type_personne": type_personne,
                #     "personne": benef.personne,
                #     "nom_prenom": benef.nom_prenom,
                #     "grade": benef.grade,
                #     "type_compte": benef.type_compte,
                #     "numero_compte": benef.compte,
                #     "montant": benef.montant_mission,
                # })
        
        # ✅ CAS 2 : Un seul type de compte
        elif len(types_compte) == 1:
            type_unique = list(types_compte)[0]
            
            if len(fm.table_beneficiaires) == 1:
                # 1 seul bénéficiaire → Afficher ses infos
                benef = fm.table_beneficiaires[0]
                self.type_creancier = "Liste Personnes"
                self.nom_raison_sociale = benef.nom_prenom
                self.numero_compte = benef.compte
                self.type_compte = benef.type_compte
                #self.domicile = benef.type_compte
                if benef.type_compte == "CCP":
                    self.domicile = "CCP"
                    #self.type_creancier = "Divers CCP"
                elif benef.type_compte == "Banque":
                    el_benef = frappe.get_doc(benef.type_personne, benef.personne)
                    self.domicile = el_benef.banque or "Banque"
                    self.numero_agence = el_benef.numero_agence or ""
                    
            else:
                # Plusieurs bénéficiaires, même type → Divers
                self.type_creancier = f"Divers {type_unique}"
                self.nom_raison_sociale = "DIVERS"
                self.domicile = f"Divers {type_unique}"
                self.numero_compte = "DIVERS"
                self.type_compte = type_unique
                self.numero_agence = ""
            
            # Copier tous les bénéficiaires
            self.liste_personnes = []
            for benef in fm.table_beneficiaires:
                type_personne = ''
                if fm.type_missionnaire == 'Etudiants':
                    type_personne = 'Etudiants'
                elif fm.type_missionnaire == 'Enseignant':
                    type_personne = 'Enseignant'
                elif fm.type_missionnaire == 'Personnel Administratif':
                    type_personne = 'Personnel Administratif'
                
                row = {
                    "type_personne": benef.type_personne,
                    "personne": benef.personne,
                    "nom_prenom": benef.nom_prenom,
                    "grade": benef.grade,
                    "type_compte": benef.type_compte,
                    "numero_compte": benef.compte,
                    "montant": benef.montant_mission,
                    "banque": "",
                    "numero_agence": "",
                }
                if benef.type_compte == "Banque" :
                    el_benef = frappe.get_doc(benef.type_personne, benef.personne)
                    row["banque"] = el_benef.banque or ""
                    row["numero_agence"] = el_benef.numero_agence or ""
                self.append("liste_personnes", row)

                # self.append("liste_personnes", {
                #     "type_personne": type_personne,
                #     "personne": benef.personne,
                #     "nom_prenom": benef.nom_prenom,
                #     "grade": benef.grade,
                #     "type_compte": benef.type_compte,
                #     "numero_compte": benef.compte,
                #     "montant": benef.montant_mission,
                # })
        
        # Objet
        if not self.objet_paiement:
            type_label = self.type_creancier.replace("Divers ", "") if "Divers" in self.type_creancier else ""
            if type_label:
                self.objet_paiement = f"Paiement Frais Mission ({type_label})"
            else:
                self.objet_paiement = "Paiement Frais Mission"
    
    
    def _validate_creancier(self):
        """Valide les informations du créancier."""
        
        if self.type_creancier == "Fournisseur Unique":
            if not self.fournisseur:
                frappe.throw(_("Veuillez sélectionner un fournisseur."))
            # Si source = Dépense Interne, vérifier que les factures
            # correspondent à celles de la Dépense Interne
            if self.type_source == "Depense Interne" and self.depense_interne:
                dep = frappe.get_doc("Depense Interne", self.depense_interne)
                
                if dep.type_depense == "Fournisseur" and dep.factures:
                    # Récupérer les IDs des factures de la Dépense Interne
                    factures_dep = set([f.facture_fournisseur for f in dep.factures])
                    
                    # Récupérer les IDs des factures du Mandat
                    factures_mandat = set([f.facture_fournisseur for f in self.factures_a_mandater or []])
                    
                    # Vérifier que c'est exactement les mêmes
                    if factures_dep != factures_mandat:
                        frappe.throw(_(
                            "Les factures du mandat doivent correspondre exactement "
                            "à celles de la Dépense Interne.<br>"
                            "La table des factures ne peut pas être modifiée pour "
                            "une Dépense Interne."
                        ))

        elif self.type_creancier in ["Liste Personnes", "Divers Banque", "Divers CCP"]:
            if not self.liste_personnes:
                frappe.throw(_("Veuillez ajouter au moins un bénéficiaire."))
            # Validation du nombre et du type de compte
            if self.type_creancier == "Liste Personnes":
                if len(self.liste_personnes) != 1:
                    frappe.throw(_("Pour le type 'Liste Personnes', il doit y avoir exactement un bénéficiaire."))
            elif self.type_creancier == "Divers Banque":
                for row in self.liste_personnes:
                    if row.type_compte != "Banque":
                        frappe.throw(_("Tous les bénéficiaires doivent avoir le type de compte 'Banque'."))
            elif self.type_creancier == "Divers CCP":
                for row in self.liste_personnes:
                    if row.type_compte != "CCP":
                        frappe.throw(_("Tous les bénéficiaires doivent avoir le type de compte 'CCP'."))

        if self.type_source == "Fiche Depense" and self.fiche_depense and self.type_creancier in ["Liste Personnes", "Divers Banque", "Divers CCP"]:
                fiche = frappe.get_doc("Fiche Budgetaire", self.fiche_depense)
                if fiche.type_engagement_apriori == "Frais Mission":
                    fm = frappe.get_doc("Frais Mission", fiche.frais_mission_apriori)
                    personnes_fm = {b.personne for b in fm.table_beneficiaires}
                    for row in self.liste_personnes:
                        if row.personne not in personnes_fm:
                            frappe.throw(_("Le bénéficiaire {0} ne fait pas partie du frais de mission.").format(row.nom_prenom))

        # Vérification des doublons de bénéficiaires pour une même fiche dépense (Frais Mission)
        if self.type_source == "Fiche Depense" and self.fiche_depense and self.type_creancier in ["Liste Personnes", "Divers Banque", "Divers CCP"]:
            fiche = frappe.get_doc("Fiche Budgetaire", self.fiche_depense)
            if fiche.type_engagement_apriori == "Frais Mission":
                personnes_actuelles = [p.personne for p in self.liste_personnes if p.personne]
                if not personnes_actuelles:
                    return

                # Récupérer les mandats autres que celui-ci
                autres_mandats = frappe.get_all(
                    "Mandat Paiement",
                    filters={
                        "type_source": "Fiche Depense",
                        "fiche_depense": self.fiche_depense,
                        "name": ["!=", self.name or ""],
                        "docstatus": ["!=", 2]
                    },
                    pluck="name"
                )
                if autres_mandats:
                    autres_personnes = frappe.db.get_list(
                        "Mandat Personne Element",
                        filters={
                            "parent": ["in", autres_mandats]
                        },
                        pluck="personne",
                        distinct=True
                    )
                    doublons = set(personnes_actuelles) & set(autres_personnes)
                    if doublons:
                        frappe.throw(_("Les bénéficiaires suivants sont déjà mandatés dans un autre mandat pour ce frais de mission : {0}").format(", ".join(doublons)))

    #
    def _calculate_montant_total(self):
        """Calcule le montant total."""
        
        if self.type_creancier in ["Liste Personnes", "Divers Banque", "Divers CCP"]:
            total = sum(flt(p.montant) for p in self.liste_personnes)
            self.montant_total = total

    def _convert_montant_lettres(self):
        """Convertit le montant en lettres."""
        if not self.montant_total:
            self.montant_lettres = ""
            return
        
        try:
            entier = int(self.montant_total)
            centimes = int((self.montant_total - entier) * 100)
            
            lettres_entier = num2words(entier, lang='fr').upper()
            
            if centimes > 0:
                lettres_centimes = num2words(centimes, lang='fr').upper()
                self.montant_lettres = f"{lettres_entier} DINARS ET {lettres_centimes} CENTIMES"
            else:
                self.montant_lettres = f"{lettres_entier} DINARS"
                
        except Exception as e:
            frappe.log_error(f"Erreur conversion montant: {str(e)}")
            self.montant_lettres = ""

    def _update_source_reference(self):
        """Met à jour la source."""
        
        # Dépense Interne
        if self.type_source == "Depense Interne" and self.depense_interne:
            dep_status = frappe.db.get_value("Depense Interne", self.depense_interne, "status")
            # Ne pas écraser le statut d'une dépense rejetée définitivement
            if dep_status != "Rejeté Définitif":
                update_dict = {
                    "mandat_paiement": self.name,
                    "numero_mandat": self.numero_mandat,
                    "date_mandat": self.date_mandat,
                }
                # Seulement si le mandat est en brouillon (draft)
                if self.docstatus == 0 and self.status_admission == "En Attente":
                    update_dict["status"] = "Mandaté"
                frappe.db.set_value("Depense Interne", self.depense_interne, update_dict)
        # Factures
        if self.factures_a_mandater:
            for row in self.factures_a_mandater:
                frappe.db.set_value(
                    "Facture Fournisseur",
                    row.facture_fournisseur,
                    {
                        "mandat_paiement": self.name,
                        "numero_mandat": self.numero_mandat,
                        "date_mandat": self.date_mandat,
                        "status": "Mandaté"
                    }
                )
        # Situation Paiement (convention prestation)
        if self.type_source == "Fiche Depense" and self.situation_paiement:
            #self._add_ligne_situation_paiement()
            self._mettre_a_jour_situation_paiement()
            
    def _mettre_a_jour_situation_paiement(self):
        if not self.situation_paiement:
            return
        sit = frappe.get_doc("Situation Paiement", self.situation_paiement)
        
        # Vérifier si c'est le premier mandat (aucune ligne avant)
        premiere_ligne = (len(sit.paiements) == 0)

        # Recherche de la ligne existante
        ligne_existante = None
        for ligne in sit.paiements:
            if ligne.mandat_paiement == self.name:
                ligne_existante = ligne
                break

        if ligne_existante:
            # Mise à jour de la ligne
            ligne_existante.montant_operation = self.montant_total
            ligne_existante.factures_payes = self.factures_concernees or ""
            ligne_existante.numero_mandat = self.numero_mandat
            ligne_existante.date_mandat = self.date_mandat   
        else:
            # Ajout d'une nouvelle ligne
            ligne_numero = len(sit.paiements) + 1
            if sit.paiements:
                ancien_solde = sit.paiements[-1].reste_solde
            else:
                ancien_solde = sit.montant_total_convention
            sit.append("paiements", {
                "ligne_numero": ligne_numero,
                "mandat_paiement": self.name,
                "numero_mandat": self.numero_mandat,
                "date_mandat": self.date_mandat,
                "ancien_solde": ancien_solde,
                "montant_operation": self.montant_total,
                "reste_solde": ancien_solde - flt(self.montant_total),
                "factures_payes": self.factures_concernees or ""
            })

        # Si c'était le premier mandat, mettre la convention en "En exécution"
        if premiere_ligne and sit.convention:
            conv = frappe.get_doc("Convention", sit.convention)
            if conv.status not in ["En Exécution", "Soldé"]:
                conv.status = "En Exécution"
                conv.save(ignore_permissions=True)

        # Recalculer les soldes avant sauvegarde
        sit._recalcul_soldes()
        sit.save(ignore_permissions=True)


    # ══════════════════════════════════════════
    #  ACTIONS MÉTIER — appelées depuis les APIs
    # ══════════════════════════════════════════

    def action_envoyer_au_comptable(self, date_envoi_comptable=None):
        """
        Soumet le mandat (docstatus 0→1) = envoi au comptable.
        """
        if self.docstatus != 0:
            frappe.throw(_("Seul un mandat en brouillon peut être envoyé au comptable."))
        self.status_admission = "Envoyé Comptable"
        #self.date_envoi_comptable = date_envoi_comptable
        if self.type_source == "Depense Interne" and self.depense_interne:
            frappe.db.set_value("Depense Interne", self.depense_interne, {
                "status": "Envoyé Comptable",
                "date_envoi_comptable": date_envoi_comptable,
            })
        self.save(ignore_permissions=True)
        self.submit()

    def action_admettre(self, numero_mandat, date_mandat, numero_admission, date_admission, mode_paiement, numero_cheque, date_cheque, date_paiement=None,
                        folio=None, mois=None, ordre=None, numero_jc=None):
        """
        Admission : mandat déjà soumis (docstatus=1), on met à jour les champs.
        Bloque toute modification future (status_admission = "Payé").
        """
        if self.docstatus != 1:
            frappe.throw(_("Le mandat doit être soumis pour être admis."))
        if self.status_admission not in ("Envoyé Comptable",):
            frappe.throw(_("Le mandat doit être au statut 'Envoyé Comptable'."))

        self.numero_mandat = numero_mandat
        self.date_mandat = date_mandat
        self.status_admission  = "Payé"
        self.numero_admission  = numero_admission
        self.date_admission    = date_admission
        self.mode_paiement = mode_paiement
        self.numero_cheque = numero_cheque
        self.date_cheque = date_cheque
        if date_paiement: self.date_paiement = date_paiement
        if folio:         self.folio  = folio
        if mois:          self.mois   = mois
        if ordre:         self.ordre  = ordre
        if numero_jc:     self.numero_jc = numero_jc

        # Passer le status de la dépense interne à Réglé
        if self.type_source == "Depense Interne" and self.depense_interne:
            frappe.db.set_value("Depense Interne", self.depense_interne, {
                "status": "Réglé",  # D'abord marquer comme Réglé
            })
        # Passer les factures en Payé
        if self.factures_a_mandater:
            for row in self.factures_a_mandater:
                if row.get("facture_fournisseur"):
                    frappe.db.set_value("Facture Fournisseur", row.facture_fournisseur, {
                        "status": "Payé",
                    })
        self._update_source_reference()
        self.save(ignore_permissions=True)
        

    def action_rejeter(self, motif, date_rejet=None, definitif=False):
        """
        Rejet : cancel le mandat soumis (docstatus 1→2).
        - Rejet simple    → status_admission = "Rejeté"         → Amend disponible
        - Rejet définitif → status_admission = "Annulé Définitif" → Amend bloqué en JS
        """
        if self.docstatus != 1:
            frappe.throw(_("Seul un mandat soumis peut être rejeté."))
        if self.status_admission not in ("Envoyé Comptable",):
            frappe.throw(_("Le mandat doit être au statut 'Envoyé Comptable' pour être rejeté."))
        if not motif:
            frappe.throw(_("Le motif de rejet est obligatoire."))

        # Enregistrer dans l'historique
        nb = (self.nb_rejets or 0) + 1
        self.nb_rejets = nb
        self.append("historique_rejets", {
            "numero_rejet":    nb,
            "date_rejet":      date_rejet or nowdate(),
            "motif_rejet":     motif,
            "rejet_definitif": 1 if definitif else 0,
        })

        # Poser le statut AVANT le cancel (on_cancel le lira)
        self.status_admission = "Annulé Définitif" if definitif else "Rejeté"
        self.save(ignore_permissions=True)

        # Cancel Frappe → on_cancel() → traite la dépense selon le statut
        self.cancel()

    def action_marquer_corrige(self, date_correction=None, corrections=None):
        """
        Après Amend : le nouveau draft est corrigé, prêt à re-soumettre.
        Enregistre la correction dans la dernière ligne de l'historique.
        """
        if self.docstatus != 0:
            frappe.throw(_("Seul un mandat en brouillon (après Amend) peut être marqué corrigé."))

        for row in reversed(self.historique_rejets or []):
            if not row.date_correction:
                row.date_correction = date_correction or nowdate()
                if corrections:
                    row.corrections   = corrections
                    #row.motif_rejet = (row.motif_rejet or "") + f"\n→ Corrections : {corrections}"
                break

        self.status_admission = "En Attente"
        self.save(ignore_permissions=True)

    # # ══════════════════════════════════════════
    # #  ACTION : Enregistrer un rejet
    # #  Appelée depuis le JS (bouton « Rejeter »)
    # # ══════════════════════════════════════════

    # def enregistrer_rejet(self, motif, definitif=False, date_rejet=None):
    #     """
    #     Ajoute une ligne dans historique_rejets et met à jour les statuts.

    #     Si definitif=True :
    #       - Mandat       → status_admission = "Annulé Définitif"
    #       - Dépense Interne → status = "Rejeté Définitif", docstatus=2 (annulé)
    #       - Les factures reprennent le statut "En Attente"

    #     Sinon :
    #       - Mandat       → status_admission = "Rejeté"
    #       - Dépense Interne → status = "Mandaté" (prête pour correction)
    #     """
    #     if not motif:
    #         frappe.throw(_("Le motif de rejet est obligatoire."))

    #     # Incrémenter le compteur
    #     nb = (self.nb_rejets or 0) + 1

    #     # Ajouter une ligne dans la table historique
    #     self.append("historique_rejets", {
    #         "numero_rejet": nb,
    #         "date_rejet": date_rejet,
    #         "motif_rejet": motif,
    #         "rejet_definitif": 1 if definitif else 0,
    #     })

    #     self.nb_rejets = nb

    #     if definitif:
    #         self.status_admission = "Annulé Définitif"

    #         # 1. Sauvegarder l'historique + statut pendant qu'on est en draft
    #         self.save(ignore_permissions=True)

    #         # 2. Traiter la Dépense Interne (avant le cancel du mandat)
    #         self._annuler_depense_interne_definitif(motif)

    #         # 3. Passer le mandat en docstatus=2 (Cancelled) :
    #         #    Le mandat est en draft (docstatus=0) → submit (→1) → cancel (→2)
    #         #    on_cancel détecte "Annulé Définitif" sur la dépense et ne restaure pas.
    #         try:
    #             frappe.db.set_value("Mandat Paiement", self.name, "docstatus", 1)
    #             frappe.db.commit()
    #             doc_frais = frappe.get_doc("Mandat Paiement", self.name)
    #             doc_frais.cancel()
    #             frappe.db.commit()
    #         except Exception as e:
    #             frappe.log_error(frappe.get_traceback(), "Rejet définitif mandat — erreur cancel")
    #             # Fallback direct si cancel() échoue
    #             frappe.db.set_value("Mandat Paiement", self.name, "docstatus", 2)
    #             frappe.db.commit()
    #         #self.status_admission = "Annulé Définitif"
    #         #self._annuler_depense_interne_definitif(motif)
    #     else:
    #         self.status_admission = "Rejeté"
    #         # La dépense reste mandatée mais le mandat passe en Rejeté :
    #         # le service budget peut corriger puis renvoyer
    #         if self.type_source == "Depense Interne" and self.depense_interne:
    #             frappe.db.set_value(
    #                 "Depense Interne",
    #                 self.depense_interne,
    #                 {"status": "Mandaté"},   # on garde le lien mandat
    #             )

    #     self.save(ignore_permissions=True)

    # def _annuler_depense_interne_definitif(self, motif):
    #     """
    #     Rejet définitif : annule la Dépense Interne (docstatus=2)
    #     et remet les factures en 'En Attente'.
    #     La dépense reste visible mais exclue du calcul des soldes.
    #     """
    #     if not (self.type_source == "Depense Interne" and self.depense_interne):
    #         return

    #     dep = frappe.get_doc("Depense Interne", self.depense_interne)

    #     # Annuler la Dépense Interne via Frappe (docstatus=2)
    #     if dep.docstatus != 2:
    #         # On utilise db.set_value pour éviter les triggers de validate
    #         frappe.db.set_value("Depense Interne", dep.name, {
    #             "status": "Rejeté Définitif",
    #             "mandat_paiement": None,
    #             "numero_mandat": 0,
    #             "date_mandat": None,
    #             #"docstatus": 2,         # Annulé Frappe
    #         })

    #     # Remettre les factures en "En Attente"
    #     if self.factures_a_mandater:
    #         for row in self.factures_a_mandater:
    #             if row.facture_fournisseur:
    #                 frappe.db.set_value("Facture Fournisseur", row.facture_fournisseur, {
    #                     "mandat_paiement": None,
    #                     "numero_mandat": 0,
    #                     "date_mandat": None,
    #                     "status": "En Attente",
    #                 })

    #     frappe.msgprint(_(
    #         "Dépense interne {0} annulée définitivement (rejet définitif). "
    #         "Le document est conservé avec la trace des rejets."
    #     ).format(self.depense_interne), indicator="orange")

    # # ══════════════════════════════════════════
    # #  ACTION : Correction après rejet simple
    # #  Appelée depuis le JS (bouton « Marquer corrigé »)
    # # ══════════════════════════════════════════

    # def marquer_corrige(self, date_correction=None, corrections=None):
    #     """
    #     Le service budget a corrigé le mandat et la dépense.
    #     Met à jour la dernière ligne rejet avec la date de correction
    #     et repasse le mandat en 'En Attente' pour renvoi au comptable.
    #     """
    #     if self.status_admission not in ("Rejeté",):
    #         frappe.throw(_(
    #             "Seul un mandat au statut « Rejeté » peut être marqué comme corrigé."
    #         ))

    #     # Mettre à jour la dernière ligne de rejet
    #     for row in reversed(self.historique_rejets):
    #         if not row.date_correction:
    #             row.date_correction = date_correction 
    #             row.corrige_par = frappe.session.user
    #             if corrections:
    #                 # Ajouter les corrections au motif existant
    #                 row.motif_rejet = (row.motif_rejet or "") + f"\n→ Corrections : {corrections}"
    #             break

    #     self.status_admission = "En Attente"
    #     self.save(ignore_permissions=True)

    # # ══════════════════════════════════════════
    # #  ACTION : Envoyer au comptable
    # # ══════════════════════════════════════════

    # def envoyer_au_comptable(self, date_envoi_comptable=None):
    #     """
    #     Passe le mandat et la dépense interne liée en 'Envoyé Comptable'.
    #     Validation : la dépense doit être en état Mandaté ou Validé.
    #     """
    #     if self.status_admission not in ("En Attente",):
    #         frappe.throw(_(
    #             "Le mandat doit être au statut « En Attente » pour être envoyé au comptable."
    #         ))

    #     self.status_admission = "Envoyé Comptable"
    #     if self.type_source == "Depense Interne" and self.depense_interne:
    #         frappe.db.set_value("Depense Interne", self.depense_interne, {
    #             "status": "Envoyé Comptable",
    #             "date_envoi_comptable": date_envoi_comptable,
    #         })
    #     self.save(ignore_permissions=True)

    # # ══════════════════════════════════════════
    # #  ACTION : Admettre (payé)
    # # ══════════════════════════════════════════

    # def admettre(self, numero_admission, date_admission, folio=None,
    #              mois=None, ordre=None, numero_jc=None):
    #     """
    #     Admission du mandat par le comptable.
    #     Passe en Payé et régularise la dépense interne.
    #     """
    #     if self.status_admission != "Envoyé Comptable":
    #         frappe.throw(_(
    #             "Le mandat doit être au statut « Envoyé Comptable » pour être admis."
    #         ))

    #     self.status_admission = "Admis"
    #     self.numero_admission = numero_admission
    #     self.date_admission = date_admission
    #     if folio:
    #         self.folio = folio
    #     if mois:
    #         self.mois = mois
    #     if ordre:
    #         self.ordre = ordre
    #     if numero_jc:
    #         self.numero_jc = numero_jc

    #     # Marquer la Dépense Interne comme Régularisée
    #     if self.type_source == "Depense Interne" and self.depense_interne:
    #         frappe.db.set_value("Depense Interne", self.depense_interne, {
    #             "status": "Régularisé",
    #         })

    #     # Mettre les factures en "Payé"
    #     if self.factures_a_mandater:
    #         for row in self.factures_a_mandater:
    #             if row.facture_fournisseur:
    #                 frappe.db.set_value("Facture Fournisseur", row.facture_fournisseur, {
    #                     "status": "Payé",
    #                 })

    #     self.save(ignore_permissions=True)


# ═══════════════════════════════════════════════════════════
# API
# ═══════════════════════════════════════════════════════════

@frappe.whitelist()
def get_depenses_pour_mandat(budget_global, article=None):
    """Dépenses Internes prêtes pour mandat."""
    filters = {
        "budget_global": budget_global,
        "status": ["Valide"],
        "mandat_paiement": ["in", ["", None]],
    }
    
    if article:
        filters["article"] = article
    
    return frappe.get_all(
        "Depense Interne",
        filters=filters,
        fields=[
            "name", "numero_interne", "type_depense", "montant_total",
            "fournisseur", "article", "semestre"
        ],
        order_by="date_depense desc"
    )


@frappe.whitelist()
def get_situations_pour_mandat(budget_global):
    """Situations avec reste à payer."""
    situations = frappe.get_all(
        "Situation Paiement",
        filters={
            "budget_global": budget_global,
            "status": "En Cours",
        },
        fields=[
            "name", "convention", "numero_convention",
            "fournisseur", "montant_total_convention",
            "montant_paye", "reste_a_payer"
        ]
    )
    
    return [s for s in situations if flt(s.reste_a_payer) > 0]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_factures_pour_mandat(doctype, txt, searchfield, start, page_len, filters):
    """
    Retourne les factures disponibles pour un mandat.
    Les filtres peuvent contenir soit 'fiche_depense' soit 'situation_paiement'.
    """
    fiche_depense = filters.get('fiche_depense')
    situation_paiement = filters.get('situation_paiement')
    mandat_actuel = filters.get('mandat_actuel')
    fournisseur = filters.get('fournisseur')

    if not fiche_depense and not situation_paiement:
        return []

    filter_list = []

    # Déterminer la référence (BC ou Convention)
    if fiche_depense:
        fiche = frappe.get_doc("Fiche Budgetaire", fiche_depense)
        if fiche.type_engagement_apriori == "Bon Commande" and fiche.bon_commande:
            filter_list.append(["bon_commande", "=", fiche.bon_commande])
        elif fiche.type_engagement_apriori == "Convention" and fiche.convention:
            filter_list.append(["convention", "=", fiche.convention])
        else:
            return []
    # elif situation_paiement:
    #     sit = frappe.get_doc("Situation Paiement", situation_paiement)
    #     if sit.convention:
    #         filter_list.append(["convention", "=", sit.convention])
    #     else:
    #         return []

    # Fournisseur
    if fournisseur:
        filter_list.append(["fournisseur", "=", fournisseur])

    # Statut
    filter_list.append(["status", "=", "En Attente"])

    # Condition sur le mandat_paiement
    if mandat_actuel:
        filter_list.append(["mandat_paiement", "in", ["", None, mandat_actuel]])
    else:
        filter_list.append(["mandat_paiement", "in", ["", None]])

    # Recherche textuelle
    if txt:
        filter_list.append(["numero_facture", "like", f"%{txt}%"])

    factures = frappe.get_list(
        "Facture Fournisseur",
        filters=filter_list,
        fields=["name", "numero_facture", "date_facture", "montant_ttc"],
        order_by="date_facture asc",
        limit_start=start,
        limit_page_length=page_len
    )

    return [
        [f.name, f.numero_facture, f.date_facture, f.montant_ttc]
        for f in factures
    ]

# ═══════════════════════════════════════════════════════════
#  APIs Mandat Paiement avec Bonnes Signatures
#  
# ═══════════════════════════════════════════════════════════

@frappe.whitelist()
def get_factures_disponibles_mandat(fiche_depense, fournisseur):
    """
    Retourne les factures disponibles pour un mandat.
    
    ⚠️ ATTENTION : Cette fonction est appelée DIRECTEMENT, 
    pas comme query de Link Field.
    
    Utilisation : Depuis le bouton "Charger Factures" dans le JS.
    """
    if not fiche_depense or not fournisseur:
        return []
    
    # Récupérer la fiche
    fiche = frappe.get_doc("Fiche Budgetaire", fiche_depense)
    
    # Déterminer la référence (BC ou Convention)
    reference = None
    type_reference = None
    
    if fiche.bon_commande:
        reference = fiche.bon_commande
        type_reference = "Bon Commande"
    elif fiche.convention:
        reference = fiche.convention
        type_reference = "Convention"
    else:
        frappe.throw(_("La fiche n'a ni BC ni Convention liée."))
    
    # ✅ Récupérer les factures avec Frappe ORM
    filters = {
        "fournisseur": fournisseur,
        "type_reference": type_reference,
        "status": ["in", ["Validé", "En Attente"]]
    }
    
    # Ajouter le filtre BC ou Convention
    if type_reference == "Bon Commande":
        filters["bon_commande"] = reference
    else:
        filters["convention"] = reference
    
    # Récupérer les factures
    factures = frappe.get_all(
        "Facture Fournisseur",
        filters=filters,
        fields=[
            "name",
            "numero_facture",
            "date_facture",
            "montant_ttc",
            "bon_commande",
            "convention"
        ],
        order_by="date_facture asc"
    )
    
    # ✅ Exclure les factures déjà mandatées
    factures_deja_mandatees = frappe.get_all(
        "Facture Mandat Element",
        filters={
            "parenttype": "Mandat Paiement"
        },
        fields=["facture_fournisseur"],
        pluck="facture_fournisseur"
    )
    
    # Filtrer les factures non mandatées
    factures_disponibles = [
        f for f in factures 
        if f.name not in factures_deja_mandatees
    ]
    
    return factures_disponibles


@frappe.whitelist()
def charger_info_fiche_depense(fiche_depense):
    """
    Charge les informations depuis une Fiche Dépense.
    
    ⚠️ ATTENTION : Appelée directement depuis le JS.
    
    Retourne : article, chapitre, partition, fournisseur, etc.
    """
    if not fiche_depense:
        return {}
    
    fiche = frappe.get_doc("Fiche Budgetaire", fiche_depense)
    
    # Vérifier type
    if fiche.type_fiche != "Dépense":
        frappe.throw(_("La fiche sélectionnée n'est pas une Fiche Dépense."))
    
    if fiche.type_article != "A priori":
        frappe.throw(_("La fiche sélectionnée n'est pas A Priori. Utilisez 'Depense Interne'."))
    
    # if fiche.status != "Visé CF":
    #     frappe.throw(_("La fiche doit être visée par le CF avant de créer un mandat."))
    
    # Préparer les données
    data = {
        "article": fiche.article,
        "chapitre": fiche.chapitre,
        "partition": fiche.partition if hasattr(fiche, 'partition') else None,
        "type_engagement": fiche.type_engagement_apriori,
        "fournisseur": None,
        "type_creancier": "Fournisseur Unique",
        "bon_commande": None,
        "convention": None,
        "type_convention": None,
    }
    
    # Selon le type d'engagement
    if fiche.type_engagement_apriori == "Bon Commande":
        if fiche.bon_commande:
            bc = frappe.get_doc("Bon Commande", fiche.bon_commande)
            data["fournisseur"] = bc.prestataire
            data["bon_commande"] = bc.name
            data["objet"] = f"Paiement BC N° {bc.numero_bon_commande}"
            
    elif fiche.type_engagement_apriori == "Convention":
        if fiche.convention:
            conv = frappe.get_doc("Convention", fiche.convention)
            data["fournisseur"] = conv.fournisseur
            data["convention"] = conv.name
            data["type_convention"] = conv.type_convention
            data["objet"] = f"Paiement Convention N° {conv.numero_convention}"
            
            # # Vérifier type convention
            # if conv.type_convention == "Prestation":
            #     frappe.msgprint(_(
            #         "<b>Convention Prestation détectée</b><br>"
            #         "Pour les Conventions Prestation, vous devriez normalement "
            #         "utiliser le type de source 'Situation Paiement' pour créer "
            #         "des mandats partiels."
            #     ), indicator="orange", alert=True)
    
    elif fiche.type_engagement_apriori == "Frais Mission":
        # Pour Frais Mission, pas de fournisseur
        data["type_creancier"] = "Liste Personnes"
        data["fournisseur"] = None
        data["frais_mission_apriori"] = fiche.frais_mission_apriori
    
    return data


@frappe.whitelist()
def verifier_mandat_existant(fiche_depense, type_engagement):
    """
    Vérifie si un mandat existe déjà pour cette fiche.
    
    ⚠️ ATTENTION : Appelée directement depuis le JS.
    
    Règles :
    - BC : 1 seul mandat autorisé
    - Convention : Plusieurs mandats possibles avec situation paiement
    """
    if not fiche_depense:
        return {"exists": False}
    
    mandat_existant = frappe.db.get_value(
        "Mandat Paiement",
        {
            "type_source": "Fiche Depense",
            "fiche_depense": fiche_depense,
            "docstatus": ["!=", 2]
        },
        "name"
    )
    
    if mandat_existant:
        return {
            "exists": True,
            "mandat": mandat_existant,
            "message": f"Un mandat existe déjà : {mandat_existant}"
        }
    
    return {"exists": False}

@frappe.whitelist()
def get_personnes_deja_mandatees(fiche_depense, mandat_actuel=None):
    """
    Retourne la liste des personnes (bénéficiaires) déjà mandatées pour cette fiche dépense,
    dans d'autres mandats (sauf le mandat actuel).
    """
    if not fiche_depense:
        return []

    filters = {
        "type_source": "Fiche Depense",
        "fiche_depense": fiche_depense,
        "docstatus": ["!=", 2]
    }
    if mandat_actuel:
        filters["name"] = ["!=", mandat_actuel]

    mandats = frappe.get_all("Mandat Paiement", filters=filters, pluck="name")

    if not mandats:
        return []

    # Récupérer les personnes via la table enfant (Mandat Personne Element)
    personnes = frappe.get_all(
        "Mandat Personne Element",
        filters={
            "parenttype": "Mandat Paiement",
            "parent": ["in", mandats]
        },
        pluck="personne",
        distinct=True
    )
    return personnes

# # ═══════════════════════════════════════════════════════════
# #  API WORKFLOW STATUS ADMISSION — appelées depuis le JS
# # ═══════════════════════════════════════════════════════════

# @frappe.whitelist()
# def rejeter_mandat(mandat_name, motif, definitif=0):
#     """
#     Enregistre un rejet (simple ou définitif) sur un mandat.

#     Appel JS :
#         frappe.call({
#             method: "...mandat_paiement.rejeter_mandat",
#             args: { mandat_name, motif, definitif: 0 ou 1 }
#         })
#     """
#     mandat = frappe.get_doc("Mandat Paiement", mandat_name)

#     if mandat.status_admission not in ("Envoyé Comptable", "Rejeté"):
#         frappe.throw(_(
#             "Impossible de rejeter un mandat au statut « {0} »."
#         ).format(mandat.status_admission))

#     mandat.enregistrer_rejet(motif=motif, definitif=bool(int(definitif)))
#     return {
#         "status": mandat.status_admission,
#         "nb_rejets": mandat.nb_rejets,
#         "message": _(
#             "Rejet définitif enregistré." if int(definitif) else "Rejet enregistré. Le service budget peut corriger et renvoyer."
#         ),
#     }


# @frappe.whitelist()
# def marquer_corrige(mandat_name):
#     """
#     Le service budget indique que les corrections sont faites.
#     Repasse le mandat en 'En Attente'.
#     """
#     mandat = frappe.get_doc("Mandat Paiement", mandat_name)
#     mandat.marquer_corrige()
#     return {"status": mandat.status_admission}


# @frappe.whitelist()
# def envoyer_au_comptable(mandat_name):
#     """Envoie le mandat (et la dépense liée) au comptable."""
#     mandat = frappe.get_doc("Mandat Paiement", mandat_name)
#     mandat.envoyer_au_comptable()
#     return {"status": mandat.status_admission}


# @frappe.whitelist()
# def admettre_mandat(mandat_name, numero_admission, date_admission,
#                     folio=None, mois=None, ordre=None, numero_jc=None):
#     """Admet le mandat (statut Admis/Payé)."""
#     mandat = frappe.get_doc("Mandat Paiement", mandat_name)
#     mandat.admettre(
#         numero_admission=numero_admission,
#         date_admission=date_admission,
#         folio=folio, mois=mois, ordre=ordre, numero_jc=numero_jc,
#     )
#     return {"status": mandat.status_admission}


# @frappe.whitelist()
# def get_historique_rejets(mandat_name):
#     """Retourne l'historique des rejets d'un mandat pour affichage JS."""
#     rejets = frappe.get_all(
#         "Rejet Mandat Element",
#         filters={"parent": mandat_name, "parenttype": "Mandat Paiement"},
#         fields=["numero_rejet", "date_rejet", "motif_rejet",
#                 "rejet_definitif", "date_correction", "corrige_par"],
#         order_by="numero_rejet asc",
#     )
#     return rejets

# ═══════════════════════════════════════════════════════════
#  API WORKFLOW STATUS ADMISSION — appelées depuis le JS
# ═══════════════════════════════════════════════════════════

@frappe.whitelist()
def rejeter_mandat(mandat_name, motif, definitif=0, date_rejet=None):
    """
    Rejet simple ou définitif d'un mandat soumis.
    - Rejet simple    : docstatus → 2, status_admission = "Rejeté"          → Amend possible
    - Rejet définitif : docstatus → 2, status_admission = "Annulé Définitif" → Amend bloqué JS
    """
    mandat = frappe.get_doc("Mandat Paiement", mandat_name)
    definitif_bool = bool(int(definitif))
    mandat.action_rejeter(motif=motif, date_rejet=date_rejet, definitif=definitif_bool)
    return {
        "status":    mandat.status_admission,
        "nb_rejets": mandat.nb_rejets,
        "message": _(
            "Rejet définitif enregistré. Le mandat est annulé définitivement."
            if definitif_bool else
            "Rejet enregistré. Utilisez 'Amend' pour créer un mandat corrigé."
        ),
    }


@frappe.whitelist()
def marquer_corrige(mandat_name, date_correction=None, corrections=None):
    """
    Après Amend : marquer les corrections effectuées sur le nouveau draft.
    """
    mandat = frappe.get_doc("Mandat Paiement", mandat_name)
    mandat.action_marquer_corrige(
        date_correction=date_correction,
        corrections=corrections,
    )
    return {"status": mandat.status_admission}


@frappe.whitelist()
def envoyer_au_comptable(mandat_name, date_envoi_comptable=None):
    """Soumet le mandat (docstatus 0→1) = envoi au comptable."""
    mandat = frappe.get_doc("Mandat Paiement", mandat_name)
    mandat.action_envoyer_au_comptable(date_envoi_comptable)
    return {"status": mandat.status_admission, "docstatus": mandat.docstatus}


@frappe.whitelist()
def admettre_mandat(mandat_name, numero_mandat, date_mandat, numero_admission, date_admission,
                    mode_paiement, numero_cheque, date_cheque, date_paiement=None, folio=None, mois=None,
                    ordre=None, numero_jc=None):
    """Admission et paiement du mandat soumis (docstatus=1)."""
    mandat = frappe.get_doc("Mandat Paiement", mandat_name)
    mandat.action_admettre(
        numero_mandat=numero_mandat,
        date_mandat=date_mandat,
        numero_admission=numero_admission,
        date_admission=date_admission,
        mode_paiement=mode_paiement,
        numero_cheque=numero_cheque,
        date_cheque=date_cheque,
        date_paiement=date_paiement,
        folio=folio, mois=mois, ordre=ordre, numero_jc=numero_jc,
    )
    return {"status": mandat.status_admission}


@frappe.whitelist()
def get_historique_rejets(mandat_name):
    """Retourne l'historique des rejets d'un mandat pour affichage JS."""
    rejets = frappe.get_all(
        "Rejet Mandat Element",
        filters={"parent": mandat_name, "parenttype": "Mandat Paiement"},
        fields=["numero_rejet", "date_rejet", "motif_rejet",
                "rejet_definitif", "date_correction", "corrige_par"],
        order_by="numero_rejet asc",
    )
    return rejets
