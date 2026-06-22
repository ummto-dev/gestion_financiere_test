import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from num2words import num2words


class Convention(Document):

    def autoname(self):
        """Génère le numéro de convention."""
        self._set_numero_convention()
        self.name = f"CONV-{self.budget_global}-{str(self.numero_convention).zfill(5)}"

    def before_insert(self):
        """Appelé avant insertion."""
        if not hasattr(self, 'numero_convention') or not self.numero_convention:
            self._set_numero_convention()

    def validate(self):
        """Validations lors de la sauvegarde."""
        self._validate_article_apriori()
        self._convert_montant_lettres()
        self._update_suivi_execution()

    def _set_numero_convention(self):
        """Génère un numéro séquentiel par exercice budgetaire (budget global)."""
        dernier = frappe.db.sql("""
            SELECT MAX(CAST(SUBSTRING_INDEX(name, '-', -1) AS UNSIGNED))
            FROM `tabConvention`
            WHERE budget_global = %s
        """, self.budget_global)[0][0]
        
        self.numero_convention = (dernier or 0) + 1

        #Récupérer toutes les conventions pour cette année
        conventions = frappe.get_all("Convention", 
            filters={"budget_global": self.budget_global},
            fields=["name"]
        )
        
        max_numero = 0
        for conv in conventions:
            # Extraire le numéro après le dernier tiret
            if "-" in conv.name:
                try:
                    numero = int(conv.name.split("-")[-1])
                    max_numero = max(max_numero, numero)
                except ValueError:
                    continue
        
        self.numero_convention = max_numero + 1
        
    def _validate_article_apriori(self):
        """Vérifie que l'article est de type A priori."""
        if not self.article:
            return
        
        type_article = frappe.db.get_value("Budget Article", self.article, "type")
        
        if type_article != "A priori":
            frappe.throw(_(
                "Les Conventions sont réservées aux articles À Priori. "
                "L'article sélectionné est de type {0}."
            ).format(type_article))
    
    def _convert_montant_lettres(self):
        """Convertit le montant en lettres."""
        if not self.montant_convention:
            self.montant_lettres = ""
            return
        
        try:
            # Partie entière
            entier = int(self.montant_convention)
            # Centimes
            centimes = int((self.montant_convention - entier) * 100)
            
            lettres_entier = num2words(entier, lang='fr').upper()
            
            if centimes > 0:
                lettres_centimes = num2words(centimes, lang='fr').upper()
                self.montant_lettres = (
                    f"{lettres_entier} DINARS ET {lettres_centimes} CENTIMES"
                )
            else:
                self.montant_lettres = f"{lettres_entier} DINARS"
                
        except Exception as e:
            frappe.log_error(f"Erreur conversion montant en lettres: {str(e)}")
            self.montant_lettres = ""

    def _update_suivi_execution(self):
        """Met à jour les champs de suivi d'exécution."""
        
        # Pour Convention Prestation : récupérer depuis Situation Paiement
        #if self.type_convention == "Prestation" and self.situation_paiement:
        if self.situation_paiement:
            try:
                sit = frappe.get_doc("Situation Paiement", self.situation_paiement)
                self.montant_paye = sit.montant_paye
                self.reste_a_payer = sit.reste_a_payer
                
                # NE PAS changer automatiquement le statut ici
                # Le statut "Soldé" sera mis manuellement ou via la Situation
            except:
                # Si la situation n'existe pas encore, initialiser à 0
                self.montant_paye = 0
                self.reste_a_payer = self.montant_convention

@frappe.whitelist()
def creer_fiche_depense_convention(convention):
    """
    Crée automatiquement une Fiche Dépense pour la convention.
    Appelé depuis le JS après visa CF.
    """
    conv = frappe.get_doc("Convention", convention)
    
    # Vérifier statut
    if conv.status != "Envoyé CF":
        frappe.throw(_("La Convention doit être au status Envoyé CF."))
    
    # Vérifier qu'une fiche n'existe pas déjà
    if conv.fiche_depense:
        frappe.throw(_("Une Fiche Dépense existe déjà pour cette convention."))
    chapitre = frappe.db.get_value("Budgte Article", conv.article, "chapitre")
    titre = frappe.db.get_value("Chapitre", chapitre, "titre")
    # Créer la Fiche Dépense
    fiche = frappe.get_doc({
        "doctype": "Fiche Budgetaire",
        "annee_budgetaire": conv.annee_budgetaire,
        "titre": titre,
        "chapitre": chapitre,
        "article": conv.article,
        "partition": conv.partition,
        "type_fiche": "Dépense",
        "type_engagement_apriori": "Convention",
        "convention": conv.name,
        "fournisseur": conv.fournisseur,
        "raison_sociale": conv.raison_sociale,
        "montant_operation": conv.montant_convention,
        "conv-date": conv.date_convention,
        "conv_numero": conv.numero_convention,
        "conv_montant": conv.montant_convention,
        "nature_engagement": f"Convention N° {conv.numero_convention} - {conv.objet_convention}",
        "status": "Brouillon",
    })
    
    fiche.insert(ignore_permissions=True)
    
    # Mettre à jour la convention
    conv.fiche_depense = fiche.name
    #conv.status = "En Exécution"
    conv.save(ignore_permissions=True)
    
    # Si Convention Prestation : créer aussi la Situation Paiement
    # if conv.type_convention == "Prestation":
    #     sit = frappe.get_doc({
    #         "doctype": "Situation Paiement",
    #         "convention": conv.name,
    #         "fiche_depense": fiche.name,
    #         "annee_budgetaire": conv.annee_budgetaire,
    #         "article": conv.article,
    #     })
    #     sit.insert(ignore_permissions=True)
        
    #     conv.situation_paiement = sit.name
    #     conv.save(ignore_permissions=True)
    
    return {
        "fiche_depense": fiche.name,
        #"situation_paiement": conv.situation_paiement if conv.type_convention == "Prestation" else None
        "situation_paiement": conv.situation_paiement 
    }


@frappe.whitelist()
def get_conventions_pour_fiche_depense(budget_global, article=None):
    """Retourne les conventions visées CF sans fiche dépense."""
    filters = {
        "budget_global": budget_global,
        "status": "Envoyé CF",
        "fiche_depense": ["in", ["", None]]
    }
    
    if article:
        filters["article"] = article
    
    conventions = frappe.get_all(
        "Convention",
        filters=filters,
        fields=[
            "name", "numero_convention", "date_convention",
            "type_convention", "fournisseur", "objet_convention",
            "montant_convention", "article"
        ],
        order_by="date_convention desc"
    )
    
    return conventions
