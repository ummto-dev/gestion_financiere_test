import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate
from num2words import num2words

class DepenseInterne(Document):
    
    def _get_article_info(self, article):
        """Récupère les informations de l'article."""
        return frappe.db.get_value("Budget Article", article, ["type", "code_article", "intitule_article"], as_dict=True)

    def autoname(self):
        """Génère le name du document."""
        self._set_numero_interne()
        #annee = frappe.db.get_value("Annee Budgetaire", self.annee_budgetaire, "annee")
        #code_art = frappe.db.get_value("Article", self.article, "code_article")
        self.name = f"DINT-{self.article}-{str(self.numero_interne).zfill(4)}"

    def before_insert(self):
        """Appelé avant insertion."""
        if not self.numero_interne:
            self._set_numero_interne()
            #self._calculer_ancien_solde()
        
    def validate(self):
        # Bloquer modification si annulée définitivement
        if not self.is_new():
            statut_actuel = frappe.db.get_value("Depense Interne", self.name, "status")
            if statut_actuel == "Rejeté Définitif":
                frappe.throw(_(
                    "Cette dépense a été rejetée définitivement. Elle ne peut plus être modifiée."
                ))
        """Validations lors de la sauvegarde."""
        self._validate_article_aposteriori()
        self._validate_status_workflow()
        self._validate_provision_visee()
        self._validate_type_depense()
        self._validate_factures_doublons()     
        self._validate_factures_status()       
        self._validate_factures_coherence()
        self._validate_type_compte_beneficiaires()
        self._validate_factures_fournisseur()
        self._validate_beneficiaires_frais_mission()
        self._calculate_montant_operation()
        self._calculer_ancien_solde()
        self._calculer_nouveau_solde()
        self._convert_montant_lettres()
        self._set_objet_auto()
        # Vérification du solde suffisant
        if flt(self.montant_total) > flt(self.ancien_solde):
            frappe.throw(_(
                "⚠️ Solde insuffisant !<br><br>"
                "<b>Solde disponible avant cette dépense :</b> {0} DA<br>"
                "<b>Montant de cette dépense :</b> {1} DA<br>"
                "<b>Dépassement :</b> {2} DA"
            ).format(
                flt(self.ancien_solde),
                flt(self.montant_total),
                flt(self.montant_total) - flt(self.ancien_solde)
            ))
        if self.status == "Mandaté" and self.mandat_paiement:
            frappe.throw(_("Une dépense mandatée ne peut plus être modifiée. Annulez d'abord le mandat."))
    
   
    # ══════════════════════════════════════════
    #  NUMÉROTATION
    # ══════════════════════════════════════════

    def _set_numero_interne(self):
        """
        Génère un numéro séquentiel pour la dépense interne.
        Le premier numéro est égal au numéro de la provision S1 de l'article + 1,
        puis incrémenté pour chaque nouvelle dépense (tous semestres confondus).
        """
        # Récupérer le numéro de la provision S1 pour cet article (visée CF)
        provision = frappe.db.get_value(
            "Fiche Budgetaire",
            filters={
                "article": self.article,
                "budget_global": self.budget_global,
                "type_fiche": "Provision",
                "semestre": "S1",
                #"docstatus": 1  # soumise (visée CF)
                #"status": ["in", ["Signé Doyen", "Envoyé CF", "Visé CF"]],
                "docstatus": ["!=", 2],
            },
            fieldname="numero_fiche",
            order_by="numero_fiche desc"
        )
        if not provision:
            frappe.throw(_(
                "Aucune provision S1 trouvée pour l'article {0}. "
                "Veuillez d'abord créer et viser la provision S1."
            ).format(self.article))
        
        # Récupérer le maximum des numéros des dépenses internes existantes pour cet article
        filters = {
            "article": self.article,
            "budget_global": self.budget_global,
        }
        if self.name:
            filters["name"] = ["!=", self.name]
        
        max_dep = frappe.db.get_value(
            "Depense Interne",
            filters=filters,
            fieldname="max(numero_interne)"
        ) or 0
        
        # Le prochain numéro doit être au moins provision + 1, et supérieur au max existant
        base = provision + 1
        self.numero_interne = max(base, max_dep + 1)
  
    def _calculate_montant_operation(self):
        """Calcule le montant_operation de cette dépense"""
        if self.type_depense == "Fournisseur":
            self.montant_operation = sum(
                flt(f.montant) for f in self.factures if f.inclure
            )
            self.montant_total = self.montant_operation
        elif self.type_depense == "Frais Mission":
            self.montant_operation = sum(
                flt(b.montant) for b in self.beneficiaires
            )
            self.montant_total = self.montant_operation
        else:
            self.montant_operation = 0
            self.montant_total = 0

    def _calculer_nouveau_solde(self):
        """
        Calcule le nouveau solde = ancien_solde - montant_operation
        """
        self.nouveau_solde = flt(self.ancien_solde) - flt(self.montant_operation)
        
    def _validate_article_aposteriori(self):
        """Vérifie que l'article est de type A posteriori."""
        if not self.article:
            return
        
        article_info = self._get_article_info(self.article)
        
        if article_info.type != "A posteriori":
            frappe.throw(_(
                "Les Dépenses Internes sont réservées aux articles À Posteriori. "
                "L'article sélectionné ({0}) est de type {1}.<br><br>"
                "Pour les articles À Priori, utilisez les Fiches Dépense."
            ).format(article_info.code_article, article_info.type))

    def _validate_status_workflow(self):
        """Valide la cohérence du workflow de statut."""
        if self.status == "Réglé" and not self.mandat_paiement:
            frappe.throw(_(
                "Une dépense ne peut être marquée comme 'Réglée' sans mandat de paiement."
            ))
        
        if self.status == "Régularisé" and self.status != "Réglé":
            frappe.throw(_(
                "Une dépense doit être 'Réglée' avant d'être 'Régularisée'."
            ))
        
        if self.status == "Rejeté Définitif" and self.status == "Régularisé":
            frappe.throw(_(
                "Une dépense régularisée ne peut être rejetée."
            ))
    
    def _validate_provision_visee(self):
        """Vérifie que la provision du semestre est visée CF."""
        if not self.provision_reference:
            frappe.throw(_("Veuillez sélectionner la Provision de référence."))
        
        prov = frappe.get_doc("Fiche Budgetaire", self.provision_reference)
        
        # Vérifier que c'est bien une Provision
        if prov.type_fiche != "Provision":
            frappe.throw(_(
                "La fiche référencée doit être une Provision."
            ))
        
        # Vérifier le semestre
        if prov.semestre != self.semestre:
            frappe.throw(_(
                "La Provision référencée (semestre {0}) ne correspond pas "
                "au semestre de la dépense ({1})."
            ).format(prov.semestre, self.semestre))
        
        # Vérifier que la provision est visée CF
        if prov.status == "Rejeté Définitif":
            frappe.throw(_(
                "La Provision du semestre {0} est rejétée définitivement. "
                "Vous ne pouvez pas créer de dépense pour cette provision."
            ).format(self.semestre))
        
        # Vérifier l'article
        if prov.article != self.article:
            frappe.throw(_(
                "La Provision référencée appartient à l'article {0}, "
                "pas à l'article {1}."
            ).format(prov.article, self.article))

    def _validate_type_depense(self):
        """Valide les données selon le type de dépense."""
        
        if self.type_depense == "Fournisseur":
            if not self.fournisseur:
                frappe.throw(_("Veuillez sélectionner un fournisseur."))
            
            if not self.factures:
                frappe.throw(_("Veuillez ajouter au moins une facture."))
        
        elif self.type_depense == "Frais Mission":
            if not self.frais_mission:
                frappe.throw(_("Veuillez sélectionner un Frais Mission."))
            
            if not self.beneficiaires:
                frappe.throw(_(
                    "Veuillez charger les bénéficiaires depuis le Frais Mission."
                ))
            
            # Vérifier que le Frais Mission correspond à l'article
            fm = frappe.get_doc("Frais Mission", self.frais_mission)
            if fm.article != self.article:
                frappe.throw(_(
                    "Le Frais Mission sélectionné appartient à l'article {0}, "
                    "pas à l'article {1}."
                ).format(fm.article, self.article))
            
            # ✅ VALIDATION STRICTE pour A POSTERIORI : Type compte unique
            types_compte = set([b.type_compte for b in fm.table_beneficiaires if b.type_compte])
            
            if len(types_compte) == 0:
                frappe.throw(_(
                    "Aucun type de compte renseigné pour les bénéficiaires."
                ))
                        
            if len(types_compte) > 1:
                nb_banque = len([b for b in fm.table_beneficiaires if b.type_compte == "Banque"])
                nb_ccp = len([b for b in fm.table_beneficiaires if b.type_compte == "CCP"])
                        
                frappe.throw(_(
                    "⚠️ <b>RÈGLE Articles A Posteriori</b><br><br>"
                    "Le Frais Mission contient :<br>"
                    "- {0} avec <b>Banque</b><br>"
                    "- {1} avec <b>CCP</b><br><br>"
                    "Pour les articles À Posteriori, tous les bénéficiaires "
                    "doivent avoir le <b>même type de compte</b>.<br><br>"
                    "💡 <i>Créez 2 Frais Mission séparés.</i>"
                ).format(nb_banque, nb_ccp))
                
    def _validate_factures_doublons(self):
        """Empêche d'ajouter la même facture plusieurs fois."""
        if self.type_depense != "Fournisseur":
            return
        
        if not self.factures:
            return
        
        factures_vues = {}
        
        for row in self.factures:
            if not row.facture_fournisseur:
                continue
            
            if row.facture_fournisseur in factures_vues:
                frappe.throw(_(
                    "❌ <b>Doublon détecté</b><br><br>"
                    "La facture <b>{0}</b> apparaît plusieurs fois.<br><br>"
                    "Première occurrence : Ligne {1}<br>"
                    "Doublon : Ligne {2}<br><br>"
                    "Chaque facture ne peut être ajoutée qu'une seule fois."
                ).format(
                    row.numero_facture or row.facture_fournisseur,
                    factures_vues[row.facture_fournisseur],
                    row.idx
                ))
            
            factures_vues[row.facture_fournisseur] = row.idx
    
    def _validate_factures_status(self):
        """Vérifie que toutes les factures sont En Attente."""
        if self.type_depense != "Fournisseur":
            return
        
        if not self.factures:
            return
        
        for row in self.factures:
            if not row.facture_fournisseur:
                continue
            
            status = frappe.db.get_value(
                "Facture Fournisseur", 
                row.facture_fournisseur, 
                "status"
            )
            
            if status != "En Attente":
                frappe.throw(_(
                    "❌ La facture <b>{0}</b> a le statut <b>{1}</b>.<br><br>"
                    "Seules les factures avec le statut <b>En Attente</b> "
                    "peuvent être ajoutées à une Dépense Interne."
                ).format(row.numero_facture or row.facture_fournisseur, status))


    def _validate_type_compte_beneficiaires(self):
        """
        Vérifie que tous les bénéficiaires d'une mission
        ont le même type de compte (Banque OU CCP).
        """
        if self.type_depense == "Frais Mission" and self.beneficiaires:
            types_compte = set([b.type_compte for b in self.beneficiaires if b.type_compte])
            
            if len(types_compte) > 1:
                frappe.throw(_(
                    "Tous les bénéficiaires doivent avoir le même type de compte "
                    "(Banque ou CCP)."
                ))
            
            # Définir le type de compte de la mission
            if types_compte:
                self.type_compte_mission = list(types_compte)[0]

    def _validate_factures_fournisseur(self):
        """Vérifie que les factures sélectionnées sont valides."""
        if self.type_depense != "Fournisseur" or not self.fournisseur:
            return
        
        if not self.factures:
            frappe.throw(_("Veuillez ajouter au moins une facture pour ce type de dépense."))
        
        # Vérifier que les factures cochées appartiennent bien au fournisseur
        for facture in self.factures:
            if facture.inclure and facture.facture_fournisseur:
                # Vérifier que la facture existe et appartient au bon fournisseur
                facture_doc = frappe.get_doc("Facture Fournisseur", facture.facture_fournisseur)
                if facture_doc.fournisseur != self.fournisseur:
                    frappe.throw(_(
                        "La facture {0} n'appartient pas au fournisseur {1}."
                    ).format(facture.numero_facture, self.fournisseur))
                
                # Vérifier que la facture est toujours "En Attente"
                if facture_doc.status != "En Attente":
                    frappe.throw(_(
                        "La facture {0} n'est plus en statut 'En Attente'. "
                        "Statut actuel : {1}"
                    ).format(facture.numero_facture, facture_doc.status))
                
                # Vérifier que la facture est liée à un Bon Commande avec le bon article
                if facture_doc.type_reference == "Bon Commande" and facture_doc.bon_commande:
                    bc_doc = frappe.get_doc("Bon Commande", facture_doc.bon_commande)
                    if bc_doc.article != self.article:
                        frappe.throw(_(
                            "La facture {0} est liée au Bon Commande {1} qui n'a pas "
                            "le bon article ({2}). Article attendu : {3}."
                        ).format(
                            facture.numero_facture,
                            facture_doc.bon_commande,
                            bc_doc.article or "Non défini",
                            self.article or "Non défini"
                        ))
        
        # Vérifier qu'au moins une facture est cochée
        factures_cochees = [f for f in self.factures if f.inclure]
        if not factures_cochees:
            frappe.throw(_("Veuillez cocher au moins une facture à inclure."))

    def _validate_factures_coherence(self):
        """Vérifie la cohérence des factures sélectionnées."""
        if self.type_depense != "Fournisseur":
            return
        
        if not self.factures:
            return
        
        for row in self.factures:
            if not row.facture_fournisseur:
                continue
            
            fact = frappe.get_doc("Facture Fournisseur", row.facture_fournisseur)
            
            # Vérifier fournisseur
            if fact.fournisseur != self.fournisseur:
                frappe.throw(_(
                    "La facture {0} appartient au fournisseur {1}, "
                    "pas au fournisseur {2} de cette dépense."
                ).format(fact.numero_facture, fact.fournisseur, self.fournisseur))
            
            # Vérifier que la facture vient d'un BC du bon article
            if fact.bon_commande:
                bc = frappe.get_doc("Bon Commande", fact.bon_commande)
                if bc.article != self.article:
                    frappe.throw(_(
                        "La facture {0} provient du BC pour l'article {1}, "
                        "pas pour l'article {2}."
                    ).format(fact.numero_facture, bc.article, self.article))
            elif fact.convention:
                conv = frappe.get_doc("Convention", fact.convention)
                if conv.article != self.article:
                    frappe.throw(_(
                        "La facture {0} provient de la Convention pour l'article {1}, "
                        "pas pour l'article {2}."
                    ).format(fact.numero_facture, conv.article, self.article))
            # else:
            #     frappe.throw(_(
            #         "La facture {0} n'est liée ni à un Bon de Commande "
            #         "ni à une Convention."
            #     ).format(fact.numero_facture))

    
    def _validate_beneficiaires_frais_mission(self):
        """
        Validation stricte : quand un Frais Mission est sélectionné,
        les bénéficiaires doivent correspondre exactement à ceux du Frais Mission.
        """
        if self.type_depense != "Frais Mission" or not self.frais_mission:
            return
        
        # Récupérer les bénéficiaires du Frais Mission
        fm = frappe.get_doc("Frais Mission", self.frais_mission)
        fm_beneficiaires = fm.table_beneficiaires
        
        # Vérifier le nombre de bénéficiaires
        if len(self.beneficiaires) != len(fm_beneficiaires):
            frappe.throw(_(
                "⚠️ <b>Incohérence des bénéficiaires</b><br><br>"
                "Le Frais Mission contient {0} bénéficiaire(s) "
                "mais la dépense en contient {1}.<br><br>"
                "Les bénéficiaires doivent correspondre exactement "
                "à ceux du Frais Mission sélectionné."
            ).format(len(fm_beneficiaires), len(self.beneficiaires)))
        
        # Vérifier que chaque bénéficiaire du FM est présent
        fm_personnes = {b.personne for b in fm_beneficiaires}
        depense_personnes = {b.personne for b in self.beneficiaires}
        
        if fm_personnes != depense_personnes:
            manquants = fm_personnes - depense_personnes
            supplementaires = depense_personnes - fm_personnes
            
            message = "⚠️ <b>Bénéficiaires différents du Frais Mission</b><br><br>"
            
            if manquants:
                message += f"Manquant(s) : {', '.join(manquants)}<br>"
            if supplementaires:
                message += f"Supplémentaire(s) : {', '.join(supplementaires)}<br>"
            
            message += "<br>Les bénéficiaires doivent correspondre exactement à ceux du Frais Mission."
            
            frappe.throw(_(message))
        
        # Vérifier que les montants correspondent
        fm_montants = {b.personne: flt(b.montant_mission) for b in fm_beneficiaires}
        depense_montants = {b.personne: flt(b.montant) for b in self.beneficiaires}
        
        for personne, montant_fm in fm_montants.items():
            if personne in depense_montants:
                montant_depense = depense_montants[personne]
                if montant_depense != montant_fm:
                    frappe.throw(_(
                        "⚠️ <b>Montant différent pour {0}</b><br><br>"
                        "Montant Frais Mission : {1} DA<br>"
                        "Montant Dépense : {2} DA<br><br>"
                        "Les montants doivent être identiques."
                    ).format(personne, montant_fm, montant_depense))

    def _calculate_montant_total(self):
        """Calcule le montant total selon le type de dépense."""
        
        if self.type_depense == "Fournisseur":
            total = sum(flt(f.montant) for f in self.factures)
            self.montant_total = total
        
        elif self.type_depense == "Frais Mission":
            total = sum(flt(b.montant) for b in self.beneficiaires)
            self.montant_total = total
        
        # La validation du solde est déjà faite dans validate()
        # Plus besoin d'appeler _check_solde_disponible() ici
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
            
    def _check_solde_disponible(self):
        """Vérifie que le montant de la dépense ne dépasse pas le solde disponible."""
        if not self.provision_reference:
            return
        
        # Calculer le solde disponible (provision - dépenses déjà engagées)
        solde = self._get_solde_disponible()
        
        if flt(self.montant_total) > flt(solde):
            frappe.throw(_(
                "⚠️ Solde insuffisant !<br><br>"
                "<b>Solde disponible :</b> {0} DA<br>"
                "<b>Montant de cette dépense :</b> {1} DA<br>"
                "<b>Dépassement :</b> {2} DA<br><br>"
                "Veuillez réduire le montant de la dépense ou créer une nouvelle provision."
            ).format(
                flt(solde),
                flt(self.montant_total),
                flt(self.montant_total) - flt(solde)
            ))

    def _get_solde_disponible(self):
        """Retourne le solde disponible de la provision."""
        prov = frappe.get_doc("Fiche Budgetaire", self.provision_reference)
        montant_provision = flt(prov.montant_operation)
        
        depenses_engagees = frappe.get_all(
            "Depense Interne",
            filters={
                "provision_reference": self.provision_reference,
                "name": ["!=", self.name or ""],
                "status": ["!=", "Rejeté Définitif"]
            },
            fields=["montant_total"]
        )
        
        total_depenses = sum(flt(d["montant_total"]) for d in depenses_engagees)
        
        return montant_provision - total_depenses        
        
    def _set_objet_auto(self):
        """Génère automatiquement l'objet si vide."""
        if self.objet_depense:
            return
        
        if self.type_depense == "Fournisseur":
            if self.fournisseur and self.factures:
                raison = frappe.db.get_value("Fournisseur", self.fournisseur, "raison_sociale")
                nb_factures = len(self.factures)
                
                # Créer les lignes pour chaque facture
                lignes_factures = []
                for facture in self.factures:
                    if facture.numero_facture and facture.date_facture:
                        # Convertir la date en objet date si c'est une chaîne
                        date_obj = facture.date_facture
                        if isinstance(date_obj, str):
                            
                            date_obj = getdate(date_obj)
                        
                        lignes_factures.append(
                            f"facture N° {facture.numero_facture} du {date_obj.strftime('%d/%m/%Y')}"
                        )
                
                # Combiner le tout dans l'objet
                if lignes_factures:
                    lignes_texte = "\n".join(lignes_factures)
                    self.objet_depense = (
                        f"Paiement {nb_factures} facture(s) - {raison}\n{lignes_texte}"
                    )
                else:
                    self.objet_depense = (
                        f"Paiement {nb_factures} facture(s) - {raison}"
                    )
        
        elif self.type_depense == "Frais Mission":
            if self.frais_mission:
                fm = frappe.get_doc("Frais Mission", self.frais_mission)
                self.objet_depense = f"Frais de mission - {fm.objet_mission}"

    def _get_derniere_fiche_avant_provision(self):
        """
        Retourne le nouveau_solde de la fiche budgétaire (Économie ou Dépense)
        qui précède la provision S1 référencée.
        """
        if not self.provision_reference:
            return 0

        provision = frappe.get_doc("Fiche Budgetaire", self.provision_reference)
        if provision.type_fiche != "Provision" or provision.semestre != "S1":
            frappe.throw(_("La provision de référence doit être une Provision S1."))

        filters = {
            "article": self.article,
            "budget_global": self.budget_global,
            "numero_fiche": ["<", provision.numero_fiche],
            "type_fiche": ["in", ["Économie", "Dépense"]],
            #"status": ["in", ["Brouillon", "Signé Doyen", "Envoyé CF", "Visé CF"]],
            "docstatus": ["!=", 2]
        }
        # Si l'article a des partitions, il faut peut-être filtrer par partition
        art = frappe.get_doc("Budget Article", self.article)
        if art.has_partition and self.code_partition:
            filters["code_partition"] = self.code_partition

        result = frappe.get_all(
            "Fiche Budgetaire",
            filters=filters,
            fields=["nouveau_solde"],
            order_by="numero_fiche desc",
            limit=1
        )
        return flt(result[0]["nouveau_solde"]) if result else 0
    
    def _calculer_ancien_solde(self):
        """
        Calcule l'ancien solde selon la règle :
        - Si c'est la première dépense de la provision : ancien_solde = crédit total avant provision
        - Sinon : ancien_solde = nouveau_solde de la dépense précédente (même provision)
        """
        if not self.provision_reference:
            self.ancien_solde = 0
            return

        # Trouver la dernière dépense interne antérieure liée à la même provision
        filters = {
            #"provision_reference": self.provision_reference,
            "article": self.article,
            "name": ["!=", self.name or ""],
            "numero_interne": ["<", self.numero_interne],
            "status": ["in", ["Brouillon", "Validé", "Envoyé Comptable","Mandaté", "Régularisé", "Réglé"]],
            #"docstatus": ["!=", 2]
        }
        dernieres_depenses = frappe.get_all(
            "Depense Interne",
            filters=filters,
            fields=["nouveau_solde"],
            order_by="numero_interne desc",
            limit=1
        )

        if dernieres_depenses:
            # Il y a déjà une dépense antérieure
            self.ancien_solde = flt(dernieres_depenses[0]["nouveau_solde"])
        else:
            # Première dépense de cette provision : on prend le crédit total avant provision
            self.ancien_solde = self._get_derniere_fiche_avant_provision()
