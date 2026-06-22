import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class FactureFournisseur(Document):

    def validate(self):
        """Validations lors de la sauvegarde."""
        self._validate_reference()
        self._calculate_tva()
        self._validate_montant_reference()

    def _validate_reference(self):
        """Vérifie qu'une référence (BC ou Convention) est sélectionnée."""
        # if not self.type_reference:
        #     frappe.throw(_("Veuillez sélectionner le type de référence (Bon Commande ou Convention)."))
    
        if self.type_reference == "Bon Commande" and not self.bon_commande:
            frappe.throw(_("Veuillez sélectionner un Bon de Commande."))
        
        if self.type_reference == "Convention" and not self.convention:
            frappe.throw(_("Veuillez sélectionner une Convention."))
        
        # Vérifier cohérence fournisseur
        if self.type_reference == "Bon Commande":
            bc = frappe.get_doc("Bon Commande", self.bon_commande)
            if bc.prestataire != self.fournisseur:
                frappe.throw(_(
                    "Le fournisseur de la facture ({0}) ne correspond pas "
                    "au prestataire du Bon de Commande ({1})."
                ).format(self.fournisseur, bc.prestataire))
        
        if self.type_reference == "Convention":
            conv = frappe.get_doc("Convention", self.convention)
            if conv.fournisseur != self.fournisseur:
                frappe.throw(_(
                    "Le fournisseur de la facture ({0}) ne correspond pas "
                    "au fournisseur de la Convention ({1})."
                ).format(self.fournisseur, conv.fournisseur))

    def _calculate_tva(self):
        """Calcule le montant TVA et TTC."""
        if self.montant_ht and self.taux_tva:
            self.montant_tva = flt(self.montant_ht) * flt(self.taux_tva) / 100
            self.montant_ttc = flt(self.montant_ht) + flt(self.montant_tva)
        elif self.montant_ht and not self.taux_tva:
            self.montant_tva = 0
            self.montant_ttc = flt(self.montant_ht)

    def _validate_montant_reference(self):
        """
        Vérifie que le total des factures ne dépasse pas le montant
        du Bon de Commande ou de la Convention.
        """
        if self.type_reference == "Bon Commande" and self.bon_commande:
            bc = frappe.get_doc("Bon Commande", self.bon_commande)
            montant_ref = flt(bc.total_ttc)
            
            total_autres = frappe.get_all(
                "Facture Fournisseur",
                filters={
                    "bon_commande": self.bon_commande,
                    "name": ["!=", self.name or ""]
                },
                fields=["montant_ttc"]
            )
            total = sum(flt(f["montant_ttc"]) for f in total_autres)  
            total_avec_cette_facture = flt(total) + flt(self.montant_ttc)
            
            if total_avec_cette_facture > montant_ref:
                frappe.throw(_(
                    "⚠️ DÉPASSEMENT DU MONTANT DU BON DE COMMANDE !<br><br>"
                    "<b>Montant BC :</b> {0:,.2f} DA<br>"
                    "<b>Factures déjà enregistrées :</b> {1:,.2f} DA<br>"
                    "<b>Cette facture :</b> {2:,.2f} DA<br>"
                    "<b>Total :</b> {3:,.2f} DA<br><br>"
                    "<b style='color:red'>Dépassement :</b> {4:,.2f} DA"
                ).format(
                    montant_ref,
                    flt(total),
                    flt(self.montant_ttc),
                    total_avec_cette_facture,
                    total_avec_cette_facture - montant_ref
                ))
        
        elif self.type_reference == "Convention" and self.convention:
            conv = frappe.get_doc("Convention", self.convention)
            montant_ref = flt(conv.montant_convention)
            
            # Calculer le total des autres factures de la même Convention
            # total_autres = frappe.db.sql("""
            #     SELECT COALESCE(SUM(montant_ttc), 0)
            #     FROM `tabFacture Fournisseur`
            #     WHERE convention = %s
            #       AND name != %s
            # """, (self.convention, self.name or ""))[0][0]
            # 
            # total_avec_cette_facture = flt(total_autres) + flt(self.montant_ttc)
            total_autres = frappe.get_all(
                "Facture Fournisseur",
                filters={
                    "convention": self.convention,
                    "name": ["!=", self.name or ""]
                },
                fields=["montant_ttc"]
            )
            total = sum(flt(f["montant_ttc"]) for f in total_autres)  
            total_avec_cette_facture = flt(total) + flt(self.montant_ttc)

            
            if total_avec_cette_facture > montant_ref:
                frappe.throw(_(
                    "⚠️ DÉPASSEMENT DU MONTANT DE LA CONVENTION !<br><br>"
                    "<b>Montant Convention :</b> {0:,.2f} DA<br>"
                    "<b>Factures déjà enregistrées :</b> {1:,.2f} DA<br>"
                    "<b>Cette facture :</b> {2:,.2f} DA<br>"
                    "<b>Total :</b> {3:,.2f} DA<br><br>"
                    "<b style='color:red'>Dépassement :</b> {4:,.2f} DA"
                ).format(
                    montant_ref,
                    flt(total),
                    flt(self.montant_ttc),
                    total_avec_cette_facture,
                    total_avec_cette_facture - montant_ref
                ))


