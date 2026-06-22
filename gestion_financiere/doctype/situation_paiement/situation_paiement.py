import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

class SituationPaiement(Document):

    def validate(self):
        self._load_from_convention()
        # self._verifier_fiche_depense()
        self._recalcul_soldes()
        self._check_if_solde()

    def after_insert(self):
        """Après création — lier la Situation Paiement à la Convention et à la Fiche Budgetaire."""
        self._lier_situation_aux_documents()
    
    def on_update(self):
        """Après sauvegarde - recalculer les soldes."""
        self._recalcul_soldes()
        self._check_if_solde()

    def on_trash(self):
        """Avant suppression — effacer le lien dans Convention et Fiche Budgetaire."""
        self._delier_situation_des_documents()

    def _load_from_convention(self):
        """Charge les infos depuis la Convention."""
        if not self.convention:
            return
        
        conv = frappe.get_doc("Convention", self.convention)
        
        # Vérifier que c'est une Convention Prestation
        # if conv.type_convention != "Prestation":
        #     frappe.throw(_(
        #         "La Situation de Paiement est réservée aux Conventions de Prestation. "
        #         "Pour les Conventions d'Acquisition, le paiement se fait en une seule fois."
        #     ))
        
        # Charger les infos
        self.budget_global = conv.budget_global
        self.numero_convention = conv.numero_convention
        self.date_convention = conv.date_convention
        self.fournisseur = conv.fournisseur
        self.objet_convention = conv.objet_convention
        self.montant_total_convention = conv.montant_convention
        
        # Raison sociale
        if conv.fournisseur:
            self.raison_sociale = frappe.db.get_value(
                "Fournisseur", conv.fournisseur, "raison_sociale"
            )
        self.fiche_depense = conv.fiche_depense
        # Récupérer l'article depuis la fiche dépense liée
        #if self.fiche_depense:
        #    fiche = frappe.get_doc("Fiche Budgetaire", self.fiche_depense)
        self.article = conv.article
        self.annee_budgetaire = conv.annee_budgetaire

        
        # Initialiser montant_paye et reste_a_payer si nouveau document
        if not self.paiements:
            self.montant_paye = 0
            self.reste_a_payer = self.montant_total_convention

    # def _verifier_fiche_depense(self):
    #     """
    #     Bloque la sauvegarde si la Convention n'a pas de Fiche Dépense.
    #     Une Situation de Paiement ne peut exister sans Fiche Dépense associée.
    #     """
    #     if not self.convention:
    #         return

        # if not self.fiche_depense:
        #     frappe.throw(
        #         _(
        #             "Impossible de créer une Situation de Paiement : "
        #             "la Convention <b>{0}</b> n'a pas de Fiche Dépense associée. "
        #             "Veuillez d'abord lier une Fiche Budgetaire à cette Convention."
        #         ).format(self.convention),
        #         title=_("Fiche Dépense manquante")
        #     )

    def _lier_situation_aux_documents(self):
        """
        Après création de la Situation Paiement :
          - Met à jour le champ 'situation_paiement' dans Convention
          - Met à jour le champ 'situation_paiement' dans Fiche Budgetaire
        """
        if self.convention:
            frappe.db.set_value(
                "Convention", self.convention,
                "situation_paiement", self.name,
                update_modified=False
            )

        if self.fiche_depense:
            frappe.db.set_value(
                "Fiche Budgetaire", self.fiche_depense,
                "situation_paiement", self.name,
                update_modified=False
            )

    def _delier_situation_des_documents(self):
        """
        Avant suppression de la Situation Paiement :
          - Efface le champ 'situation_paiement' dans Convention
          - Efface le champ 'situation_paiement' dans Fiche Budgetaire
        """
        if self.convention:
            frappe.db.set_value(
                "Convention", self.convention,
                "situation_paiement", None,
                update_modified=False
            )

        if self.fiche_depense:
            frappe.db.set_value(
                "Fiche Budgetaire", self.fiche_depense,
                "situation_paiement", None,
                update_modified=False
            )

    def _recalcul_soldes(self):
        """
        Recalcule les soldes de la situation :
        - Montant payé = somme des paiements
        - Reste à payer = total - payé
        - Pour chaque ligne : ancien solde, reste solde
        """
        # S'assurer que montant_total_convention est défini
        if not self.montant_total_convention:
            if self.convention:
                conv = frappe.get_doc("Convention", self.convention)
                self.montant_total_convention = conv.montant_convention
        
        # Cas sans paiements
        if not self.paiements:
            self.montant_paye = 0
            self.reste_a_payer = flt(self.montant_total_convention)
            return
        
        # Trier les paiements par ligne
        self.paiements = sorted(self.paiements, key=lambda x: x.ligne_numero or 0)
        
        # Calculer pour chaque ligne
        for i, paiement in enumerate(self.paiements):
            if i == 0:
                # Première ligne : ancien solde = montant total
                paiement.ancien_solde = flt(self.montant_total_convention)
            else:
                # Lignes suivantes : ancien solde = reste solde précédent
                paiement.ancien_solde = self.paiements[i-1].reste_solde
            
            # Reste solde = ancien - montant opération
            paiement.reste_solde = flt(paiement.ancien_solde) - flt(paiement.montant_operation)
        
        # Calculer montant payé et reste à payer
        self.montant_paye = sum(flt(p.montant_operation) for p in self.paiements)
        self.reste_a_payer = flt(self.montant_total_convention) - flt(self.montant_paye)
        if self.convention:
            frappe.db.set_value("Convention", self.convention, {
                "montant_paye"  : self.montant_paye,
                "reste_a_payer" : self.reste_a_payer,
            }, update_modified=False)
    
    def _check_if_solde(self):
        """Vérifie si la situation est soldée et met à jour la Convention."""
        # Vérifier si soldé (reste <= 0.01 DA pour gérer les arrondis)
        if flt(self.reste_a_payer) <= 1:
            self.status = "Soldé"
            if not self.date_solde:
                self.date_solde = frappe.utils.today()
            
            # Mettre à jour la Convention
            if self.convention:
                conv = frappe.get_doc("Convention", self.convention)
                if conv.status != "Soldé":
                    conv.status = "Soldé"
                    conv.save(ignore_permissions=True)
        else:
            self.status = "En Cours"
            self.date_solde = None
            
            # S'assurer que la Convention est "En Exécution"
            if self.convention:
                conv = frappe.get_doc("Convention", self.convention)
                if conv.status != "En Exécution":
                    conv.status = "En Exécution"
                    conv.save(ignore_permissions=True)