@frappe.whitelist()
def get_provisions_visees(article, budget_global, semestre):
    """
    Retourne les provisions visées CF pour un article et semestre.
    Appelé depuis le JS pour faciliter la sélection.
    """
    provisions = frappe.get_all(
        "Fiche Budgetaire",
        filters={
            "article": article,
            "budget_global": budget_global,
            "type_fiche": "Provision",
            "semestre": semestre,
            #"status": "Visé CF"
            "docstatus": ["!=", 2]
        },
        #fields=["name", "numero_fiche", "montant_operation", "date_visa_cf"],
        fields=["name", "numero_fiche", "montant_operation","status"],
        order_by="numero_fiche desc"
    )
    
    # Enrichir avec solde disponible
    for prov in provisions:
        depenses_engagees = frappe.get_all(
            "Depense Interne",
            filters={
                "provision_reference": prov.name,
                "status": ["!=", "Rejeté Définitif"],
                #"docstatus": ["!=", 2]
            },
            fields=["montant_total"]
        )
        
        total_depenses = sum(flt(d["montant_total"]) for d in depenses_engagees)
        prov["solde_disponible"] = flt(prov["montant_operation"]) - total_depenses
        
    return provisions


@frappe.whitelist()
def get_solde_provision(provision_reference):
    """Retourne le solde disponible d'une provision."""
    prov = frappe.get_doc("Fiche Budgetaire", provision_reference)
    
    # Calculer les dépenses engagées avec le Frappe ORM
    depenses_engagees = frappe.db.get_value("Depense Interne", {
        "provision_reference": provision_reference,
        "status": ["!=", "Rejeté Définitif"]
    }, "SUM(montant_total)") or 0
    
    solde = flt(prov.montant_operation) - flt(depenses_engagees)
    
    return {
        "montant_provision": flt(prov.montant_operation),
        "depenses_engagees": flt(depenses_engagees),
        "solde_disponible": solde,
        "numero_fiche": prov.numero_fiche
    }