@frappe.whitelist()
def get_factures_bon_commande(bon_commande):
    """Retourne les factures d'un Bon de Commande."""
    factures = frappe.get_all(
        "Facture Fournisseur",
        filters={"bon_commande": bon_commande},
        fields=[
            "name", "numero_facture", "date_facture", "montant_ttc",
            "status", "mandat_paiement", "numero_mandat"
        ],
        order_by="date_facture asc"
    )
    
    # Calculer le total
    total = sum(flt(f.montant_ttc) for f in factures)
    
    # Récupérer montant BC
    bc = frappe.get_doc("Bon Commande", bon_commande)
    
    return {
        "factures": factures,
        "total_factures": total,
        "montant_bc": bc.total_ttc,
        "reste": flt(bc.total_ttc) - total
    }


@frappe.whitelist()
def get_factures_convention(convention):
    """Retourne les factures d'une Convention."""
    factures = frappe.get_all(
        "Facture Fournisseur",
        filters={"convention": convention},
        fields=[
            "name", "numero_facture", "date_facture", "montant_ttc",
            "status", "mandat_paiement", "numero_mandat"
        ],
        order_by="date_facture asc"
    )
    
    # Calculer le total
    total = sum(flt(f.montant_ttc) for f in factures)
    
    # Récupérer montant Convention
    conv = frappe.get_doc("Convention", convention)
    
    return {
        "factures": factures,
        "total_factures": total,
        "montant_convention": conv.montant_convention,
        "reste": flt(conv.montant_convention) - total
    }


