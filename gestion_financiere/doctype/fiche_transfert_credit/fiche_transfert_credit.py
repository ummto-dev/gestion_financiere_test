import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class FicheTransfertCredit(Document):

    def before_save(self):
        """Appelé avant chaque sauvegarde - calculer les champs readonly."""
        self._set_readonly_fields()

    def validate(self):
        """Validations métier - appelé automatiquement lors du save."""
        self._validate_articles_differents()  # Vérifier EN PREMIER
        self._validate_meme_chapitre()
        self._validate_solde_disponible()
        self._validate_provision_aposteriori()

    def _set_readonly_fields(self):
        """Calcule et remplit les champs readonly."""
        # Type article source
        if self.article_source:
            self.type_article_source = frappe.db.get_value(
                "Budget Article", self.article_source, "type"
            )
        
        # Type article destination
        if self.article_destination:
            self.type_article_destination = frappe.db.get_value(
                "Budget Article", self.article_destination, "type"
            )
        
        # Solde disponible source
        if self.article_source and self.budget_global:
            self.solde_disponible_source = self._get_solde_article_source()

    #commenter la condition visé cf pour permettre la création des fiches budgétaires même si le statut n'est pas visé cf
    # def on_submit(self):
    #     """Crée automatiquement les 2 fiches budgétaires après visa CF."""
    #     if self.status != "Visé CF":
    #         frappe.throw(_(
    #             "La Fiche Transfert doit être visée par le CF avant soumission."
    #         ))

    def on_cancel(self):
        """Annule les fiches budgétaires liées."""
        if self.fiche_source:
            frappe.delete_doc("Fiche Budgetaire", self.fiche_source, force=1)
        if self.fiche_destination:
            frappe.delete_doc("Fiche Budgetaire", self.fiche_destination, force=1)

    def _validate_meme_chapitre(self):
        """Vérifie que les deux articles sont du même chapitre."""
        chap_src = frappe.db.get_value(
            "Budget Article", self.article_source, "budget_chapitre"
        )
        chap_dest = frappe.db.get_value(
            "Budget Article", self.article_destination, "budget_chapitre"
        )
        
        if chap_src != chap_dest:
            frappe.throw(_(
                "Le transfert de crédit est uniquement autorisé entre articles "
                "du même chapitre. Article source : Chapitre {0} | "
                "Article destination : Chapitre {1}."
            ).format(chap_src, chap_dest))
        
        #self.chapitre = chap_src

    def _validate_articles_differents(self):
        """Vérifie que les articles source et destination sont différents."""
        if not self.article_source or not self.article_destination:
            return  # Pas encore rempli
            
        if self.article_source == self.article_destination:
            frappe.throw(_(
                "❌ <b>ERREUR : Articles Identiques</b><br><br>"
                "L'article source et l'article destination doivent être <b>différents</b>.<br><br>"
                "Article sélectionné : <b>{0}</b><br><br>"
                "Veuillez choisir un article destination différent."
            ).format(self.article_source))

    def _validate_solde_disponible(self):
        """Vérifie que l'article source a un solde suffisant."""
        solde = self._get_solde_article_source()
        self.solde_disponible_source = solde
        
        if flt(self.montant_transfere) > flt(solde):
            frappe.throw(_(
                "Crédit insuffisant sur l'article source. "
                "Solde disponible : {0} DA | Montant à transférer : {1} DA."
            ).format(solde, self.montant_transfere))

    def _validate_provision_aposteriori(self):
        """Vérifie que les articles source et destination ne sont pas visés en A posteriori."""
        for role, article in [("source", self.article_source), ("destination", self.article_destination)]:
            if article:
                type_art = frappe.db.get_value("Budget Article", article, "type")
                if type_art == "A posteriori":
                    prov_visee = frappe.db.exists(
                        "Fiche Budgetaire",
                        {
                            "article": article,
                            "type_fiche": "Provision",
                            "semestre": "S1",
                            #"status": "Visé CF",
                            "docstatus": ["!=", 2],
                        }
                    )
                    if prov_visee:
                        frappe.throw(_(
                            "Transfert impossible : la Provision S1 exite "
                            "pour l'article {0} (À Posteriori)."
                        ).format(article))
        self.provision_1_visee = False  # optionnel

    def _get_solde_article_source(self):
        """Retourne le solde disponible de l'article source."""
        result = frappe.get_all(
            "Fiche Budgetaire",
            filters={
                "article": self.article_source,
                "budget_global": self.budget_global,
                #"status": "Visé CF",
                "docstatus": ["!=", 2],
            },
            fields=["nouveau_solde"],
            order_by="numero_fiche desc",
            limit=1,
        )
        return flt(result[0]["nouveau_solde"]) if result else 0

    def _creer_fiches_budgetaires(self):
        """
        Crée les 2 fiches budgétaires EN BROUILLON (pas visées).
        Les fiches suivront le workflow normal : Brouillon → Signé Doyen → Envoyé CF → Visé CF
        """
        titre = frappe.db.get_value("Budget Chapitre", self.chapitre, "titre")
        # 1. Fiche SOURCE (Dépense - Crédit Donné)
        fiche_src = frappe.get_doc({
            "doctype": "Fiche Budgetaire",
            "budget_global": self.budget_global,
            "titre": titre,
            "chapitre": self.chapitre,
            "article": self.article_source,
            "partition": self.partition_source,
            "type_fiche": "Dépense",
            "is_transfert": 1,
            "sens_transfert": "Crédit Donné",
            "article_contrepartie": self.article_destination,
            "fiche_transfert": self.name,
            "montant_operation": self.montant_transfere,
            "nature_engagement": f"Transfert de crédit vers {self.article_destination}",
            "ref_engagement_obs":f"TRANSFERT DE CRÉDIT DONNÉ – ARTICLE DESTINATION : {self.article_destination}",
            "status": "Brouillon",
        })
        fiche_src.insert(ignore_permissions=True)
        self.fiche_source = fiche_src.name

        # 2. Fiche DESTINATION (Économie - Crédit Reçu) EN BROUILLION
        fiche_dest = frappe.get_doc({
            "doctype": "Fiche Budgetaire",
            "budget_global": self.budget_global,
            "titre": titre,
            "chapitre": self.chapitre,
            "article": self.article_destination,
            "partition": self.partition_destination,
            "type_fiche": "Économie",
            "is_transfert": 1,
            "sens_transfert": "Crédit Reçu",
            "article_contrepartie": self.article_source,
            "fiche_transfert": self.name,
            "montant_operation": self.montant_transfere,
            "nature_engagement": f"Transfert de crédit depuis {self.article_source}",
            "ref_engagement_obs":f"TRANSFERT DE CRÉDIT RECU – ARTICLE SOURCE : {self.article_source}",
            "status": "Brouillon",
        })
        fiche_dest.insert(ignore_permissions=True)
        self.fiche_destination = fiche_dest.name

        self.save()