@frappe.whitelist()
def get_factures_fournisseur(fournisseur, article):
    """
    Retourne les factures 'En Attente' d'un fournisseur pour création de dépense.
    Filtres supplémentaires : type_reference = 'Bon Commande' et article correspondant.
    """
    factures = []
    
    # Étape 1: Toutes les factures du fournisseur
    toutes_factures = frappe.get_all(
        "Facture Fournisseur",
        filters={"fournisseur": fournisseur},
        fields=["name", "numero_facture", "fournisseur", "article", "status", "date_facture", "montant_ttc"]
    )
    
    # Étape 2: Filtrer par statut "En Attente"
    #factures_en_attente = [f for f in toutes_factures if f.status == "En Attente"]
    factures = [f for f in toutes_factures if f.status == "En Attente"]
    
    # Étape 3: Filtrer par type_reference "Bon Commande"
    #factures_bc = [f for f in factures_en_attente if f.type_reference == "Bon Commande"]
    
    # Étape 4: Filtrer par article si spécifié
    # if article and factures_bc:
    #     factures_finales = []
        
    #     for f in factures_bc:
    #         if f.bon_commande:
    #             try:
    #                 bc_article = frappe.db.get_value("Bon Commande", f.bon_commande, "article")
                    
    #                 if bc_article == article:
    #                     factures_finales.append(f)
    #             except Exception as e:
    #                 pass  # Ignorer les erreurs de BC
        
    #     factures = factures_finales
    # else:
    #     factures = factures_bc
    
    # Calculer le total
    total = sum(flt(f.montant_ttc) for f in factures)
    
    # Récupérer infos fournisseur
    try:
        fournisseur_info = frappe.get_doc("Fournisseur", fournisseur)
        raison_sociale = fournisseur_info.raison_sociale
    except:
        raison_sociale = fournisseur
    
    return {
        "factures": factures,
        "total_factures": total,
        "raison_sociale": raison_sociale,
        "article_filtre": article,
        "type_reference_filtre": "Bon Commande"
    }


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_frais_mission_aposteriori(doctype, txt, searchfield, start, page_len, filters):
    """
    Query pour filtrer les Frais Mission dont l'article est A posteriori.
    Utilisée dans Dépense Interne.
    Filtre sur : budget_global, article, et frais de mission non utilisés dans les dépenses internes existantes.
    """
    article = filters.get('article')
    budget_global = filters.get('budget_global')
    
    if not article:
        return []
    
    # Vérifier que l'article est A posteriori
    type_article = frappe.db.get_value("Budget Article", article, "type")
    if type_article != "A posteriori":
        return []
    
    # Récupérer les frais de mission déjà utilisés dans les dépenses internes
    frais_mission_utilises = frappe.get_all(
        "Depense Interne",
        filters={"frais_mission": ["!=", ""]},
        pluck="frais_mission"
    )
    
    # Construire les filtres pour la requête
    query_filters = {"article": article}
    
    # if annee_budgetaire and frappe.db.has_column("Frais Mission", "annee_budgetaire"):
    #     query_filters["annee_budgetaire"] = annee_budgetaire
    
    if frais_mission_utilises:
        query_filters["name"] = ["not in", frais_mission_utilises]
    
    if txt:
        # Pour le OR sur objet_mission, on utilise une approche différente
        resultats_nom = frappe.get_all(
            "Frais Mission",
            filters={**query_filters, "name": ["like", f"%{txt}%"]},
            fields=["name", "objet_mission"],
            order_by="creation desc",
            start=start,
            page_length=page_len
        )
        
        # Recherche sur objet_mission
        filters_objet = query_filters.copy()
        filters_objet["objet_mission"] = ["like", f"%{txt}%"]
        
        resultats_objet = frappe.get_all(
            "Frais Mission",
            filters=filters_objet,
            fields=["name", "objet_mission"],
            order_by="creation desc",
            start=start,
            page_length=page_len
        )
        
        # Combiner et dédupliquer les résultats
        resultats_dict = {r["name"]: r for r in resultats_nom + resultats_objet}
        resultats = list(resultats_dict.values())[:page_len]
        
        # Convertir en tuples pour le format attendu par Frappe
        return [(r["name"], r["objet_mission"]) for r in resultats]
    else:
        resultats = frappe.get_all(
            "Frais Mission",
            filters=query_filters,
            fields=["name", "objet_mission"],
            order_by="creation desc",
            start=start,
            page_length=page_len
        )
        # Convertir en tuples pour le format attendu par Frappe
        return [(r["name"], r["objet_mission"]) for r in resultats]