@frappe.whitelist()
def get_factures_non_mandatees(fournisseur=None, bon_commande=None, convention=None):
    """Retourne les factures non mandatées pour création de mandat."""
    filters = {
        "status": "En Attente",
        "mandat_paiement": ["in", ["", None]]
    }
    
    if fournisseur:
        filters["fournisseur"] = fournisseur
    
    if bon_commande:
        filters["bon_commande"] = bon_commande
    
    if convention:
        filters["convention"] = convention
    
    factures = frappe.get_all(
        "Facture Fournisseur",
        filters=filters,
        fields=[
            "name", "numero_facture", "date_facture", "fournisseur",
            "montant_ttc", "bon_commande", "convention"
        ],
        order_by="date_facture asc"
    )
    
    return factures


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_bon_commande_pour_facture(doctype, txt, searchfield, start, page_len, filters):
    """
    Retourne les BC disponibles pour une facture :
    - Même fournisseur (prestataire)
    - Optionnel : même article
    """
    fournisseur = filters.get('fournisseur')
    article = filters.get('article')
    
    if not fournisseur:
        return []
    
    # ✅ Construction des filtres avec Frappe ORM
    filter_dict = {
        'prestataire': fournisseur,
        'status': ['not in', ['Rejeté Définitif', 'Soldé']]
    }
    
    # Ajouter filtre article si fourni
    if article:
        filter_dict['article'] = article
    
    # Filtre de recherche textuelle
    or_filters = []
    if txt:
        or_filters = [
            ['numero_bon_commande', 'like', f'%{txt}%'],
            ['name', 'like', f'%{txt}%']
        ]
    
    # ✅ Récupération avec frappe.get_all()
    bons_commande = frappe.get_all(
        'Bon Commande',
        filters=filter_dict,
        or_filters=or_filters if or_filters else None,
        fields=[
            'name',
            'numero_bon_commande',
            'date_commande',
            'total_ttc',
            'article',
            'objet_detaille'
        ],
        order_by='date_commande desc',
        start=start,
        page_length=page_len
    )
    
    # ✅ Retourner au format attendu par le Link Field
    return [[bc.name, bc.numero_bon_commande, bc.date_commande, bc.total_ttc, bc.article] 
            for bc in bons_commande]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_convention_pour_facture(doctype, txt, searchfield, start, page_len, filters):
    """
    Retourne les Conventions disponibles pour une facture :
    - Même fournisseur
    - Optionnel : même article
    """
    fournisseur = filters.get('fournisseur')
    article = filters.get('article')
    
    if not fournisseur:
        return []
    
    # ✅ Construction des filtres avec Frappe ORM
    filter_dict = {
        'fournisseur': fournisseur,
        'status': ['not in', ['Rejeté Définitif', 'Soldé']]
    }
    
    # Ajouter filtre article si fourni
    if article:
        filter_dict['article'] = article
    
    # Filtre de recherche textuelle
    or_filters = []
    if txt:
        or_filters = [
            ['numero_convention', 'like', f'%{txt}%'],
            ['name', 'like', f'%{txt}%']
        ]
    
    # ✅ Récupération avec frappe.get_all()
    conventions = frappe.get_all(
        'Convention',
        filters=filter_dict,
        or_filters=or_filters if or_filters else None,
        fields=[
            'name',
            'numero_convention',
            'date_convention',
            'montant_convention',
            'article',
            'objet_convention'
        ],
        order_by='date_convention desc',
        start=start,
        page_length=page_len
    )
    
    # ✅ Retourner au format attendu par le Link Field
    return [[conv.name, conv.numero_convention, conv.date_convention, 
             conv.montant_convention, conv.article] 
            for conv in conventions]


@frappe.whitelist()
def get_info_bc_pour_facture(bon_commande):
    """
    Retourne les infos d'un BC pour pré-remplir la facture.
    
    Utilise Frappe ORM au lieu de SQL brut.
    """
    if not bon_commande:
        return {}
    
    # ✅ Récupérer le BC avec frappe.get_doc()
    bc = frappe.get_doc("Bon Commande", bon_commande)
    
    # ✅ Calculer le total des factures existantes avec frappe.get_all()
    factures_existantes = frappe.get_all(
        "Facture Fournisseur",
        filters={"bon_commande": bon_commande},
        fields=["montant_ttc"]
    )
    
    total_facture = sum(flt(f.montant_ttc) for f in factures_existantes)
    reste = flt(bc.total_ttc) - total_facture
    
    return {
        "fournisseur": bc.prestataire,
        "budget_global": bc.budget_global,
        "article": bc.article,
        "montant_bc": bc.total_ttc,
        "total_facture": total_facture,
        "reste": reste,
        "taux_tva": bc.taux_tva if hasattr(bc, 'taux_tva') else 0
    }


@frappe.whitelist()
def get_info_convention_pour_facture(convention):
    """
    Retourne les infos d'une Convention pour pré-remplir la facture.
    
    Utilise Frappe ORM au lieu de SQL brut.
    """
    if not convention:
        return {}
    
    # ✅ Récupérer la Convention avec frappe.get_doc()
    conv = frappe.get_doc("Convention", convention)
    
    # ✅ Calculer le total des factures existantes avec frappe.get_all()
    factures_existantes = frappe.get_all(
        "Facture Fournisseur",
        filters={"convention": convention},
        fields=["montant_ttc"]
    )
    
    total_facture = sum(flt(f.montant_ttc) for f in factures_existantes)
    reste = flt(conv.montant_convention) - total_facture
    
    return {
        "fournisseur": conv.fournisseur,
        "budget_global": conv.budget_global,
        "article": conv.article,
        "montant_convention": conv.montant_convention,
        "total_facture": total_facture,
        "reste": reste
    }