@frappe.whitelist()
def get_solde_article_pour_transfert(article, budget_global):
    """API pour récupérer le solde d'un article depuis le JS."""
    result = frappe.get_all(
        "Fiche Budgetaire",
        filters={
            "article": article,
            "budget_global": budget_global,
            #"status": "Visé CF",
            "docstatus": ["!=", 2],
        },
        fields=["nouveau_solde", "numero_fiche"],
        order_by="numero_fiche desc",
        limit=1,
    )
    return {
        "solde": flt(result[0]["nouveau_solde"]) if result else 0,
        "derniere_fiche": result[0]["numero_fiche"] if result else 0,
    }

@frappe.whitelist()
def creer_fiches_transfert(fiche_transfert):
    """
    API appelée depuis le JS pour créer les fiches budgétaires.
    Les fiches sont créées EN BROUILLON et suivront le workflow normal.
    """
    doc = frappe.get_doc("Fiche Transfert Credit", fiche_transfert)
    
    # Vérifications
    if doc.status != "Visé CF":
        frappe.throw(_("La Fiche Transfert doit être visée par le CF."))
    
    if doc.fiche_source or doc.fiche_destination:
        frappe.throw(_("Les fiches budgétaires ont déjà été créées."))
    
    # Créer les fiches
    doc._creer_fiches_budgetaires()
    
    return {
        "fiche_source": doc.fiche_source,
        "fiche_destination": doc.fiche_destination
    }