# @frappe.whitelist()
# @frappe.validate_and_sanitize_search_inputs
# def get_factures_fournisseur_pour_depense(doctype, txt, searchfield, start, page_len, filters):
#     """
#     Query pour filtrer les factures :
#     1. Du fournisseur sélectionné
#     2. Via BC ayant le même article (A Posteriori)
#     3. Status = En Attente uniquement
#     4. Non déjà ajoutées dans la dépense actuelle
#     """
#     fournisseur = filters.get('fournisseur')
#     article = filters.get('article')
#     depense_interne = filters.get('depense_interne')  # Pour exclure les déjà ajoutées
    
#     if not fournisseur or not article:
#         return []
    
#     # Récupérer les BC de cet article + fournisseur
#     bons_commande = frappe.get_all(
#         "Bon Commande",
#         filters={
#             "article": article,
#             "prestataire": fournisseur
#         },
#         pluck="name"
#     )
    
#     if not bons_commande:
#         return []
    
#     # Construire les conditions
#     conditions = [
#         "fournisseur = %(fournisseur)s",
#         "status = 'En Attente'",  # ✅ Uniquement En Attente
#         "bon_commande IN %(bons_commande)s"
#     ]
    
#     # ✅ Exclure les factures déjà dans une autre Dépense Interne non annulée
#     conditions.append("""
#         name NOT IN (
#             SELECT facture_fournisseur 
#             FROM `tabFacture Depense Element` 
#             WHERE parent IN (
#                 SELECT name FROM `tabDepense Interne` 
#                 WHERE docstatus != 2
#             )
#         )
#     """)
    