@frappe.whitelist()
def get_conventions_sans_situation(doctype, txt, searchfield, start, page_len, filters):
    """
    Query function pour le champ 'convention' lors de la création
    d'une Situation Paiement depuis ce doctype.

    Exclut :
      - les conventions ayant déjà une Situation Paiement
      - les conventions avec statut 'Rejeté Définitif'
    """
    # Conventions déjà liées à une Situation Paiement
    situations = frappe.get_all(
        "Situation Paiement",
        filters=[["convention", "is", "set"]],
        fields=["convention"],
        ignore_permissions=True,
    )
    used = {s.convention for s in situations if s.convention}

    #orm_filters = [["status", "!=", "Rejeté Définitif"]]
    orm_filters = [
        ["status",        "!=",  "Rejeté Définitif"],
        ["fiche_depense", "is",  "set"],          # Convention doit avoir une Fiche Dépense
    ]
    if used:
        orm_filters.append(["name", "not in", list(used)])

    or_filters = []
    if txt:
        or_filters = [
            ["name",              "like", f"%{txt}%"],
            ["numero_convention", "like", f"%{txt}%"],
            ["objet_convention",  "like", f"%{txt}%"],
        ]

    conventions = frappe.get_all(
        "Convention",
        filters=orm_filters,
        or_filters=or_filters or None,
        fields=["name", "numero_convention", "objet_convention"],
        order_by="numero_convention asc",
        start=int(start),
        page_length=int(page_len),
        ignore_permissions=True,
    )

    return [[c.name, c.numero_convention, c.objet_convention or ""] for c in conventions]


# @frappe.whitelist()
# def get_conventions_disponibles(doctype, txt, searchfield, start, page_len, filters):
    # """ 
    # Retourne les conventions disponibles pour créer une situation de paiement.

    # """
    # # Récupérer toutes les conventions avec statut Visé CF
    # conventions = frappe.get_all('Convention',
        # filters={
            # 'status': ['!=', 'Rejeté Définitif']
        # },
        # fields=['name', 'numero_convention', 'fournisseur', 'objet_convention'],
        # order_by='numero_convention'
    # )
    
    # if not conventions:
        # return []
    
    # # Récupérer les conventions qui ont déjà une situation de paiement
    # situations_paiement = frappe.get_all('Situation Paiement',
        # filters={
            # #'convention': ['is not', None]
            # 'convention': ['!=', '']
        # },
        # fields=['convention']
    # )
    
    # # Extraire les noms des conventions déjà utilisées
    # used_conventions = {sit.convention for sit in situations_paiement}
    
    # # Filtrer les conventions disponibles
    # conventions_disponibles = []
    # for conv in conventions:
        # if conv.name not in used_conventions:
            # # Récupérer le nom du fournisseur pour l'affichage
            # fournisseur_name = frappe.db.get_value('Fournisseur', conv.fournisseur, 'raison_sociale') or conv.fournisseur
            
            # conventions_disponibles.append({
                # 'value': conv.name,
                # 'label': f"{conv.numero_convention} - {fournisseur_name}",
                # 'description': conv.objet_convention[:100] + "..." if conv.objet_convention and len(conv.objet_convention) > 100 else conv.objet_convention
            # })
    
    # return conventions_disponibles

@frappe.whitelist()
def get_paiements_situation(situation_paiement):
    """Retourne les paiements d'une situation."""
    sit = frappe.get_doc("Situation Paiement", situation_paiement)
    
    return {
        "paiements": [
            {
                "ligne_numero": p.ligne_numero,
                "mandat_paiement": p.mandat_paiement,
                "numero_mandat": p.numero_mandat,
                "date_mandat": p.date_mandat,
                "ancien_solde": p.ancien_solde,
                "montant_operation": p.montant_operation,
                "reste_solde": p.reste_solde,
                "factures_payees": p.factures_payees
            }
            for p in sit.paiements
        ],
        "montant_total": sit.montant_total_convention,
        "montant_paye": sit.montant_paye,
        "reste_a_payer": sit.reste_a_payer,
        "status": sit.status
    }
