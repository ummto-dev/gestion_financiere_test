import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, add_days, add_months, getdate
from num2words import num2words
from datetime import timedelta


class BonCommande(Document):

    def before_save(self):
        """Calculs avant sauvegarde."""
        #self._set_numero_bon_commande()
        #self._validate_article_apriori()

    def validate(self):
        """Validations lors de la sauvegarde."""
        #self._validate_article_apriori()
        self._validate_coherence_imputation()
        self._calculate_totaux()
        self._convert_montant_lettres()
        self._calculate_date_limite_livraison()
        self._update_suivi_execution()

    # def _validate_article_apriori(self):
    #     """Vérifie que l'article est de type A Priori."""
    #     if not self.article:
    #         return
        
    #     type_article = frappe.db.get_value("Article", self.article, "type")
        
    #     if type_article != "A priori":
    #         frappe.throw(_(
    #             "Les Bons de Commande sont réservés aux articles À Priori. "
    #             "L'article sélectionné est de type {0}."
    #         ).format(type_article))

    def _validate_coherence_imputation(self):
        """Vérifie la cohérence de l'imputation budgétaire."""
        if not all([self.titre, self.chapitre, self.article]):
            return
        
        # Vérifier que le chapitre appartient bien au titre
        chapitre_data = frappe.db.get_value("Budget Chapitre", self.chapitre, ["titre", "annee_budgetaire"])
        if not chapitre_data:
            frappe.throw(_("Le chapitre sélectionné n'existe pas."))
        
        titre_chapitre, annee_chapitre = chapitre_data
        if titre_chapitre != self.titre:
            frappe.throw(_(
                "Incohérence : Le chapitre {0} n'appartient pas au titre {1}."
            ).format(self.chapitre, self.titre))
        
        if annee_chapitre != self.annee_budgetaire:
            frappe.throw(_(
                "Incohérence : Le chapitre n'appartient pas à l'année budgétaire {0}."
            ).format(self.annee_budgetaire))
        
        # Vérifier que l'article appartient bien au chapitre
        article_data = frappe.db.get_value("Budget Article", self.article, ["budget_chapitre", "annee_budgetaire"])
        if not article_data:
            frappe.throw(_("L'article sélectionné n'existe pas."))
        
        chapitre_article, annee_article = article_data
        if chapitre_article != self.chapitre:
            frappe.throw(_(
                "Incohérence : L'article {0} n'appartient pas au chapitre {1}."
            ).format(self.article, self.chapitre))
        
        
        if annee_article != self.annee_budgetaire:
            frappe.throw(_(
                "Incohérence : L'article n'appartient pas à l'année budgétaire {0}."
            ).format(self.annee_budgetaire))

    def _calculate_totaux(self):
        """Calcule les totaux HT, TVA, TTC depuis les éléments."""
        if not self.bc_element:
            self.total_ht = 0
            self.montant_tva = 0
            self.total_ttc = 0
            return
        
        # Calculer total HT
        self.total_ht = sum(flt(item.montant) for item in self.bc_element)
        
        # Calculer TVA
        if self.taux_tva:
            self.montant_tva = flt(self.total_ht) * flt(self.taux_tva) / 100
        else:
            self.montant_tva = 0
        
        # Calculer TTC
        self.total_ttc = flt(self.total_ht) + flt(self.montant_tva)

    def _convert_montant_lettres(self):
        """Convertit le montant TTC en lettres."""
        if not self.total_ttc:
            self.montant_en_lettres = ""
            return
        
        try:
            entier = int(self.total_ttc)
            centimes = int((self.total_ttc - entier) * 100)
            
            lettres_entier = num2words(entier, lang='fr').upper()
            
            if centimes > 0:
                lettres_centimes = num2words(centimes, lang='fr').upper()
                self.montant_en_lettres = (
                    f"{lettres_entier} DINARS ET {lettres_centimes} CENTIMES"
                )
            else:
                self.montant_en_lettres = f"{lettres_entier} DINARS"
                
        except Exception as e:
            frappe.log_error(f"Erreur conversion montant en lettres: {str(e)}")
            self.montant_en_lettres = ""

    def _calculate_date_limite_livraison(self):
        """Calcule la date limite de livraison."""
        if not self.date_commande or not self.delai_livraison:
            return
        
        date_cmd = getdate(self.date_commande)
        
        if self.unite_delai == "Jours":
            self.date_limite_livraison = add_days(date_cmd, self.delai_livraison)
        elif self.unite_delai == "Semaines":
            self.date_limite_livraison = add_days(date_cmd, self.delai_livraison * 7)
        elif self.unite_delai == "Mois":
            self.date_limite_livraison = add_months(date_cmd, self.delai_livraison)

    def _update_suivi_execution(self):
        """Met à jour le suivi d'exécution (factures reçues)."""
        if not self.name:
            return
        
        # Calculer le total des factures
        total_factures = frappe.db.sql("""
            SELECT COALESCE(SUM(montant_ttc), 0)
            FROM `tabFacture Fournisseur`
            WHERE bon_commande = %s
        """, self.name)[0][0]
        
        self.montant_factures = flt(total_factures)
        self.reste_a_facturer = flt(self.total_ttc) - flt(total_factures)
        
        # Vérifier si soldé
        if flt(self.reste_a_facturer) <= 0.01 and self.status == "En Exécution":
            self.status = "Soldé"


@frappe.whitelist()
def creer_fiche_depense_bc(bon_commande):
    """
    Crée automatiquement une Fiche Dépense pour le BC.
    Appelé depuis le JS après Validation bon commade.
    """
    bc = frappe.get_doc("Bon Commande", bon_commande)
    
    # Vérifier statut
    if bc.status != "Validé":
        frappe.throw(_("Le Bon de Commande doit être Validé"))
    
    # Vérifier qu'une fiche n'existe pas déjà
    if bc.fiche_depense:
        frappe.throw(_("Une Fiche Dépense existe déjà pour ce BC."))
    
    # Créer la Fiche Dépense
    fiche = frappe.get_doc({
        "doctype": "Fiche Budgetaire",
        "annee_budgetaire": bc.annee_budgetaire,
        "titre": bc.titre,
        "chapitre": bc.chapitre,
        "article": bc.article,
        "partition": bc.partition,
        "type_fiche": "Dépense",
        "type_engagement_apriori": "Bon Commande",
        "bon_commande": bc.name,
        "fournisseur": bc.prestataire,
        "montant_operation": bc.total_ttc,
        "nature_engagement": f"Bon de Commande N° {bc.numero_bon_commande} - {bc.objet_detaille[:100]}",
        "status": "Brouillon",
    })
    
    fiche.insert(ignore_permissions=True)
    
    # Mettre à jour le BC
    bc.fiche_depense = fiche.name
    #bc.status = "Envoyé CF"
    bc.save(ignore_permissions=True)
    
    return {"fiche_depense": fiche.name}


@frappe.whitelist()
def get_bc_pour_fiche_depense(annee_budgetaire, article=None):
    """Retourne les BC validés sans fiche dépense."""
    filters = {
        "annee_budgetaire": annee_budgetaire,
        "status": "Validé",
        "fiche_depense": ["in", ["", None]]
    }
    
    if article:
        filters["article"] = article
    
    bcs = frappe.get_all(
        "Bon Commande",
        filters=filters,
        fields=[
            "name", "numero_bon_commande", "date_commande",
            "prestataire", "objet_detaille", "total_ttc", "article"
        ],
        order_by="date_commande desc"
    )
    
    return bcs