#     if txt:
#         conditions.append("(numero_facture LIKE %(txt)s OR name LIKE %(txt)s)")
    
#     where_clause = " AND ".join(conditions)
    
#     return frappe.db.sql(f"""
#         SELECT 
#             name,
#             numero_facture,
#             date_facture,
#             montant_ttc,
#             bon_commande
#         FROM `tabFacture Fournisseur`
#         WHERE {where_clause}
#         ORDER BY date_facture DESC
#         LIMIT {start}, {page_len}
#     """, {
#         'fournisseur': fournisseur,
#         'bons_commande': bons_commande,
#         'txt': f'%{txt}%'
#     })


@frappe.whitelist()
def get_factures_disponibles(fournisseur, article, budget_global, depense_actuelle=None):
    """
    Retourne toutes les factures disponibles pour sélection multiple dans une dépense interne.
    Filtres : fournisseur, article, année budgétaire, statut 'En Attente',
    et exclut les factures déjà utilisées dans d'autres dépenses internes.
    """
    if not fournisseur or not article or not annee_budgetaire:
        return []

    # 1. Récupérer les factures déjà utilisées dans d'autres dépenses internes
    used_filters = {
        "parenttype": "Depense Interne",
        #"status": ["!=", "Rejeté Définitif"],  # exclure uniquement les dépenses rejetées définitivement
    }
    if depense_actuelle:
        used_filters["parent"] = ["!=", depense_actuelle]  # exclure la dépense courante

    used_factures = frappe.get_all(
        "Facture Depense Element",
        filters=used_filters,
        pluck="facture_fournisseur"
    )

    # 2. Récupérer les factures disponibles avec une seule requête optimisée
    filters_list = [
        ["fournisseur", "=", fournisseur],
        ["article", "=", article],
        ["budget_global", "=", budget_global],
        ["status", "=", "En Attente"],
    ]
    if used_factures:
        filters_list.append(["name", "not in", used_factures])

    factures = frappe.db.get_list(
        "Facture Fournisseur",
        filters=filters_list,
        fields=["name", "numero_facture", "date_facture", "montant_ttc", "bon_commande"],
        order_by="date_facture desc",
        #as_dict=True
    )

    return factures