# ═══════════════════════════════════════════════════════════
#   VERSION ALTERNATIVE AVEC DB.GET_LIST (PLUS SIMPLE)
# ═══════════════════════════════════════════════════════════

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_bon_commande_pour_facture_v2(doctype, txt, searchfield, start, page_len, filters):
    """
    Version alternative avec frappe.db.get_list()
    Plus simple et plus concise.
    """
    fournisseur = filters.get('fournisseur')
    article = filters.get('article')
    
    if not fournisseur:
        return []
    
    # ✅ Filtres de base
    filter_dict = {
        'prestataire': fournisseur,
        'status': ['not in', ['Rejeté Définitif', 'Soldé']]
    }
    
    if article:
        filter_dict['article'] = article
    
    # ✅ frappe.db.get_list() - Syntaxe la plus simple
    bons_commande = frappe.db.get_list(
        'Bon Commande',
        filters=filter_dict,
        fields=['name', 'numero_bon_commande', 'date_commande', 'total_ttc', 'article'],
        order_by='date_commande desc',
        limit_start=start,
        limit_page_length=page_len,
        as_list=True  # ✅ Retourne directement des listes
    )
    
    # Filtre texte manuel si nécessaire
    if txt:
        bons_commande = [bc for bc in bons_commande 
                         if txt.lower() in str(bc[1]).lower() or txt.lower() in str(bc[0]).lower()]
    
    return bons_commande


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_bons_commande_filtres(doctype, txt, searchfield, start, page_len, filters):
    """
    Retourne les BC disponibles pour une facture avec filtre intelligent :
    - Articles : status different de 'Rejeté Définitif' et 'Soldé'
    - Même fournisseur, même année budgétaire et même article (si fourni)
    """
    prestataire = filters.get('prestataire')
    budget_global = filters.get('budget_global')
    article = filters.get('article')
    
    if not prestataire or not budget_global:
        return []
    
    # Si pas d'article spécifié, retourner tous les BC possibles
    if not article:
        bons_commande = frappe.db.sql("""
            SELECT bc.name, bc.numero_bon_commande, bc.date_commande, bc.total_ttc, 
                   bc.status, art.type as type_article
            FROM `tabBon Commande` bc
            LEFT JOIN `tabBudgetArticle` art ON bc.article = art.name
            WHERE bc.prestataire = %s
              AND bc.budget_global = %s
              AND bc.status NOT IN ('Rejeté Définitif', 'Soldé')
            ORDER BY bc.date_commande DESC
            LIMIT %s OFFSET %s
        """, (prestataire, budget_global, page_len, start), as_dict=True)
        
        # Préparer les résultats
        resultats = []
        for bc in bons_commande:
            # Appliquer le filtre textuel si nécessaire
            if txt and txt.lower() not in str(bc.numero_bon_commande).lower() and txt.lower() not in str(bc.name).lower():
                continue
            
            resultats.append([
                bc.name,
                bc.numero_bon_commande,
                bc.date_commande,
                bc.total_ttc,
                f"{bc.type_article or 'N/A'} - {bc.status}"
            ])
        
        return resultats
    
    # Récupérer le type d'article
    type_article = frappe.db.get_value('Budget Article', article, 'type')
    if not type_article:
        return []
    
    # Déterminer le statut attendu selon le type d'article
    statut_attendu = 'Visé CF' if type_article == 'A priori' else 'Validé'
    
    # Récupérer les BC avec tous les filtres
    bons_commande = frappe.db.sql("""
        SELECT bc.name, bc.numero_bon_commande, bc.date_commande, bc.total_ttc, 
               bc.status
        FROM `tabBon Commande` bc
        WHERE bc.prestataire = %s
          AND bc.budget_global = %s
          AND bc.article = %s
          AND bc.status = %s
        ORDER BY bc.date_commande DESC
        LIMIT %s OFFSET %s
    """, (prestataire, budget_global, article, statut_attendu, page_len, start), as_dict=True)
    
    # Préparer les résultats
    resultats = []
    for bc in bons_commande:
        # Appliquer le filtre textuel si nécessaire
        if txt and txt.lower() not in str(bc.numero_bon_commande).lower() and txt.lower() not in str(bc.name).lower():
            continue
        
        resultats.append([
            bc.name,
            bc.numero_bon_commande,
            bc.date_commande,
            bc.total_ttc,
            f"{type_article} - {bc.status}"
        ])
    
    return resultats