###################

@frappe.whitelist()
def get_ancien_solde_article(article, budget_global, provision_reference, semestre, depense_actuelle=None):
    """
    Calcule l'ancien solde pour une dépense interne :
    - Première dépense de la provision : ancien_solde = credit_ancien_solde de la provision S1
    - Dépense suivante : ancien_solde = nouveau_solde de la dépense interne précédente (même provision)
    """
    if not provision_reference:
        return 0

    # Récupérer la provision S1 (doit être une provision et de semestre S1)
    prov = frappe.get_doc("Fiche Budgetaire", provision_reference)
    if prov.type_fiche != "Provision" or prov.semestre != "S1":
        frappe.throw(_("La provision de référence doit être une Provision S1."))

    # Trouver la dépense précédente ( numéro inférieur, non rejetée définitivement)
    filters = {
        #"provision_reference": provision_reference,
        "article": article,
        "budget_global": budget_global,
        "status": ["!=", "Rejeté Définitif"]  # Exclure uniquement les dépenses rejetées définitivement
    }

    # Si une dépense actuelle existe et a un nom valide (pas un nom temporaire), on l'exclut
    current_numero = None
    if depense_actuelle and not depense_actuelle.startswith('new-'):
        try:
            current = frappe.get_doc("Depense Interne", depense_actuelle)
            current_numero = current.numero_interne
            filters["numero_interne"] = ["<", current_numero]
        except frappe.DoesNotExistError:
            # Le document peut ne pas exister (nouvelle fiche) ou être en cours de création
            pass

    # Récupérer la dernière dépense correspondant aux filtres
    dernieres = frappe.get_all(
        "Depense Interne",
        filters=filters,
        fields=["nouveau_solde"],
        order_by="numero_interne desc",
        limit=1
    )

    if dernieres:
        # Il existe une dépense antérieure
        return flt(dernieres[0]["nouveau_solde"])
    else:
        # Première dépense pour cette provision
        return flt(prov.credit_ancien_solde)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_factures_fournisseur_pour_depense(doctype, txt, searchfield, start, page_len, filters):
    """
    Retourne les factures disponibles pour une dépense interne :
    - Même fournisseur, même article, même année budgétaire
    - Statut 'En Attente'
    - Non déjà utilisées dans une autre dépense interne (non annulée)
    - Supporte la recherche textuelle et la pagination
    """
    fournisseur = filters.get('fournisseur')
    article = filters.get('article')
    budget_global= filters.get('budget_global')
    depense_interne = filters.get('depense_interne')  # nom de la dépense courante (optionnel)

    if not fournisseur or not article or not budget_global:
        return []

    # 1. Récupérer les factures déjà utilisées dans d'autres dépenses internes
    used_filters = [
        ["parenttype", "=", "Depense Interne"]
    ]
    if depense_interne:
        used_filters.append(["parent", "!=", depense_interne])  # exclure la dépense courante

    used_factures = frappe.get_all(
        "Facture Depense Element",
        filters=used_filters,
        pluck="facture_fournisseur"
    )

    # 2. Construire les filtres pour les factures
    filters_list = [
        ["fournisseur", "=", fournisseur],
        ["article", "=", article],
        ["budget_global", "=", budget_global],
        ["status", "=", "En Attente"],
    ]
    if used_factures:
        filters_list.append(["name", "not in", used_factures])
    if txt:
        filters_list.append(["numero_facture", "like", f"%{txt}%"])

    # 3. Récupérer les factures avec pagination
    factures = frappe.db.get_list(
        "Facture Fournisseur",
        filters=filters_list,
        fields=["name", "numero_facture", "date_facture", "montant_ttc", "bon_commande"],
        order_by="date_facture desc",
        limit_start=start,
        limit_page_length=page_len,
        as_list=True  # retourne une liste de listes pour le Link Field
    )

    return factures