import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate, flt, cint

# ─────────────────────────────────────────────
#  Jours fériés algériens (fixes)
# ─────────────────────────────────────────────
FERIES_FIXES = [
    (1,  1),   # Nouvel An
    (5,  1),   # Fête du Travail
    (7,  5),   # Fête de l'Indépendance
    (11, 1),   # Fête de la Révolution
]

# ─────────────────────────────────────────────
#  Matrice des combinaisons valides
#
#  type_fiche   | type_article  | is_transfert | sens_transfert | Condition
#  -------------|---------------|--------------|----------------|------------------------------
#  Économie     | A priori      | 0            | —              | Fiche initiale 0001
#  Économie     | A posteriori  | 0            | —              | Fiche initiale 0001
#  Économie     | A priori      | 1            | Crédit Reçu    | Transfert reçu (numéro N)
#  Économie     | A posteriori  | 1            | Crédit Reçu    | Transfert reçu AVANT Prov S1
#  Provision    | A posteriori  | 0            | —              | S1=0002 ou S2=N
#  Dépense      | A priori      | 0            | —              | Dépense normale BC/Conv/Frais
#  Dépense      | A priori      | 1            | Crédit Donné   | Transfert donné (numéro N)
#  Dépense      | A posteriori  | 1            | Crédit Donné   | Transfert donné AVANT Prov S1
#  Régularisation| A posteriori | 0            | —              | Régularisation normale
# ─────────────────────────────────────────────


class FicheBudgetaire(Document):

    # ══════════════════════════════════════════
    #  HOOKS FRAPPE
    # ══════════════════════════════════════════

    def autoname(self):
        """
        Génère le name du document : FB-{article}-{numero_fiche}
        Exemple : FB-2024-FSBSA-titre2-22-11-05-0001
         Pour les amendements, on ne génère pas le nom ici, il sera fait dans before_insert.
        """
        # Ne générer un nom que pour les nouveaux documents
        #if not self.amended_from:
        if not self.name or self.name.startswith('new-'):
            if not self.numero_fiche:
                self._set_numero_fiche()
                
            # Construire le name
            self.name = f"FB-{self.article}-{str(self.numero_fiche).zfill(4)}"
    
    def before_insert(self):
        #self._set_numero_fiche()
        if self.amended_from:
            # Amendement : conserver le numero_fiche de la fiche originale
            orig_numero = frappe.db.get_value(
                "Fiche Budgetaire", self.amended_from, "numero_fiche"
            )
            if orig_numero:
                self.numero_fiche = orig_numero
            # Le name a déjà été fixé par autoname() — ne pas le recalculer
        else:
            # Nouvelle fiche : calculer le numéro séquentiel
            self._set_numero_fiche()
        self._set_readonly_fields()

    def validate(self):
        self._bloquer_si_definitif()
        self._set_readonly_fields()
        self._validate_type_coherence()
        self._validate_sequence()
        self._validate_prerequis()
        self._validate_transfert()        
        if self.type_article == "A posteriori":
            # Articles À Posteriori
            if self.type_fiche in ("Économie", "Dépense"):
			    # Economie et Depense transfert
                self._compute_ancien_solde()
                #self._validate_montants_aposteriori()
                self._validate_montants()
                self._compute_nouveau_solde()
            else:
                # Provision et Régularisation : Structure 2 lignes
                self._compute_soldes_aposteriori()
                self._validate_montants_aposteriori()
                
        else:
            # Articles A Priori 
            self._compute_ancien_solde()
            self._validate_montants()
            self._compute_nouveau_solde()  
        self._set_ref_engagement_obs()
        self._set_nature_engagement()
        self._validate_regularisation_table()
        self._validate_frais_mission() 
         # ── Dépense A priori Convention → créer Situation Paiement ──
        
        # if self.amended_from:
        #     original = frappe.get_doc("Fiche Budgetaire", self.amended_from)
        #     if original.docstatus == 2 and self.status == "Rejeté":
        #         frappe.throw(_("Impossible d'amender une fiche rejetée définitivement.")) 

    # def before_submit(self):
    #     """Empêche la soumission si la fiche n'est pas au statut 'Visé CF'."""
    #     if self.status != "Visé CF":
    #         frappe.throw(_("La fiche doit être au statut 'Visé CF' avant de pouvoir être soumise."))    
        
    # ══════════════════════════════════════════
    #  HOOKS WORKFLOW
    # ══════════════════════════════════════════
    #
    #  MAPPAGE DOCSTATUS :
    #    Brouillon       → docstatus=0 (draft)
    #    Signé Doyen     → docstatus=0 (draft)
    #    Envoyé CF       → docstatus=1 (submitted) ← SUBMIT ici
    #    Visé CF         → docstatus=1 (submitted, allow_on_submit)
    #    Rejeté          → docstatus=2 (cancelled)  ← Amend disponible
    #    Rejeté Définitif→ docstatus=2 (cancelled)  ← Amend bloqué
    # ══════════════════════════════════════════

    def before_submit(self):
        """
        Submit = Envoyé CF (docstatus 0→1).
        La fiche DOIT être status='Envoyé CF'.
        """
        if self.status != "Envoyé CF":
            frappe.throw(_(
                "Seule une fiche au statut 'Envoyé CF' peut être soumise. "
                "Statut actuel : {0}"
            ).format(self.status))

    def after_insert(self):
        """Appelé après la création de la fiche."""
        if (self.type_fiche == "Dépense"
                and self.type_article == "A priori"
                and not self.is_transfert
                and not self.situation_paiement
                and self.docstatus != 2
                and self.type_engagement_apriori == "Convention"):
            self._creer_situation_paiement()
            self._mettre_a_jour_document_lie()

    def on_submit(self):
        """docstatus 0→1 : Fiche envoyée au CF (soumise)."""
        pass  # _handle_post_submit() est appelé par action_viser_cf après le visa

    def before_cancel(self):
        """
        Cancel = Rejet CF (simple ou définitif).
        Bloque si la fiche est Visée CF (docstatus=1, status='Visé CF').
        """
        if self.status == "Visé CF":
            frappe.throw(_("Une fiche visée par le CF ne peut pas être annulée."))

    def on_cancel(self):
        """
        Déclenché par action_rejeter() après avoir posé le status.
        - Rejeté Définitif → _handle_rejet_definitif() + _handle_cancel()
        - Rejeté           → _handle_cancel() standard (restaure liaisons)
        """
        if self.status == "Rejeté Définitif":
            self._handle_rejet_definitif()
        else:
            self._handle_cancel()

    def before_amend(self):
        """Bloque côté serveur l'Amend sur Rejeté Définitif."""
        if self.status == "Rejeté Définitif":
            frappe.throw(_(
                "Cette fiche a été rejetée définitivement. "
                "Elle ne peut pas être amendée."
            ))

    def on_amend(self):
        #"""
        # Amend après Rejeté simple.
        # Conserve le numero_fiche original — même numéro tout au long du cycle.
        # Repart à Brouillon, docstatus=0.
        # """
        # if self.amended_from:
        #     orig_numero = frappe.db.get_value(
        #         "Fiche Budgetaire", self.amended_from, "numero_fiche"
        #     )
        #     if orig_numero:
        #         self.numero_fiche = orig_numero
        # self.status         = "Brouillon"
        # self.motif_rejet    = ""
        # self.visa_cf_numero = ""
        # self.date_visa_cf   = None
        """
        Pattern identique au Mandat Paiement :
        - Remet status = "Brouillon" (le cycle repart proprement)
        - Vide les champs liés au rejet et au visa
        - Le numero_fiche est déjà conservé par before_insert
        """
        self.status             = "Brouillon"
        self.motif_rejet        = ""
        self.visa_cf_numero     = ""
        self.date_visa_cf       = None
        self.date_signature_doyen = None
        
        # Re-synchroniser les champs depuis le BC ou la convention
        self._set_readonly_fields()

    def on_trash(self):
        """
        Suppression : bloquée si Visé CF (docstatus=1) ou Rejeté Définitif (docstatus=2)
                     ou si des fiches postérieures existent
        """
        if self.status in ("Visé CF", "Rejeté", "Rejeté Définitif"):
            frappe.throw(_(
                "La fiche au statut '{0}' ne peut pas être supprimée."
            ).format(self.status))
        
        # Vérifier l'ordre séquentiel
        if self._has_successor_fiches():
            fiches_list = ", ".join(self._get_successor_fiches_list())
            frappe.throw(_(
                "Impossible de supprimer la fiche N° {0}.<br><br>"
                "Des fiches postérieures existent pour le même article: {1}.<br><br>"
                "Supprimez d'abord les fiches suivantes dans l'ordre décroissant."
            ).format(
                str(self.numero_fiche).zfill(4),
                fiches_list
            ))
        # Libérer le document lié uniquement si la suppression est autorisée
        self._handle_cancel()

    # ══════════════════════════════════════════
    #  NUMÉROTATION SÉQUENTIELLE
    # ══════════════════════════════════════════

    def _set_numero_fiche(self):
        """
        Numéro séquentiel par article (ou partition si has_partition=1).
        Toutes les fiches d'un article partagent la même séquence :
          0001 → Économie initiale
          0002 → Provision S1 (A Post.) | Dépense #1 (A Pri.) | Éco transfert | Dép transfert
          0003..N → suite séquentielle
        """
        filters = self._base_filters_insert()
        dernier = frappe.db.get_value(
            "Fiche Budgetaire",
            filters,
            "numero_fiche",
            order_by="numero_fiche desc",
        )
        self.numero_fiche = (cint(dernier) + 1) if dernier else 1

    def _base_filters_insert(self):
        """Filtres de base pour numérotation (avant save, pas de self.name)."""
        filters = {
            "article": self.article,
            "budget_global": self.budget_global,
            #"docstatus": ["!=", 2],
        }
        art = frappe.get_doc("Budget Article", self.article)
        if art.has_partition and self.code_partition:
            filters["code_partition"] = self.code_partition
        return filters

    # ══════════════════════════════════════════
    #  CHAMPS READONLY (fetch automatique)
    # ══════════════════════════════════════════

    def _set_readonly_fields(self):
        """Remplit les champs calculés depuis les liaisons."""

        # ── Ordonnateur depuis Annee Budgetaire ──
        # if self.annee_budgetaire:
        #     ab     = frappe.get_doc("Annee Budgetaire", self.annee_budgetaire)
        #     faculte = frappe.get_doc("Faculte", ab.faculte)
        #     self.code_ordonnateur    = faculte.ordonnateur
        #     self.intitule_ordonnateur = faculte.intitule_faculte

        # ── Article → Chapitre + champs ──
        if self.article:
            art = frappe.get_doc("Budget Article", self.article)
            self.type_article     = art.type
            self.code_article         = art.code_article
            self.intitule_article = art.intitule_article
            self.chapitre         = art.budget_chapitre
            if art.has_partition:
                self.code_partition           = art.code_partition
                self.intitule_partition = art.intitule_partition

        # ── Chapitre ──
        if self.chapitre:
            chap = frappe.get_doc("Budget Chapitre", self.chapitre)
            self.code_chapitre     = chap.code
            self.intitule_chapitre = chap.intitule

        # ── Transfert : renseigner article_contrepartie + montant ──
        if self.is_transfert and self.fiche_transfert:
            trans = frappe.get_doc("Fiche Transfert Credit", self.fiche_transfert)
            self.montant_operation = flt(trans.montant_transfere)
            self.chapitre = trans.chapitre
            #self.titre = trans.titre
            # Article contrepartie selon sens
            if self.sens_transfert == "Crédit Reçu":
                self.article_contrepartie = trans.article_source
                self.article = trans.article_destination
                self.code_partition = trans.partition_destination
            else:
                self.article_contrepartie = trans.article_destination
                self.article = trans.article_source
                self.code_partition = trans.partition_source
                

        # ── Engagement A Priori : Bon Commande / Convention / Frais Mission ──
        # Re-synchronise les champs read_only depuis la source liée.
        # Indispensable après Amend : les valeurs copiées de l'original
        # sont ignorées par Frappe (champs read_only) et doivent être
        # recalculées côté serveur pour refléter le nouvel engagement choisi.
        if (self.type_fiche == "Dépense"
                and self.type_article == "A priori"
                and not self.is_transfert
                and self.type_engagement_apriori):

            if self.type_engagement_apriori == "Bon Commande" and self.bon_commande:
                bc = frappe.get_doc("Bon Commande", self.bon_commande)
                self.bc_numero  = bc.numero_bon_commande
                self.bc_date    = bc.date_commande
                self.bc_montant = flt(bc.total_ttc)
                self.fournisseur = bc.prestataire or self.fournisseur
                if bc.prestataire:
                    rs = frappe.db.get_value("Fournisseur", bc.prestataire, "raison_sociale")
                    if rs:
                        self.raison_sociale = rs
                # montant_operation = montant du BC (sauf si déjà saisi différemment)
                if not self.is_transfert:
                    self.montant_operation = flt(bc.total_ttc)

            elif self.type_engagement_apriori == "Convention" and self.convention:
                conv = frappe.get_doc("Convention", self.convention)
                self.conv_numero          = conv.numero_convention
                self.conv_date            = conv.date_convention
                self.conv_montant         = flt(conv.montant_convention)
                self.reference_convention = conv.numero_convention
                self.fournisseur          = conv.fournisseur or self.fournisseur
                if conv.fournisseur:
                    rs = frappe.db.get_value("Fournisseur", conv.fournisseur, "raison_sociale")
                    if rs:
                        self.raison_sociale = rs
                if not self.is_transfert:
                    self.montant_operation = flt(conv.montant_convention)

            elif self.type_engagement_apriori == "Frais Mission" and self.frais_mission_apriori:
                fm = frappe.get_doc("Frais Mission", self.frais_mission_apriori)
                # montant_operation = montant du Frais Mission
                self.montant_operation = flt(fm.montant_total)

        # ── Provision (pour Régularisation — lignes Provision & Crédit) ──
        if self.type_fiche == "Régularisation" and self.provision_reference:
            prov = frappe.get_doc("Fiche Budgetaire", self.provision_reference)
            self.provision_ancien_solde  = prov.ancien_solde
            self.provision_montant       = prov.montant_operation
            self.provision_nouveau_solde = prov.nouveau_solde
            # Ligne crédit = soldes de la fiche courante (calculés après)

    # ══════════════════════════════════════════
    #  COHÉRENCE TYPE_FICHE / TYPE_ARTICLE
    # ══════════════════════════════════════════

    def _validate_type_coherence(self):
        ta = self.type_article
        tf = self.type_fiche
        tr = self.is_transfert

        # ── Provision → uniquement A posteriori ──
        if tf == "Provision" and ta != "A posteriori":
            frappe.throw(_("La fiche Provision est réservée aux articles À Posteriori."))

        # ── Régularisation → uniquement A posteriori ──
        if tf == "Régularisation" and ta != "A posteriori":
            frappe.throw(_("La fiche Régularisation est réservée aux articles À Posteriori."))

        # ── Dépense normale (hors transfert) → uniquement A priori ──
        if tf == "Dépense" and not tr and ta != "A priori":
            frappe.throw(_(
                "La fiche Dépense (hors transfert) est réservée aux articles À Priori."
            ))

        # ── Transfert : sens_transfert obligatoire ──
        if tr and not self.sens_transfert:
            frappe.throw(_("Veuillez préciser le sens du transfert (Crédit Reçu / Crédit Donné)."))

        # ── Transfert Crédit Reçu → type_fiche doit être Économie ──
        if tr and self.sens_transfert == "Crédit Reçu" and tf != "Économie":
            frappe.throw(_(
                "Un transfert de Crédit Reçu doit être enregistré comme fiche Économie."
            ))

        # ── Transfert Crédit Donné → type_fiche doit être Dépense ──
        if tr and self.sens_transfert == "Crédit Donné" and tf != "Dépense":
            frappe.throw(_(
                "Un transfert de Crédit Donné doit être enregistré comme fiche Dépense."
            ))

        # ── Semestre obligatoire pour Provision & Régularisation ──
        if tf in ("Provision", "Régularisation") and not self.semestre:
            frappe.throw(_("Le semestre est obligatoire pour les fiches {0}.").format(tf))

    # ══════════════════════════════════════════
    #  VALIDATION TRANSFERT DE CRÉDIT
    # ══════════════════════════════════════════

    def _validate_transfert(self):
        """
        Règles spécifiques aux transferts de crédit :
        ─ A posteriori (source ou destination) : uniquement AVANT la Provision S1 visée
        ─ Même chapitre entre article source et destination
        ─ Fiche Transfert Credit doit être visée CF
        ─ Le montant du transfert doit correspondre à la Fiche Transfert Credit
        """
        if not self.is_transfert:
            return

        if not self.fiche_transfert:
            frappe.throw(_(
                "Veuillez indiquer la Fiche Transfert Crédit associée à ce transfert."
            ))

        trans = frappe.get_doc("Fiche Transfert Credit", self.fiche_transfert)

        # ── Fiche Transfert doit être visée CF ──
        if trans.status != "Visé CF":
            frappe.throw(_(
                "La Fiche Transfert Crédit {0} doit être visée par le CF avant "
                "de créer les fiches de transfert."
            ).format(self.fiche_transfert))

        # ── Montant cohérent ──
        if flt(self.montant_operation) != flt(trans.montant_transfere):
            frappe.throw(_(
                "Le montant de la fiche ({0} DA) doit être égal au montant transféré "
                "dans la Fiche Transfert ({1} DA)."
            ).format(self.montant_operation, trans.montant_transfere))

        # ── Contrainte A posteriori : avant Provision S1 ──
        # Sur l'article COURANT (qu'il soit source ou destination)
        if self.type_article == "A posteriori":
            if self._provision_s1_visee():
                frappe.throw(_(
                    "Transfert impossible sur l'article {0} (À Posteriori) : "
                    "la Provision S1 est déjà visée."
                ).format(self.article))

        # ── Contrainte A posteriori : sur l'article CONTREPARTIE ──
        if self.article_contrepartie:
            art_contra = frappe.get_doc("Budget Article", self.article_contrepartie)
            if art_contra.type == "A posteriori":
                prov_s1_contra = self._provision_s1_visee_pour(self.article_contrepartie)
                if prov_s1_contra:
                    frappe.throw(_(
                        "Transfert impossible : la Provision S1 est déjà visée "
                        "pour l'article contrepartie {0} (À Posteriori)."
                    ).format(self.article_contrepartie))

        # ── Même chapitre ──
        chapitre_contra = frappe.db.get_value(
            "Budget Article", self.article_contrepartie, "budget_chapitre"
        ) if self.article_contrepartie else None

        if chapitre_contra and chapitre_contra != self.chapitre:
            frappe.throw(_(
                "Le transfert de crédit doit se faire entre articles du même chapitre. "
                "Article courant : chapitre {0}, Article contrepartie : chapitre {1}."
            ).format(self.chapitre, chapitre_contra))

        # ── Vérifier cohérence sens / rôle dans la fiche transfert ──
        if self.sens_transfert == "Crédit Donné":
            if trans.article_source != self.article:
                frappe.throw(_(
                    "Incohérence : pour un Crédit Donné, l'article courant ({0}) "
                    "doit être l'article SOURCE dans la Fiche Transfert ({1})."
                ).format(self.article, trans.article_source))

        if self.sens_transfert == "Crédit Reçu":
            if trans.article_destination != self.article:
                frappe.throw(_(
                    "Incohérence : pour un Crédit Reçu, l'article courant ({0}) "
                    "doit être l'article DESTINATION dans la Fiche Transfert ({1})."
                ).format(self.article, trans.article_destination))

        # ── Vérifier qu'une seule fiche de ce sens existe pour ce transfert ──
        fiche_doublon = frappe.db.exists("Fiche Budgetaire", {
            "fiche_transfert": self.fiche_transfert,
            "sens_transfert": self.sens_transfert,
            "article": self.article,
            "docstatus": ["!=", 2],
            "name": ["!=", self.name or ""],
        })
        if fiche_doublon:
            frappe.throw(_(
                "Une fiche de transfert ({0}) existe déjà pour cet article "
                "avec le sens '{1}'."
            ).format(fiche_doublon, self.sens_transfert))

    # ══════════════════════════════════════════
    #  VALIDATION SÉQUENCE
    # ══════════════════════════════════════════

    def _validate_sequence(self):
        n  = self.numero_fiche
        tf = self.type_fiche
        tr = self.is_transfert

        # ── Économie initiale → toujours 0001, unique ──
        if tf == "Économie" and not tr:
            if n != 1:
                frappe.throw(_("La fiche Économie initiale doit toujours être numéro 0001."))
            if self._fiche_economie_initiale_existe():
                frappe.throw(_("Une fiche Économie initiale existe déjà pour cet article."))

        # ── Provision S1 → doit être 0002 ──
        # Mais attention : si un transfert (éco ou dépense) a déjà été créé avant,
        # la Provision S1 peut porter un numéro > 2. On vérifie seulement
        # qu'elle vient après la fiche Économie initiale.
        if tf == "Provision" and self.semestre == "S1":
            eco = self._get_fiche_economie_initiale()
            if not eco:
                frappe.throw(_(
                    "Impossible de créer la Provision S1 : "
                    "aucune fiche Économie initiale trouvée."
                ))
            # S'il y a eu un transfert entre l'éco et maintenant,
            # le numéro peut être 3 ou plus — c'est correct.
            # On valide seulement qu'il n'existe pas déjà une Provision S1.
            if self._provision_s1_existe():
                frappe.throw(_("Une Provision S1 existe déjà pour cet article."))

        # ── Provision S2 → après Provision S1 visée ──
        if tf == "Provision" and self.semestre == "S2":
            if not self._provision_s1_visee():
                frappe.throw(_(
                    "La Provision S1 doit être visée par le CF avant de créer la Provision S2."
                ))
            if self._provision_s2_existe():
                frappe.throw(_("Une Provision S2 existe déjà pour cet article."))

    # ══════════════════════════════════════════
    #  PRÉREQUIS (fiches antérieures visées CF)
    # ══════════════════════════════════════════

    def _validate_prerequis(self):
        tf = self.type_fiche
        tr = self.is_transfert

        # ── Toute fiche sauf Économie initiale :
        #    la Fiche Économie initiale doit être visée CF ──
        if not (tf == "Économie" and not tr):
            eco = self._get_fiche_economie_initiale()
            if not eco:
                frappe.throw(_(
                    "Aucune fiche Économie initiale trouvée pour l'article {0}."
                ).format(self.article))
            
            #if self.status != "Visé CF" and self.status != "Rejeté" and self.docstatus == 0:
            #     frappe.msgprint(_("Cette fiche n'est pas encore visée par le CF. Veuillez la viser."), indicator="blue")
            if self.status in ["Visé CF", "Rejeté", "Rejeté Définitif"]:
                if eco.docstatus != 1 or eco.status != "Visé CF":
                    frappe.throw(_(
                        "La fiche Économie initiale (N° {0}) doit être visée par le CF "
                        "avant toute autre fiche."
                    ).format(str(eco.numero_fiche).zfill(4)))

        # ── Transfert de Crédit Donné (Dépense transfert) :
        #    la Fiche Transfert Credit doit être visée CF (déjà vérifié dans _validate_transfert)
        #    De plus, le solde disponible doit être suffisant ──
        if tr and self.sens_transfert == "Crédit Donné":
            disponible = self._get_solde_disponible()
            if flt(self.montant_operation) > flt(disponible):
                frappe.throw(_(
                    "Solde insuffisant pour le transfert. "
                    "Disponible : {0} DA, Montant transféré : {1} DA."
                ).format(disponible, self.montant_operation))

        # ── Régularisation → Provision du semestre visée ──
        if tf == "Régularisation":
            if not self.provision_reference:
                frappe.throw(_(
                    "Veuillez indiquer la référence de la Provision pour cette Régularisation."
                ))
            prov = frappe.get_doc("Fiche Budgetaire", self.provision_reference)
            # if prov.status != "Visé CF":
            #     frappe.throw(_(
            #         "La Provision du semestre {0} doit être visée par le CF "
            #         "avant la Régularisation."
            #     ).format(self.semestre))
            if prov.semestre != self.semestre:
                frappe.throw(_(
                    "La Provision référencée (semestre {0}) ne correspond pas "
                    "au semestre de la Régularisation ({1})."
                ).format(prov.semestre, self.semestre))

    # ══════════════════════════════════════════
    #  MONTANTS & SOLDES
    # ══════════════════════════════════════════

    def _validate_montants(self):
        tf = self.type_fiche
        tr = self.is_transfert

        # ── Économie initiale : montant = montant alloué à l'article ──
        if tf == "Économie" and not tr:
            # Budget Article naming = {article}, donc name = article
            montant_alloue = frappe.db.get_value(
                "Budget Article", self.article, "montant"
            )
            if not montant_alloue:
                frappe.throw(_(
                    "Aucun Budget Article trouvé pour l'article {0}. "
                    "Créez un Budget Article avec name = {0}."
                ).format(self.article))
            if flt(self.montant_operation) != flt(montant_alloue):
                frappe.throw(_(
                    "Le montant de la fiche Économie ({0} DA) doit être égal "
                    "au montant alloué à l'article ({1} DA)."
                ).format(self.montant_operation, montant_alloue))

        # ── Provision : montant = 50 % du total disponible ──
        # Le total disponible = somme Économie initiale + tous les transferts reçus
        if tf == "Provision":
            total_credit = self._get_total_credit_article()
            attendu = flt(total_credit) * 0.5
            if flt(self.montant_operation) != attendu:
                frappe.throw(_(
                    "La Provision {0} doit être égale à 50 % du crédit total de l'article "
                    "({1} DA × 50% = {2} DA)."
                ).format(self.semestre, total_credit, attendu))

        # ── Dépense / Régularisation : crédit disponible suffisant ──
        if tf in ("Dépense", "Régularisation") and not tr:
            disponible = self._get_solde_disponible()
            if flt(self.montant_operation) > flt(disponible):
                frappe.throw(_(
                    "Crédit insuffisant. Solde disponible : {0} DA, "
                    "Montant demandé : {1} DA."
                ).format(disponible, self.montant_operation))

        # ── Transfert Crédit Reçu : montant > 0 ──
        if tr and self.sens_transfert == "Crédit Reçu":
            if flt(self.montant_operation) <= 0:
                frappe.throw(_("Le montant du transfert doit être supérieur à 0."))

    def _compute_ancien_solde(self):
        """
        Calcule l'ancien solde = nouveau_solde de la dernière fiche visée CF.
        Doit être appelé EN PREMIER dans validate().
        """
        # Économie initiale et Provision : ancien_solde = 0
        #if self.type_fiche in ("Économie", "Provision") and not self.is_transfert:
        if (self.type_fiche == "Économie") and not self.is_transfert:
            self.ancien_solde = 0
        else:
            self.ancien_solde = self._get_solde_fiche_precedente()

    def _compute_nouveau_solde(self):
        """
        Calcule le nouveau solde selon le type d'opération.
        Doit être appelé APRÈS _validate_montants().
        """
        # Crédit → Ajouter
        if self.type_fiche in ("Économie", "Provision"):
            self.nouveau_solde = flt(self.ancien_solde) + flt(self.montant_operation)
        
        # Débit → Soustraire
        elif self.type_fiche in ("Dépense", "Régularisation"):
            self.nouveau_solde = flt(self.ancien_solde) - flt(self.montant_operation)
        
        # Transfert Crédit Reçu → Ajouter
        if self.is_transfert and self.sens_transfert == "Crédit Reçu":
            self.nouveau_solde = flt(self.ancien_solde) + flt(self.montant_operation)
        
        # Transfert Crédit Donné → Soustraire
        if self.is_transfert and self.sens_transfert == "Crédit Donné":
            self.nouveau_solde = flt(self.ancien_solde) - flt(self.montant_operation)
        
        # ✅ Vérifier que le solde n'est pas négatif
        if flt(self.nouveau_solde) < 0:
            frappe.throw(_(
                "⚠️ Solde négatif détecté !<br><br>"
                "Ancien solde : <b>{0} DA</b><br>"
                "Montant opération : <b>{1} DA</b><br>"
                "Nouveau solde : <b style='color:red'>{2} DA</b><br><br>"
                "Le montant de l'opération dépasse le solde disponible."
            ).format(
                format_currency(self.ancien_solde),
                format_currency(self.montant_operation),
                format_currency(self.nouveau_solde)
            ))
    
    # ══════════════════════════════════════════
    #  NATURE ENGAGEMENT (auto)
    # ══════════════════════════════════════════

    def _set_ref_engagement_obs(self):
        annee = frappe.db.get_value("Annee Budgetaire", self.annee_budgetaire, "annee")
        tf    = self.type_fiche
        tr    = self.is_transfert
        sens  = self.sens_transfert
        if not self.ref_engagement_obs:
            if tf == "Économie" and not tr:
                self.ref_engagement_obs = (
                    f"PRISE EN COMPTE DE CRÉDITS SUIVANT EXTRAIT D'ORDONNANCE DE DÉLÉGATION "
                    f"DE CRÉDITS DANS LE CADRE DU BUDGET DE FONCTIONNEMENT {annee}"
                )

            elif tf == "Économie" and tr and sens == "Crédit Reçu":
                art_source = frappe.db.get_value(
                    "Budget Article", self.article_contrepartie,
                    ["code_article", "intitule_article"], as_dict=True
                ) if self.article_contrepartie else {}
                self.ref_engagement_obs = (
                    f"TRANSFERT DE CRÉDIT REÇU – ARTICLE SOURCE : "
                    f"{art_source.get('code_article','')} {art_source.get('intitule_article','')}"
                )

            elif tf == "Provision" and self.semestre == "S1":
                self.ref_engagement_obs = (
                    "ENGAGEMENT DE LA PREMIÈRE PROVISION POUR L'EXERCICE {annee}"
                )

            elif tf == "Provision" and self.semestre == "S2":
                self.ref_engagement_obs = (
                    "ENGAGEMENT DE LA DEUXIÈME PROVISION POUR L'EXERCICE {annee}"
                )

            elif tf == "Dépense" and tr and sens == "Crédit Donné":
                art_dest = frappe.db.get_value(
                    "Budget Article", self.article_contrepartie,
                    ["code_article", "intitule_article"], as_dict=True
                ) if self.article_contrepartie else {}
                self.ref_engagement_obs = (
                    f"TRANSFERT DE CRÉDIT DONNÉ – ARTICLE DESTINATAIRE : "
                    f"{art_dest.get('code_article','')} {art_dest.get('intitule_article','')}"
                )

            elif tf == "Dépense" and not tr:
                mapping = {
                    "Bon Commande" : "BON DE COMMANDE",
                    "Convention"   : "CONVENTION",
                    "Frais Mission": "ÉTAT DE FRAIS DE MISSION",
                }
                self.ref_engagement_obs = mapping.get(self.type_engagement_apriori, "DÉPENSE")
                if self.type_engagement_apriori == "Convention":
                    self.ref_engagement_obs = f"CONVENTION N° {self.conv_numero}  du {self.conv_date} "
                elif self.type_engagement_apriori == "Bon Commande":
                    self.ref_engagement_obs = f"BON DE COMMANDE N° {self.bc_numero} du {self.bc_date} - {self.raison_sociale}"    
                elif self.type_engagement_apriori == "Frais Mission":
                     self.ref_engagement_obs = "REMBOURSEMENT DE FRAIS DE MISSION "
            elif tf == "Régularisation":
                self.ref_engagement_obs = "REGULARISATION D'ENGAGEMENT DE DEPENSES DANS SA FORME A POSTERIORI"
    def _set_nature_engagement(self):
        if not self.nature_engagement:
            self.nature_engagement = self.ref_engagement_obs
	# ─────────────────────────────────────────────────────────
	#  CALCUL SOLDES - ARTICLES À POSTERIORI
	# ─────────────────────────────────────────────────────────

    def _compute_soldes_aposteriori(self):
        """
        Calcule les soldes pour les articles À Posteriori :
        - Provision S1 et S2
        - Régularisation
        Remplit les champs : provision_*, credit_*, et les champs standard.
        """
        tf = self.type_fiche

        # --- Provision S1 ---
        if tf == "Provision" and self.semestre == "S1":
            derniere_fiche = self._get_derniere_fiche_visee()
            if not derniere_fiche:
                frappe.throw(_("Aucune fiche visée avant la Provision S1."))
            credit_initial = flt(derniere_fiche.nouveau_solde)
            montant_provision = credit_initial * 0.5

            # Ligne Crédit
            self.credit_ancien_solde = credit_initial
            self.credit_montant = montant_provision
            self.credit_nouveau_solde = credit_initial - montant_provision

            # Ligne Provision
            self.provision_ancien_solde = 0
            self.provision_montant = montant_provision
            self.provision_nouveau_solde = montant_provision

            # Champs standard
            self.ancien_solde = 0
            self.montant_operation = montant_provision
            self.nouveau_solde = montant_provision

        # --- Provision S2 ---
        elif tf == "Provision" and self.semestre == "S2":
            derniere_fiche = self._get_derniere_fiche_visee()
            if not derniere_fiche:
                frappe.throw(_("Aucune fiche visée avant la Provision S2."))
            # Le crédit restant après S1 (ou après régularisations)
            credit_restant = flt(derniere_fiche.credit_ancien_solde)
            # Le montant de la provision existante avant S2
            provision_anterieure = flt(derniere_fiche.provision_nouveau_solde)

            # Ligne Crédit : on prend tout le crédit restant
            self.credit_ancien_solde = credit_restant
            self.credit_montant = credit_restant
            self.credit_nouveau_solde = 0

            # Ligne Provision
            self.provision_ancien_solde = provision_anterieure
            self.provision_montant = credit_restant
            self.provision_nouveau_solde = provision_anterieure + credit_restant

            # Champs standard
            self.ancien_solde = provision_anterieure
            self.montant_operation = credit_restant
            self.nouveau_solde = provision_anterieure + credit_restant

        # --- Régularisation ---
        elif tf == "Régularisation":  # adaptez le nom exact (avec ou sans accent)
            if not self.provision_reference:
                frappe.throw(_("Provision de référence manquante."))

            prov_ref = frappe.get_doc("Fiche Budgetaire", self.provision_reference)
            credit_actuel = flt(prov_ref.credit_nouveau_solde)
            derniere_fiche = self._get_derniere_fiche_visee()
            if derniere_fiche:

                #credit_actuel = flt(derniere_fiche.credit_nouveau_solde)
                provision_actuelle = flt(derniere_fiche.provision_nouveau_solde)
            else:
                # Première régularisation après provision
                #prov_ref = frappe.get_doc("Fiche Budgetaire", self.provision_reference)
                #credit_actuel = flt(prov_ref.credit_nouveau_solde)
                provision_actuelle = flt(prov_ref.provision_nouveau_solde)

            montant_regularise = self._calculate_montant_regularisation()

            # Ligne Provision
            self.provision_ancien_solde = provision_actuelle
            self.provision_montant = montant_regularise
            self.provision_nouveau_solde = provision_actuelle - montant_regularise

            # Ligne Crédit
            self.credit_ancien_solde = credit_actuel
            self.credit_montant = self.provision_nouveau_solde
            self.credit_nouveau_solde = self.credit_ancien_solde + self.credit_montant

            # Champs standard
            self.ancien_solde = provision_actuelle
            self.montant_operation = montant_regularise
            self.nouveau_solde = provision_actuelle - montant_regularise

    def _calculate_montant_regularisation(self):
        """
		Calcule le montant total des dépenses internes régularisées.
		= Somme des montants de toutes les factures des dépenses internes.
		"""
        if not self.depenses_regularisees:
            return 0
		
        total = 0
        # for row in self.depenses_regularisees:
        #     dep = frappe.get_doc("Depense Interne", row.depense_interne)
        #     # Le montant_total de la Dépense Interne = montant du mandat
        #     total += flt(dep.montant_total)
        for row in self.depenses_regularisees:
            total += flt(row.montant)
                    
        return total


    def _get_derniere_fiche_visee(self):
        """
        Retourne la dernière fiche visée CF pour cet article.
        Utilisé pour récupérer les soldes actuels (Provision et Régularisation).
        """
        #filters = self._base_filters()
        filters = {
            "article": self.article,
            "budget_global": self.budget_global,
            "name": ["!=", self.name or ""]
        }
        #filters["status"] = "Visé CF"
        #filters["docstatus"] = ["!=", 2]
        #filters["numero_fiche"] = ["<", self.numero_fiche]
        if self.numero_fiche:
            filters["numero_fiche"] = ["<", self.numero_fiche]

        result = frappe.get_all(
            "Fiche Budgetaire",
			filters=filters,
		    fields=["name", "numero_fiche", "nouveau_solde", "provision_nouveau_solde", "credit_nouveau_solde"],
            #fields=["name", "provision_nouveau_solde", "credit_nouveau_solde", "numero_fiche"],
			order_by="numero_fiche desc",
			limit=1
		)
		
        if result:
            return frappe.get_doc("Fiche Budgetaire", result[0].name)
		
        return None


	# ─────────────────────────────────────────────────────────
	#  VALIDATION MONTANTS - ARTICLES À POSTERIORI
	# ─────────────────────────────────────────────────────────

    def _validate_montants_aposteriori(self):
        """
        Valide les montants pour les articles À Posteriori.
        """
        # PROVISION S1 = 50% du crédit total
        if self.type_fiche == "Provision" and self.semestre == "S1":
            derniere_fiche = self._get_derniere_fiche_visee()
            if not derniere_fiche:
                frappe.throw(_("Aucune fiche avant Provision S1."))
            credit_total = flt(derniere_fiche.nouveau_solde)
            attendu = credit_total * 0.5
            if abs(flt(self.provision_montant) - attendu) > 0.01:
                frappe.throw(_(
                    "Provision S1 doit être 50% du crédit total ({0} DA). Saisi : {1} DA"
                ).format(attendu, self.provision_montant))
        
        elif self.type_fiche == "Provision" and self.semestre == "S2":
            derniere_fiche = self._get_derniere_fiche_visee()
            if not derniere_fiche:
                frappe.throw(_("Aucune fiche avant Provision S2."))
            credit_restant = flt(derniere_fiche.credit_ancien_solde)
            if abs(flt(self.provision_montant) - credit_restant) > 0.01:
                frappe.throw(_(
                    "Provision S2 doit être égale au crédit restant ({0} DA). Saisi : {1} DA"
                ).format(credit_restant, self.provision_montant))
        
        elif self.type_fiche == "Régularisation":
            montant_regularise = self._calculate_montant_regularisation()
            derniere_fiche = self._get_derniere_fiche_visee()
            if derniere_fiche:
                provision_dispo = flt(derniere_fiche.provision_nouveau_solde)
            else:
                prov_ref = frappe.get_doc("Fiche Budgetaire", self.provision_reference)
                provision_dispo = flt(prov_ref.provision_nouveau_solde)
            if montant_regularise > provision_dispo + 0.01:
                frappe.throw(_(
                    "Provision insuffisante. Disponible: {0} DA, demandé: {1} DA"
                ).format(provision_dispo, montant_regularise))
		
    # ══════════════════════════════════════════
    #  TABLE DÉPENSES RÉGULARISÉES
    # ══════════════════════════════════════════
    def _validate_regularisation_table(self):
        if self.type_fiche != "Régularisation":
            return

        if not self.depenses_regularisees:
            frappe.throw(_("Veuillez ajouter au moins une dépense à régulariser."))

        # Récupérer les autres fiches de régularisation non annulées
        other_regs = frappe.get_all(
            "Fiche Budgetaire",
            filters={
                "name": ["!=", self.name or ""],
                "type_fiche": "Régularisation",
                "docstatus": ["!=", 2]
            },
            pluck="name"
        )

        # Dépenses déjà utilisées ailleurs
        used_depenses = []
        if other_regs:
            used_depenses = frappe.get_all(
                "Depense Regularisee Element",
                filters={"parent": ["in", other_regs]},
                pluck="depense_interne"
            )

        # Vérification des doublons dans la table courante
        lignes_vues = set()
        total = 0
        dep_checked = {}

        for row in self.depenses_regularisees:
            if not row.depense_interne:
                frappe.throw(_("Ligne {0} : dépense interne manquante.").format(row.idx))

            # Éviter les doublons de ligne (même dépense, même facture/bénéficiaire)
            ligne_key = (row.depense_interne, row.facture_numero, row.nom_prenom, row.montant)
            if ligne_key in lignes_vues:
                frappe.throw(_("Ligne {0} : doublon détecté.").format(row.idx))
            lignes_vues.add(ligne_key)

            # Charger la dépense si pas déjà fait
            if row.depense_interne not in dep_checked:
                dep = frappe.get_doc("Depense Interne", row.depense_interne)
                dep_checked[row.depense_interne] = dep

                # Vérifications globales sur la dépense
                if dep.article != self.article:
                    frappe.throw(_("La dépense {0} appartient à l'article {1}.").format(
                        row.depense_interne, dep.article))

                if dep.status not in ["Mandaté", "Réglé"]:
                    frappe.throw(_("La dépense {0} doit être Mandaté ou Réglé.").format(row.depense_interne))

                if dep.semestre != self.semestre:
                    frappe.throw(_("La dépense {0} est du semestre {1}.").format(
                        row.depense_interne, dep.semestre))

                if row.depense_interne in used_depenses:
                    frappe.throw(_("La dépense {0} est déjà utilisée ailleurs.").format(row.depense_interne))

            total += flt(row.montant)

        self.montant_operation = total
        
      
    # ══════════════════════════════════════════
    #  VALIDATION FRAI MISSION
    # ══════════════════════════════════════════
    
    def _validate_frais_mission(self):
        """Valide le Frais Mission pour Dépense A Priori."""
        if self.type_fiche != "Dépense" or self.type_article != "A priori":
            return
        
        if self.type_engagement_apriori != "Frais Mission":
            return
        
        if not self.frais_mission_apriori:
            frappe.throw(_("Veuillez sélectionner un Frais Mission."))
        
        fm = frappe.get_doc("Frais Mission", self.frais_mission_apriori)
        
        # Vérifier article
        if fm.article != self.article:
            frappe.throw(_(
                "Le Frais Mission appartient à l'article {0}, pas à {1}."
            ).format(fm.article, self.article))
        
        # Vérifier type article A Priori
        type_article = frappe.db.get_value("Budget Article", fm.article, "type")
        if type_article != "A priori":
            frappe.throw(_(
                "Le Frais Mission est lié à un article À Posteriori. "
                "Pour les articles À Posteriori, utilisez Dépense Interne."
            ))
        
        # Le montant de la fiche doit correspondre au montant du Frais Mission
        if flt(self.montant_operation) != flt(fm.montant_total):
            frappe.throw(_(
                "Le montant de la fiche ({0} DA) doit être égal au montant "
                "du Frais Mission ({1} DA)."
            ).format(self.montant_operation, fm.montant_total))
    
    # ══════════════════════════════════════════
    #  ON UPDATE
    # ══════════════════════════════════════════
    def on_update(self):
        # ... (autres actions éventuelles)
        # if self.is_transfert and self.fiche_transfert and self.status == "Visé CF":
        #     self._mettre_a_jour_fiche_transfert()
        
        # ── Synchroniser les documents liés (Convention ou Bon Commande) ──
        self._mettre_a_jour_document_lie()

    def _mettre_a_jour_document_lie(self):
        """
        Met à jour automatiquement le statut du document lié (Convention ou Bon Commande)
        selon le statut de la fiche dépense.
        """
        # ── Convention ──
        if self.type_engagement_apriori == "Convention" and self.convention:
            conv = frappe.get_doc("Convention", self.convention)
            changed = False
            
            # Mapping des statuts Fiche Dépense → Convention
            status_mapping = {
                "Brouillon": "Brouillon",
                "Signé Doyen": "Signé",
                "Envoyé CF": "Envoyé CF", 
                "Visé CF": "Visé CF",
                "Rejeté": "Rejeté CF",
                "Rejeté Définitif": "Rejeté Définitif"
            }
            
            # Appliquer le changement de statut si nécessaire
            target_status = status_mapping.get(self.status)
            if target_status and conv.status != target_status:
                conv.status = target_status
                changed = True
                
                # Synchroniser les champs spécifiques
                if self.status == "Signé Doyen":
                    conv.date_signature = self.date_signature_doyen
                elif self.status == "Visé CF":
                    conv.visa_cf_numero = self.visa_cf_numero
                    conv.date_visa_cf = self.date_visa_cf
                elif self.status in ["Rejeté", "Rejeté Définitif"]:
                    conv.motif_rejet = self.motif_rejet
            
            # Lier la fiche dépense à la convention (si non déjà liée)
            if not conv.fiche_depense or conv.fiche_depense != self.name:
                if self.status not in ["Rejeté", "Rejeté Définitif"]:
                    conv.fiche_depense = self.name
                    if self.situation_paiement:
                        conv.situation_paiement = self.situation_paiement
                    changed = True
            # Annulation en cascade
            # if self.docstatus == 2 and conv.docstatus != 2:
            #     conv.cancel()
            #     changed = True
                
            if changed:
                conv.save(ignore_permissions=True)

        # ── Bon de Commande ──
        elif self.type_engagement_apriori == "Bon Commande" and self.bon_commande:
            bc = frappe.get_doc("Bon Commande", self.bon_commande)
            changed = False
            
            # Mapping des statuts Fiche Dépense → Bon Commande
            status_mapping = {
                "Brouillon": "Validé",
                "Signé Doyen":"Signé Doyen",
                "Envoyé CF": "Envoyé CF",
                "Visé CF": "Visé CF", 
                "Rejeté": "Rejeté",
                "Rejeté Définitif": "Rejeté Définitif"
            }
            
            # Appliquer le changement de statut si nécessaire
            target_status = status_mapping.get(self.status)
            if target_status and bc.status != target_status:
                bc.status = target_status
                changed = True
                
                # Synchroniser les champs spécifiques
                if self.status == "Visé CF":
                    bc.visa_cf = str(self.visa_cf_numero) if self.visa_cf_numero else ""
                    bc.date_visa_cf = self.date_visa_cf
                elif self.status in ["Rejeté", "Rejeté Définitif"]:
                    bc.motif_rejet = self.motif_rejet
            
            # Lier la fiche dépense au bon de commande (si non déjà lié)
            if not bc.fiche_depense or bc.fiche_depense != self.name:
                if self.status not in ["Rejeté", "Rejeté Définitif"]:
                    bc.fiche_depense = self.name  # ✅ Simple égalité pour affectation
                    changed = True
            # Annulation en cascade
            # if self.docstatus == 2 and bc.docstatus != 2:
            #     bc.cancel()
            #     changed = True
                
            if changed:
                bc.save(ignore_permissions=True)
    # ══════════════════════════════════════════
    #  POST-SUBMIT
    # ══════════════════════════════════════════

    def _handle_post_submit(self):
        """Actions après soumission."""

        # ── Régularisation : renuméroter si 1 seule dépense ──
        if self.type_fiche == "Régularisation" and self.status == "Visé CF":
            #nb = len(self.depenses_regularisees)
            for row in self.depenses_regularisees:
                updates = {
                    "fiche_regularisation": self.name,
                    "numero_fiche_regularisation": self.numero_fiche,
                    "status": "Régularisé",
                }
                # if nb == 1:
                #     updates["numero_interne"]          = self.numero_fiche
                #     updates["is_regularisation_unique"] = 1
                frappe.db.set_value("Depense Interne", row.depense_interne, updates)

        # ── Dépense A priori Convention → créer Situation Paiement ──
        if (self.type_fiche == "Dépense"
                and self.type_article == "A priori"
                and not self.is_transfert
                and not self.situation_paiement
                and self.docstatus != 2
                and self.type_engagement_apriori == "Convention"):
            self._creer_situation_paiement()

        # ── Transfert : mettre à jour la Fiche Transfert Credit ──
        if self.is_transfert and self.fiche_transfert:
            self._mettre_a_jour_fiche_transfert()

    def _creer_situation_paiement(self):
        """Crée la Situation Paiement pour convention Prestation et Acquisition."""
        conv = frappe.get_doc("Convention", self.convention)
        if not self.name or self.name.startswith('new-'):
            frappe.throw(_("Erreur interne : name de la fiche non disponible."))

        if frappe.db.exists("Situation Paiement", {"fiche_depense": self.name}):
            return  # Déjà créée

        sp = frappe.get_doc({
            "doctype"                : "Situation Paiement",
            "convention"             : self.convention,
            "fiche_depense"          : self.name,
            "budget_global"       : self.budget_global,
            "article"                : self.article,
            "numero_convention"      : conv.numero_convention,
            "date_convention"        : conv.date_convention,
            "fournisseur"            : conv.fournisseur,
            "objet_convention"       : conv.objet_convention,
            "montant_total_convention": self.montant_operation,
            "status"                 : "En Cours",
        })
        sp.insert(ignore_permissions=True)
        frappe.db.set_value("Fiche Budgetaire", self.name, "situation_paiement", sp.name)
        frappe.db.set_value("Convention", self.convention, "situation_paiement", sp.name)
        frappe.db.set_value("Convention", self.convention, "status", 'En Exécution')
        frappe.db.set_value("Situation Paiement", sp.name, "fiche_depense", self.name)

    def _mettre_a_jour_fiche_transfert(self):
        """
        Met à jour la Fiche Transfert Credit avec les références
        des fiches budgétaires créées (source et destination).
        """
        trans = frappe.get_doc("Fiche Transfert Credit", self.fiche_transfert)

        if self.sens_transfert == "Crédit Donné":
            frappe.db.set_value(
                "Fiche Transfert Credit", self.fiche_transfert,
                "fiche_source", self.name
            )
        elif self.sens_transfert == "Crédit Reçu":
            frappe.db.set_value(
                "Fiche Transfert Credit", self.fiche_transfert,
                "fiche_destination", self.name
            )

        # Si les deux fiches existent → marquer Exécuté
        trans.reload()
        if trans.fiche_source and trans.fiche_destination:
            # Vérifier le statut des deux fiches
            fiche_src = frappe.get_doc("Fiche Budgetaire", trans.fiche_source)
            fiche_dest = frappe.get_doc("Fiche Budgetaire", trans.fiche_destination)
            if fiche_src.status == "Visé CF" and fiche_dest.status == "Visé CF":
                frappe.db.set_value(
                    "Fiche Transfert Credit", self.fiche_transfert,
                    {"status": "Exécuté", "date_execution": nowdate()}
                )

    def _handle_cancel(self):
        """Annulation."""

        #Remettre les dépenses internes à 'Réglé'
        if self.type_fiche == "Régularisation":
            for row in self.depenses_regularisees:
                frappe.db.set_value("Depense Interne", row.depense_interne, {
                    "fiche_regularisation"          : None,
                    "numero_fiche_regularisation"   : 0,
                    "status"                        : "Réglé",
                    "is_regularisation_unique"      : 0,
                })

        # Remettre la Fiche Transfert en état Visé CF
        if self.is_transfert and self.fiche_transfert:
            field = "fiche_source" if self.sens_transfert == "Crédit Donné" else "fiche_destination"
            frappe.db.set_value(
                "Fiche Transfert Credit", self.fiche_transfert,
                {field: None, "status": "Visé CF", "date_execution": None}
            )
        # ── Libérer le bon de commande ou la convention liée lors de l'annulation ──
        # Cette section réinitialise le document lié pour qu'il puisse être réutilisé
        if self.type_fiche in ["Dépense", "Depense"] and not self.is_transfert:
            if self.type_engagement_apriori == "Bon Commande" and self.bon_commande:
                frappe.db.set_value("Bon Commande", self.bon_commande, {
                    "fiche_depense": None,        # Détacher de la fiche dépense
                    "status": "Validé",           # Remettre en statut initial
                })
            elif self.type_engagement_apriori == "Convention" and self.convention:
                frappe.db.set_value("Convention", self.convention, {
                    "fiche_depense": None,        # Détacher de la fiche dépense  
                    "status": "Brouillon",   
                    "date_signature": None,       # Vider la date de signature
                })



    # ══════════════════════════════════════════
    #  GARDE-FOU modif après visa/rejet définitif
    # ══════════════════════════════════════════

    def _bloquer_si_definitif(self):
        """
        Garde-fou : bloque la modification d'une fiche rejetée définitivement.
        Les champs allow_on_submit (status, motif_rejet, etc.) sont modifiables
        par les méthodes action_* légitimes via save() AVANT le cancel().
        Ce garde-fou s'applique aux tentatives extérieures (formulaire, API tierce).
        """
        if self.is_new():
            return
        # Lire depuis la base (self.status peut déjà avoir changé en mémoire)
        db_status    = frappe.db.get_value("Fiche Budgetaire", self.name, "status")    or ""
        db_docstatus = frappe.db.get_value("Fiche Budgetaire", self.name, "docstatus") or 0
        # Bloquer uniquement docstatus=2 + Rejeté Définitif
        # (Rejeté simple est aussi docstatus=2 mais autorise Amend → on ne bloque pas)
        if int(db_docstatus) == 2 and db_status == "Rejeté Définitif":
            frappe.throw(_(
                "Cette fiche a été rejetée définitivement. "
                "Elle ne peut plus être modifiée."
            ))

    # ══════════════════════════════════════════
    #  REJET DÉFINITIF (depuis on_cancel)
    # ══════════════════════════════════════════

    def _handle_rejet_definitif(self):
        """Libère les liaisons lors d'un rejet définitif."""
        # Appeler aussi le cancel standard (transferts, régularisations)
        self._handle_cancel()

    # ══════════════════════════════════════════
    #  ACTIONS MÉTIER
    # ══════════════════════════════════════════

    def action_signer_doyen(self, date_signature):
        """
        Brouillon → Signé Doyen (docstatus reste 0).
        Peut aussi être appelé après Amend (amended_from présent).
        """
        if self.status != "Brouillon":
            frappe.throw(_("La fiche doit être en brouillon pour être signée."))
        self.status = "Signé Doyen"
        self.date_signature_doyen = date_signature
        self.save(ignore_permissions=True)
        self._mettre_a_jour_document_lie()

    def action_envoyer_cf(self):
        """
        Signé Doyen → Envoyé CF → Submit (docstatus 0→1).

        ORDRE :
          1. status = 'Envoyé CF'
          2. save()    → validate() passe (docstatus=0 en base → _bloquer ne bloque pas)
          3. reload    → doc propre
          4. submit()  → before_submit() vérifie status='Envoyé CF' → OK → docstatus=1
        """
        if self.status != "Signé Doyen":
            frappe.throw(_("La fiche doit être signée par le Doyen avant envoi au CF."))
        self.status = "Envoyé CF"
        self.save(ignore_permissions=True)
        # Soumettre → docstatus passe à 1
        doc = frappe.get_doc("Fiche Budgetaire", self.name)
        doc.submit()
        self._mettre_a_jour_document_lie()

    def action_viser_cf(self, visa_cf_numero, date_visa_cf):
        """
        Envoyé CF → Visé CF (docstatus reste 1, champ allow_on_submit).
        Puis appelle _handle_post_submit() pour les actions post-visa.
        Pas de submit() supplémentaire : la fiche est déjà soumise.
        """
        if self.status != "Envoyé CF":
            frappe.throw(_("La fiche doit être au statut 'Envoyé CF' pour être visée."))
        if self.docstatus != 1:
            frappe.throw(_("La fiche doit être soumise (docstatus=1) pour être visée."))
        self.status         = "Visé CF"
        self.visa_cf_numero = visa_cf_numero
        self.date_visa_cf   = date_visa_cf
        self.save(ignore_permissions=True)
        # Mettre à jour les documents liés (Bon Commande)
        self._mettre_a_jour_document_lie()
        # Exécuter les actions post-visa (régularisations, conventions, etc.)
        self._handle_post_submit()

    def action_rejeter(self, motif, date_rejet=None, definitif=False):
        """
        Rejet CF depuis Envoyé CF (docstatus=1).
        Les deux types passent en docstatus=2 (cancel) :
        - Rejeté           → docstatus=2, Amend disponible (before_amend laisse passer)
        - Rejeté Définitif → docstatus=2, Amend bloqué (before_amend throw)

        ORDRE :
          1. Poser status et motif (allow_on_submit)
          2. save()    → écrit en base
          3. cancel()  → before_cancel() vérifie status != 'Visé CF' → OK
                         on_cancel()    lit self.status → dispatch
                         docstatus passe à 2
        """
        if self.status != "Envoyé CF":
            frappe.throw(_(
                "La fiche doit être au statut 'Envoyé CF' pour être rejetée. "
                "Statut actuel : {0}"
            ).format(self.status))
        if self.docstatus != 1:
            frappe.throw(_("La fiche doit être soumise (docstatus=1) pour être rejetée."))
        if not motif:
            frappe.throw(_("Le motif de rejet est obligatoire."))

        nb = (self.nb_rejets or 0) + 1
        self.nb_rejets = nb
        self.append("historique_rejets", {
            "numero_rejet":    nb,
            "date_rejet":      date_rejet or nowdate(),
            "motif_rejet":     motif,
            "rejet_definitif": 1 if definitif else 0,
        })
        self.motif_rejet = motif
        self.status      = "Rejeté Définitif" if definitif else "Rejeté"
        self.save(ignore_permissions=True)
        # Mettre à jour les documents liés (Bon Commande)
        self._mettre_a_jour_document_lie()
        # Cancel → docstatus 1→2
        # on_cancel() lira self.status ('Rejeté' ou 'Rejeté Définitif')
        frappe.get_doc("Fiche Budgetaire", self.name).cancel()

    def action_marquer_corrige(self, date_correction=None, corrections=None):
        """
        Après Amend : enregistre les corrections dans la dernière ligne de l'historique.
        Remet status = "Brouillon" pour relancer le cycle (Signer → Envoyer CF).
        Pattern identique à action_marquer_corrige() du Mandat Paiement.
        """
        if self.docstatus != 0:
            frappe.throw(_("Seule une fiche en brouillon (après Amend) peut être marquée corrigée."))
        if self.status != "Rejeté":
            frappe.throw(_("La fiche doit être au statut 'Rejeté' pour être marquée corrigée."))
        for row in reversed(self.historique_rejets or []):
            if not row.date_correction:
                row.date_correction = date_correction or nowdate()
                #row.corrige_par     = frappe.session.user
                if corrections:
                    row.corrections = corrections
                break
        self.status      = "Brouillon"
        self.motif_rejet = ""
        self.save(ignore_permissions=True)
        self._mettre_a_jour_document_lie()
        
        # Re-synchroniser les champs depuis le BC ou la convention
        self._set_readonly_fields()
        
        # Forcer la mise à jour des champs readonly avec db.set_value
        if self.type_fiche in ["Dépense", "Depense"] and self.type_engagement_apriori == "Convention" and self.convention:
            conv = frappe.get_doc("Convention", self.convention)
            updates = {
                "conv_numero": conv.numero_convention,
                "conv_montant": conv.montant_convention,
                "reference_convention": conv.consultation_numero,
                "fournisseur": conv.fournisseur,
                "montant_operation": conv.montant_convention
            }
            # Ajouter la date si elle existe
            if hasattr(conv, 'date_convention'):
                updates["conv_date"] = conv.date_convention
                
            frappe.db.set_value("Fiche Budgetaire", self.name, updates)
            
        elif self.type_fiche in ["Dépense", "Depense"] and self.type_engagement_apriori == "Bon Commande" and self.bon_commande:
            bc = frappe.get_doc("Bon Commande", self.bon_commande)
            updates = {
                "bc_numero": bc.numero_bon_commande,
                "bc_date": bc.date_commande,
                "bc_montant": bc.total_ttc
            }
            frappe.db.set_value("Fiche Budgetaire", self.name, updates)
    # ══════════════════════════════════════════
    # Verifier si fiches postérieures existe avent annuler ou supprimer
    # ══════════════════════════════════════════
    def _has_successor_fiches(self):
        """
        Vérifie s'il existe des fiches avec un numéro supérieur pour le même article.
        Retourne True si des fiches postérieures existent.
        """
        filters = {
            "article": self.article,
            "budget_global": self.budget_global,
            "numero_fiche": [">", self.numero_fiche],
            #"docstatus": ["!=", 2],  # exclut les fiches déjà annulées
            #"name": ["!=", self.name]
        }
        
        # Ajouter la partition si l'article en a une
        #art = frappe.get_doc("Article", self.article)
        #if art.has_partition and self.code_partition:
        #    filters["code_partition"] = self.code_partition
        
        #return frappe.db.exists("Fiche Budgetaire", filters)
        # Récupérer une liste distincte des numéros de fiche supérieurs
        result = frappe.db.get_list(
            "Fiche Budgetaire",
            filters=filters,
            distinct="numero_fiche",
            pluck="numero_fiche",
            limit=1
        )
        return len(result) > 0

    def _get_successor_fiches_list(self):
        """
        Retourne la liste des numéros des fiches postérieures pour l'article.
        """
        filters = {
            "article": self.article,
            "budget_global": self.budget_global,
            "numero_fiche": [">", self.numero_fiche],
            #"docstatus": ["!=", 2],
            #"name": ["!=", self.name]
        }
        
        # art = frappe.get_doc("Article", self.article)
        # if art.has_partition and self.code_partition:
        #     filters["code_partition"] = self.code_partition
        
        result = frappe.db.get_list(
            "Fiche Budgetaire",
            filters=filters,
            fields=["numero_fiche", "type_fiche"],
            group_by="numero_fiche",
            order_by="numero_fiche asc"
        )
        
        #return [f"#{str(f['numero_fiche']).zfill(4)} ({f['type_fiche']})" for f in fiches]
        return [f"#{str(row['numero_fiche']).zfill(4)} ({row['type_fiche']})" for row in result]
    # ══════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════

    def _base_filters(self):
        """Filtres de base incluant self.name en exclusion."""
        filters = {
            "article"          : self.article,
            "budget_global" : self.budget_global,
            "docstatus"        : ["!=", 2],
        }
        art = frappe.get_doc("Budget Article", self.article)
        if art.has_partition and self.code_partition:
            filters["code_partition"] = self.code_partition
        if self.name:
            filters["name"] = ["!=", self.name]
        return filters

    def _fiche_economie_initiale_existe(self):
        f = dict(self._base_filters())
        f.update({"type_fiche": "Économie", "is_transfert": 0})
        return frappe.db.exists("Fiche Budgetaire", f)

    def _get_fiche_economie_initiale(self):
        f = {
            "article"          : self.article,
            "budget_global" : self.budget_global,
            "type_fiche"       : "Économie",
            "is_transfert"     : 0,
            "status"           : ["in", ["Brouillon", "Signé Doyen", "Envoyé CF", "Visé CF"]],
            "docstatus"        : ["!=", 2],
        }
        art = frappe.get_doc("Budget Article", self.article)
        if art.has_partition and self.code_partition:
            f["code_partition"] = self.code_partition
        name = frappe.db.get_value("Fiche Budgetaire", f, "name")
        return frappe.get_doc("Fiche Budgetaire", name) if name else None

    def _provision_s1_existe(self):
        f = dict(self._base_filters())
        f.update({"type_fiche": "Provision", "semestre": "S1"})
        return frappe.db.exists("Fiche Budgetaire", f)

    def _provision_s1_visee(self):
        f = dict(self._base_filters())
        f.update({"type_fiche": "Provision", "semestre": "S1", "status": "Visé CF"})
        return frappe.db.exists("Fiche Budgetaire", f)

    def _provision_s2_existe(self):
        f = dict(self._base_filters())
        f.update({"type_fiche": "Provision", "semestre": "S2"})
        return frappe.db.exists("Fiche Budgetaire", f)

    def _provision_s1_visee_pour(self, article):
        """Vérifie Provision S1 visée pour un article quelconque (contrepartie)."""
        filters = {
            "article"          : article,
            "budget_global" : self.budget_global,
            "type_fiche"       : "Provision",
            "semestre"         : "S1",
            "status"           : ["in", ["Brouillon", "Signé Doyen", "Envoyé CF", "Visé CF"]],
            "docstatus"        : ["!=", 2],
        }
        art = frappe.get_doc("Budget Article", article)
        if art.has_partition:
            pass  # On ne filtre pas par partition ici (on ne connaît pas la partition de l'autre article)
        return frappe.db.exists("Fiche Budgetaire", filters)

    def _get_solde_disponible(self):
        """Retourne le nouveau_solde de la dernière fiche VISÉE CF."""
        f = dict(self._base_filters())
        f["status"] = ["in", ["Brouillon", "Signé Doyen", "Envoyé CF", "Visé CF"]]
        f["docstatus"] = ["!=", 2]
        result = frappe.get_all(
            "Fiche Budgetaire",
            filters=f,
            fields=["nouveau_solde"],
            order_by="numero_fiche desc",
            limit=1,
        )

        return flt(result[0]["nouveau_solde"]) if result else 0

    def _get_total_credit_article(self):
        """
        Retourne le crédit total de l'article =
        Économie initiale + tous les transferts REÇUS (Économie transfert visés CF).
        Utilisé pour calculer les provisions (50% chacune).
        """
        f = {
            "article"          : self.article,
            "budget_global" : self.budget_global,
            "type_fiche"       : "Économie",
            "status"           : ["in", ["Brouillon", "Signé Doyen", "Envoyé CF", "Visé CF"]],
            "docstatus"        : ["!=", 2],
        }
        art = frappe.get_doc("Budget Article", self.article)
        if art.has_partition and self.code_partition:
            f["code_partition"] = self.code_partition
        if self.name:
            f["name"] = ["!=", self.name]

        fiches_eco = frappe.get_all(
            "Fiche Budgetaire", filters=f, fields=["montant_operation", "is_transfert"]
        )
        total = sum(flt(fe["montant_operation"]) for fe in fiches_eco)
        return total

    # ══════════════════════════════════════════════
    #  ANCIEN SOLDE FICHE PRECEDENTE
    # ══════════════════════════════════════════════
    def _get_solde_fiche_precedente(self):
        """Retourne le nouveau_solde de la fiche avec le numéro immédiatement inférieur (même article, même partition, non annulée)."""
        filters = self._base_filters()
        filters["numero_fiche"] = ["<", self.numero_fiche]
        filters["status"] = ["in", ["Brouillon", "Signé Doyen", "Envoyé CF", "Visé CF"]]
        filters["docstatus"] = ["!=", 2]  # exclut les annulées
        # Optionnel : si vous voulez exclure certains statuts (ex: "Rejeté"), ajoutez-les.
        # Par exemple : filters["status"] = ["not in", ["Rejeté"]]

        result = frappe.get_all(
            "Fiche Budgetaire",
            filters=filters,
            fields=["nouveau_solde"],
            order_by="numero_fiche desc",
            limit=1
        )
        return flt(result[0]["nouveau_solde"]) if result else 0

# ══════════════════════════════════════════════
#  VALIDATION DATE MANDAT
# ══════════════════════════════════════════════
@frappe.whitelist()
def valider_date_mandat(date_str):
    """
    Règles :
    - Entre le 1er et le 20 du mois
    - Pas vendredi (weekday 4) ni samedi (weekday 5)
    - Pas un jour férié (fixes + table Jour Ferie)
    """
    date = getdate(date_str)

    if not (1 <= date.day <= 20):
        frappe.throw(_(
            "La date de mandatement doit être entre le 1er et le 20 du mois "
            "(jour saisi : {0})."
        ).format(date.day))

    if date.weekday() == 4:
        frappe.throw(_("La date de mandatement ne peut pas être un Vendredi."))
    if date.weekday() == 5:
        frappe.throw(_("La date de mandatement ne peut pas être un Samedi."))

    for (m, j) in FERIES_FIXES:
        if date.month == m and date.day == j:
            frappe.throw(_(
                "Le {0}/{1} est un jour férié (fixe). Choisissez un jour ouvrable."
            ).format(j, m))

    if frappe.db.exists("Jour Ferie", date_str):
        designation = frappe.db.get_value("Jour Ferie", date_str, "designation")
        frappe.throw(_(
            "Le {0} est un jour férié ({1}). Choisissez un jour ouvrable."
        ).format(date_str, designation))


# ══════════════════════════════════════════════
#  API WHITELISTED
# ══════════════════════════════════════════════

@frappe.whitelist()
def get_solde_article(article, budget_global, code_partition=None):
    """Retourne le solde disponible d'un article."""
    filters = {
        "article"          : article,
        "budget_global" : budget_global,
        #"status"           : ["in", ["Brouillon", "Signé Doyen", "Envoyé CF", "Visé CF"]],
    }
     
    art = frappe.get_doc("Budget Article", article)
    if art.type == "A priori":
        filters["docstatus"] = ["!=", 2]
        filters["status"] = ["in", ["Brouillon", "Signé Doyen", "Envoyé CF", "Visé CF"]]
    if art.has_partition and code_partition:
        filters["code_partition"] = code_partition

    result = frappe.get_all(
        "Fiche Budgetaire",
        filters=filters,
        fields=["nouveau_solde", "numero_fiche"],
        order_by="numero_fiche desc",
        limit=1,
    )
    return {
        "solde"         : flt(result[0]["nouveau_solde"]) if result else 0,
        "derniere_fiche": result[0]["numero_fiche"] if result else 0,
    }

@frappe.whitelist()
def get_ancien_solde_fiche(article, type_article,  budget_global, numero_fiche, code_partition=None):
    """Retourne le nouveau_solde de la fiche avec le numéro immédiatement inférieur (même article, même partition)."""
    filters = {
        "article": article,
        "budget_global": budget_global,
        #"status": ["in", ["Brouillon", "Signé Doyen", "Envoyé CF", "Visé CF"]],
        "numero_fiche": ["<", numero_fiche], 
    }
    if type_article == "A priori":
        filters["docstatus"] = ["!=", 2]
        filters["status"] = ["in", ["Brouillon", "Signé Doyen", "Envoyé CF", "Visé CF"]]
    # Optionnel : si on veut exclure les rejetés, on peut ajouter status != "Rejeté"
    # filters["status"] = ["!=", "Rejeté"]
    if code_partition:
        filters["code_partition"] = code_partition

    result = frappe.get_all(
        "Fiche Budgetaire",
        filters=filters,
        fields=["nouveau_solde", "numero_fiche"],
        order_by="numero_fiche desc",
        limit=1,
    )
    return {
        "solde": flt(result[0]["nouveau_solde"]) if result else 0,
        "derniere_fiche": result[0]["numero_fiche"] if result else 0,
    }

@frappe.whitelist()
def get_depenses_non_regularisees(article, budget_global, semestre, fiche_actuelle=None, depenses_exclues=None):
    """
    Retourne les Dépenses Internes mandatées, non encore utilisées
    dans une fiche de régularisation (même en cours de préparation).
    depenses_exclues : liste des dépenses déjà présentes dans la fiche courante.
    """
    import json
    if isinstance(depenses_exclues, str):
        depenses_exclues = json.loads(depenses_exclues) if depenses_exclues else []

    # 1. Récupérer toutes les fiches de régularisation non annulées SAUF la fiche actuelle
    filters_reg = {
        "type_fiche": "Régularisation",
        #"docstatus": ["!=", 2],
    }
    if fiche_actuelle:
        filters_reg["name"] = ["!=", fiche_actuelle]

    other_regs = frappe.get_all(
        "Fiche Budgetaire",
        filters=filters_reg,
        pluck="name"
    )

    # 2. Dépenses déjà utilisées dans ces fiches
    used_depenses = []
    if other_regs:
        used_depenses = frappe.get_all(
            "Depense Regularisee Element",
            filters={
                "parenttype": "Fiche Budgetaire",
                "parentfield": "depenses_regularisees",
                "parent": ["in", other_regs]
            },
            pluck="depense_interne"
        )

    # 3. Ajouter les dépenses exclues (déjà dans la fiche courante)
    if depenses_exclues:
        used_depenses.extend(depenses_exclues)

    # 4. Construire les filtres pour les dépenses internes
    filters = {
        "article": article,
        "budget_global": budget_global,
        "semestre": semestre,
        "status": ["in", ["Mandaté", "Réglé"]]
    }
    if used_depenses:
        filters["name"] = ["not in", used_depenses]

    # 5. Récupérer les dépenses éligibles
    depenses = frappe.get_all(
        "Depense Interne",
        filters=filters,
        fields=[
            "name", "numero_interne", "type_depense",
            "fournisseur", "montant_total", "mandat_paiement", "semestre"
        ]
    )

    # 6. Enrichir avec les informations du mandat
    for d in depenses:
        if d.mandat_paiement:
            mandat = frappe.get_doc("Mandat Paiement", d.mandat_paiement)
            d.numero_mandat = mandat.numero_mandat
            d.date_mandat = mandat.date_mandat

    return depenses

@frappe.whitelist()
def get_montant_alloue(article):
    """Retourne le montant Budget Article (naming = article)."""
    return flt(frappe.db.get_value("Budget Article", article, "montant"))

@frappe.whitelist()
def verifier_provision_s1_visee(article, budget_global, code_partition=None):
    """Vérifie si la Provision S1 est visée (pour bloquer les transferts A posteriori)."""
    filters = {
        "article"          : article,
        "budget_global" : budget_global,
        "type_fiche"       : "Provision",
        "semestre"         : "S1",
        "status"           : "Visé CF",
    }
    if code_partition:
        filters["code_partition"] = code_partition
    return bool(frappe.db.exists("Fiche Budgetaire", filters))


@frappe.whitelist()
def verifier_meme_chapitre(article_source, article_destination):
    """
    Vérifie que deux articles appartiennent au même chapitre.
    Utilisé pour valider les transferts de crédit.
    Appelé depuis le JS lors de la saisie de l'article contrepartie.
    """
    chap_src = frappe.db.get_value("Budget Article", article_source, "budget_chapitre")
    chap_dest = frappe.db.get_value("Budget Article", article_destination, "budget_chapitre")
    
    return {
        "meme_chapitre": chap_src == chap_dest,
        "chapitre_source": chap_src,
        "chapitre_destination": chap_dest,
    }


@frappe.whitelist()
def get_info_depense_interne(depense_interne):
    """Retourne la liste des factures ou bénéficiaires d'une Dépense Interne."""
    dep = frappe.get_doc("Depense Interne", depense_interne)
    items = []

    # Informations du mandat (communes à toutes les lignes)
    mandat_numero = ""
    mandat_date = None
    if dep.mandat_paiement:
        mandat = frappe.get_doc("Mandat Paiement", dep.mandat_paiement)
        mandat_numero = str(mandat.numero_mandat)
        mandat_date = mandat.date_mandat

    if dep.type_depense == "Fournisseur":
        for f in dep.factures:
            items.append({
                "depense_interne": dep.name,
                "type_depense": "Fournisseur",
                "facture_numero": f.numero_facture,
                "facture_date": f.date_facture,
                "montant": f.montant,
                "mandat_numero": mandat_numero,
                "mandat_date": mandat_date,
                "fournisseur": dep.fournisseur,
                "raison_sociale": dep.raison_sociale,
                "nom_prenom": "",
                "grade": ""
            })
    else:  # Frais Mission
        for b in dep.beneficiaires:
            items.append({
                "depense_interne": dep.name,
                "type_depense": "Frais Mission",
                "facture_numero": "",
                "facture_date": None,
                "montant": b.montant,
                "mandat_numero": mandat_numero,
                "mandat_date": mandat_date,
                "nom_prenom": b.nom_prenom,
                "grade": b.grade,
                "fournisseur": "",
                "raison_sociale": ""
            })
    return items

@frappe.whitelist()
def get_total_credit_article(article, budget_global, code_partition=None):
    """
    Retourne le crédit total de l'article (solde après transferts) pour le calcul de la provision.
    Utilise le nouveau_solde de la dernière fiche de type Économie ou Dépense (hors annulées).
    """
    filters = {
        "article": article,
        "budget_global": budget_global,
        "type_fiche": ["in", ["Économie", "Dépense"]],
        "status": ["in", ["Brouillon", "Signé Doyen", "Envoyé CF", "Visé CF"]],
        "docstatus": ["!=", 2],
    }
    if code_partition:
        filters["code_partition"] = code_partition

    last_fiche = frappe.get_all(
        "Fiche Budgetaire",
        filters=filters,
        fields=["nouveau_solde", "numero_fiche"],
        order_by="numero_fiche desc",
        limit=1,
    )
    if last_fiche:
        credit_total = flt(last_fiche[0]["nouveau_solde"])
    else:
        credit_total = 0

    return {"total_credit": credit_total, "provision_50": credit_total * 0.5}

@frappe.whitelist()
def verifier_transfert_possible(article, budget_global, code_partition=None):
    """
    Vérifie si un transfert est possible pour un article.
    Retourne un dict avec : possible (bool), motif (str si non possible).
    """
    art = frappe.get_doc("Budget Article", article)

    if art.type == "A posteriori":
        filters = {
            "article"          : article,
            "budget_global" : budget_global,
            "type_fiche"       : "Provision",
            "semestre"         : "S1",
            "status"           : ["in", ["Brouillon", "Signé Doyen", "Envoyé CF", "Visé CF"]],
            "docstatus"        : ["!=", 2],
        }
        if code_partition:
            filters["code_partition"] = code_partition

        if frappe.db.exists("Fiche Budgetaire", filters):
            return {
                "possible": False,
                "motif"   : "La Provision S1 existe pour cet article À Posteriori.",
            }

    return {"possible": True, "motif": ""}


@frappe.whitelist()
def get_total_economie_visee(article, budget_global, code_partition=None):
    """
    Retourne le total des montants des fiches Économie visées CF pour un article.
    Utilisé pour calculer les Provisions (50% du total Économie).
    Appelé depuis le JS lors de la création de Provision.
    """
    filters = {
        "article": article,
        "budget_global": budget_global,
        "type_fiche": "Économie",
        "status": ["in", ["Brouillon", "Signé Doyen", "Envoyé CF", "Visé CF"]],
        "docstatus": ["!=", 2],
    }
    
    art = frappe.get_doc("Budget Article", article)
    if art.has_partition and code_partition:
        filters["code_partition"] = code_partition
    
    result = frappe.get_all(
        "Fiche Budgetaire",
        filters=filters,
        fields=["montant_operation", "is_transfert", "sens_transfert"]
    )
    
    total = sum(flt(r["montant_operation"]) for r in result)
    
    return {
        "total": total,
        "provision_attendue": total * 0.5,
        "nb_fiches_economie": len(result)
    }
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_frais_mission_apriori(doctype, txt, searchfield, start, page_len, filters):
    """Query pour filtrer Frais Mission A priori, en excluant ceux déjà utilisés dans d'autres fiches dépense."""
    article = filters.get('article')
    fiche_actuelle = filters.get('fiche_actuelle', '')

    if not article:
        return []

    # Vérifier que l'article est A priori
    type_article = frappe.db.get_value("Budget Article", article, "type")
    if type_article != "A priori":
        return []

    # Ignorer les noms temporaires
    if fiche_actuelle and fiche_actuelle.startswith('new-'):
        fiche_actuelle = ''

    # Récupérer les frais de mission déjà utilisés dans des fiches dépense (non annulées)
    used_filters = {
        "type_fiche": "Dépense",
        "type_engagement_apriori": "Frais Mission",
        #"docstatus": ["!=", 2],  # exclut les annulés
        "frais_mission_apriori": ["is", "set"]
    }
    if fiche_actuelle:
        used_filters["name"] = ["!=", fiche_actuelle]

    used_frais = frappe.get_all(
        "Fiche Budgetaire",
        filters=used_filters,
        pluck="frais_mission_apriori"
    )
    used_frais = [f for f in used_frais if f]

    # Construire les filtres pour les Frais Mission
    frais_filters = [
        ["article", "=", article]
    ]
    if used_frais:
        frais_filters.append(["name", "not in", used_frais])
    if txt:
        frais_filters.append(["objet_mission", "like", f"%{txt}%"])

    # Récupérer les Frais Mission avec pagination
    frais = frappe.db.get_list(
        "Frais Mission",
        filters=frais_filters,
        fields=["name", "objet_mission"],
        order_by="creation desc",
        limit_start=start,
        limit_page_length=page_len,
        as_list=True
    )

    return frais

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_bon_commande_disponibles(doctype, txt, searchfield, start, page_len, filters):
    """
    Retourne les BC disponibles pour une Fiche Dépense :
    - Même article
    - Non déjà utilisé dans une autre fiche DÉPENSE soumise (docstatus=1)
    """
    article = filters.get('article')
    fiche_actuelle = filters.get('fiche_actuelle', '')

    if not article:
        return []

    # Ignorer les noms temporaires des nouveaux documents
    if fiche_actuelle and fiche_actuelle.startswith('new-'):
        fiche_actuelle = ''

    # 1. Récupérer les BC déjà utilisés dans des fiches dépense soumises
    used_filters = {
        "type_fiche": "Dépense",
        #"docstatus": 1,
        "bon_commande": ["is", "set"]  # non null
    }
    if fiche_actuelle:
        used_filters["name"] = ["!=", fiche_actuelle]

    used_bc = frappe.get_all(
        "Fiche Budgetaire",
        filters=used_filters,
        pluck="bon_commande"
    )
    # Filtrer les valeurs None
    used_bc = [bc for bc in used_bc if bc]

    # 2. Construire les filtres pour les BC
    bc_filters = [
        ["article", "=", article],
        ["status", "=", "Validé"]
    ]
    if used_bc:
        bc_filters.append(["name", "not in", used_bc])
    if txt:
        bc_filters.append(["numero_bon_commande", "like", f"%{txt}%"])

    # 3. Récupérer les BC avec pagination
    bons_commande = frappe.db.get_list(
        "Bon Commande",
        filters=bc_filters,
        fields=["name", "numero_bon_commande", "date_commande", "total_ttc", "prestataire"],
        order_by="date_commande desc",
        limit_start=start,
        limit_page_length=page_len,
        as_list=True
    )

    return bons_commande


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_convention_disponibles(doctype, txt, searchfield, start, page_len, filters):
    """
    Retourne les Conventions disponibles pour une Fiche Dépense :
    - Même article
    - Non déjà utilisée dans une autre fiche dépense (non annulée)
    """
    article = filters.get('article')
    fiche_actuelle = filters.get('fiche_actuelle', '')

    if not article:
        return []

    # Ignorer les noms temporaires de nouveaux documents
    if fiche_actuelle and fiche_actuelle.startswith('new-'):
        fiche_actuelle = ''

    # Récupérer les conventions déjà utilisées dans des fiches dépense (non annulées)
    used_filters = {
        "type_fiche": "Dépense",
        #"docstatus": ["!=", 2],
        "convention": ["is", "set"]
    }
    if fiche_actuelle:
        used_filters["name"] = ["!=", fiche_actuelle]

    used_convs = frappe.get_all(
        "Fiche Budgetaire",
        filters=used_filters,
        pluck="convention"
    )
    used_convs = [c for c in used_convs if c]

    # Construire les filtres pour les conventions
    conv_filters = [
        ["article", "=", article]
    ]
    if used_convs:
        conv_filters.append(["name", "not in", used_convs])

    # Recherche textuelle (OR sur numero_convention et name)
    or_filters = []
    if txt:
        or_filters = [
            ["numero_convention", "like", f"%{txt}%"],
            ["name", "like", f"%{txt}%"]
        ]

    # Récupérer les conventions avec pagination
    conventions = frappe.db.get_list(
        "Convention",
        filters=conv_filters,
        or_filters=or_filters if or_filters else None,
        fields=["name", "numero_convention", "date_convention", "montant_convention", "fournisseur"],
        order_by="date_convention desc",
        limit_start=start,
        limit_page_length=page_len,
        as_list=True
    )

    return conventions

# ─────────────────────────────────────────────────────────
#  API : GET SOLDE (pour articles A Posteriori)
# ─────────────────────────────────────────────────────────

@frappe.whitelist()
def get_solde_article_aposteriori(article, budget_global, code_partition=None):
    """
    Retourne le solde pour les articles À Posteriori.
    
    Returns:
        dict: {
            'provision_solde': solde provision disponible,
            'credit_solde': solde crédit restant,
            'derniere_fiche': numéro de la dernière fiche
        }
    """
    filters = {
        "article": article,
        "budget_global": budget_global,
        "type_article": "A Posteriori",
    }
    
    # art = frappe.get_doc("Article", article)
    # if art.has_partition and code_partition:
    #     filters["code_partition"] = code_partition
    
    result = frappe.get_all(
        "Fiche Budgetaire",
        filters=filters,
        fields=["provision_nouveau_solde", "credit_nouveau_solde", "numero_fiche"],
        order_by="numero_fiche desc",
        limit=1,
    )
    
    if result:
        return {
            "provision_solde": flt(result[0].get("provision_nouveau_solde", 0)),
            "credit_solde": flt(result[0].get("credit_nouveau_solde", 0)),
            "derniere_fiche": result[0].get("numero_fiche", 0)
        }
    else:
        return {
            "provision_solde": 0,
            "credit_solde": 0,
            "derniere_fiche": 0
        }

@frappe.whitelist()
def calculer_lignes_provision_credit(args):
    """
    Calcule les lignes provision et crédit pour une fiche de type Provision ou Régularisation.
    args : dict contenant les champs du formulaire (article, annee_budgetaire, type_fiche, semestre, provision_reference, montant_operation, etc.)
    Retourne un dict avec les 6 champs.
    """
    import json
    if isinstance(args, str):
        args = json.loads(args)

    # Créer un document temporaire
    doc = frappe.new_doc("Fiche Budgetaire")
    for key, value in args.items():
        if value is not None:
            setattr(doc, key, value)

    # Si un nom est fourni, on l'affecte pour l'exclure des recherches de dernières fiches
    if args.get('name'):
        doc.name = args['name']

    if doc.type_fiche in ("Provision", "Régularisation"):
        doc._compute_soldes_aposteriori()
    else:
        return {}

    return {
        "provision_ancien_solde": doc.provision_ancien_solde,
        "provision_montant": doc.provision_montant,
        "provision_nouveau_solde": doc.provision_nouveau_solde,
        "credit_ancien_solde": doc.credit_ancien_solde,
        "credit_montant": doc.credit_montant,
        "credit_nouveau_solde": doc.credit_nouveau_solde,
    }


# @frappe.whitelist()
# def get_ordonnateur_from_annee(annee_budgetaire):
#     """
#     Retourne le code ordonnateur et l'intitulé de l'ordonnateur pour un exercice budgétaire donnée.
#     """
#     if not budget_global:
#         return {}
#     ab = frappe.get_doc("Budget G", annee_budgetaire)
#     faculte = frappe.get_doc("Faculte", ab.faculte)
#     return {
#         "code_ordonnateur": faculte.ordonnateur,
#         "intitule_ordonnateur": faculte.intitule_faculte
#     }

# ─────────────────────────────────────────────────────────
#  API : MISE A JOUR WORKFLOW CONVENTION
# ─────────────────────────────────────────────────────────
@frappe.whitelist()
def signer_fiche_et_convention(fiche_name, date_signature):
    """Signe la fiche dépense et la convention liée (si existe)."""
    fiche = frappe.get_doc("Fiche Budgetaire", fiche_name)
    if fiche.type_engagement_apriori == "Convention" and fiche.convention:
        conv = frappe.get_doc("Convention", fiche.convention)
        conv.date_signature = date_signature
        conv.status = "Signé"
        conv.save()
    fiche.status = "Signé Doyen"
    fiche.date_signature_doyen = date_signature
    fiche.save()
    return {"success": True}

@frappe.whitelist()
def envoyer_fiche_au_cf(fiche_name):
    """Envoie la fiche dépense et la convention liée au CF."""
    fiche = frappe.get_doc("Fiche Budgetaire", fiche_name)
    if fiche.type_engagement_apriori == "Convention" and fiche.convention:
        conv = frappe.get_doc("Convention", fiche.convention)
        conv.status = "Envoyé CF"
        conv.save()
    fiche.status = "Envoyé CF"
    fiche.save()
    return {"success": True}

@frappe.whitelist()
def enregistrer_visa_cf(fiche_name, visa_cf_numero, date_visa_cf):
    """Enregistre le visa CF pour la fiche dépense et la convention liée."""
    fiche = frappe.get_doc("Fiche Budgetaire", fiche_name)
    if fiche.type_engagement_apriori == "Convention" and fiche.convention:
        conv = frappe.get_doc("Convention", fiche.convention)
        conv.visa_cf_numero = visa_cf_numero
        conv.date_visa_cf = date_visa_cf
        conv.status = "Visé CF"
        conv.save()
    fiche.visa_cf_numero = visa_cf_numero
    fiche.date_visa_cf = date_visa_cf
    fiche.status = "Visé CF"
    fiche.save()
    return {"success": True}

@frappe.whitelist()
def rejeter_fiche_et_convention(fiche_name, motif, definitif):
    """Rejette la fiche dépense et la convention liée."""
    fiche = frappe.get_doc("Fiche Budgetaire", fiche_name)
    if fiche.type_engagement_apriori == "Convention" and fiche.convention:
        conv = frappe.get_doc("Convention", fiche.convention)
        conv.motif_rejet = motif
        conv.status = "Rejeté"
        conv.save()
    fiche.motif_rejet = motif
    fiche.status = "Rejeté"
    fiche.save()
    if definitif:
        fiche.cancel()  # passe docstatus à 2 (annulé)
    return {"success": True}

# ─────────────────────────────────────────────────────────
#  API : ANNULER FICHE BUDGETAIRE
# ─────────────────────────────────────────────────────────
@frappe.whitelist()
def annuler_fiche(fiche_name, motif):
    fiche = frappe.get_doc("Fiche Budgetaire", fiche_name)
    if fiche.docstatus != 0:
        frappe.throw(_("Seules les fiches en brouillon peuvent être annulées définitivement."))
    # Mettre à jour directement en base pour éviter les validations inutiles
    frappe.db.set_value("Fiche Budgetaire", fiche_name, {
        "status": "Rejeté",
        "motif_rejet": motif,
        "docstatus": 2
    })
    return {"success": True}

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_depenses_interne_pour_regularisation(doctype, txt, searchfield, start, page_len, filters):
    import json
    # Si filters est une chaîne, la convertir en dict
    if isinstance(filters, str):
        filters = json.loads(filters)

    article = filters.get('article')
    budget_global = filters.get('budget_global')
    semestre = filters.get('semestre')
    exclude = filters.get('exclude', [])

    if not article or not budget_global or not semestre:
        return []

    # 1. Récupérer les fiches de régularisation non annulées
    active_regs = frappe.get_all(
        "Fiche Budgetaire",
        filters={
            "type_fiche": "Régularisation",
            "docstatus": ["!=", 2]
        },
        pluck="name"
    )

    # 2. Dépenses déjà utilisées dans ces fiches
    used_depenses = []
    if active_regs:
        used_depenses = frappe.get_all(
            "Depense Regularisee Element",
            filters={
                "parenttype": "Fiche Budgetaire",
                "parentfield": "depenses_regularisees",
                "parent": ["in", active_regs]
            },
            pluck="depense_interne"
        )

    # 3. Construire les filtres pour les dépenses internes
    filters_list = [
        ["article", "=", article],
        ["budget_global", "=", budget_global],
        ["semestre", "=", semestre],
        ["status", "in", ["Mandaté", "réglé"]]
    ]

    if used_depenses:
        filters_list.append(["name", "not in", used_depenses])

    if exclude:
        if isinstance(exclude, str):
            try:
                exclude = json.loads(exclude)
            except:
                exclude = []
        if exclude:
            filters_list.append(["name", "not in", exclude])

    if txt:
        filters_list.append(["name", "like", f"%{txt}%"])

    # 4. Récupérer les dépenses avec pagination
    depenses = frappe.get_all(
        "Depense Interne",
        filters=filters_list,
        fields=["name", "numero_interne", "type_depense", "fournisseur", "montant_total"],
        limit_start=start,
        limit_page_length=page_len,
        order_by="numero_interne desc"
    )

    # 5. Formater pour le champ Link : liste de [value, label]
    result = []
    for d in depenses:
        if d.type_depense == "Fournisseur":
            label = f"N° {d.numero_interne} - Fournisseur: {d.fournisseur or '?'} - {d.montant_total} DA"
        else:  # Frais Mission
            label = f"N° {d.numero_interne} - Frais Mission - {d.montant_total} DA"
        result.append([d.name, label])

    return result


# ═══════════════════════════════════════════════════════════
#  APIs WORKFLOW FICHE BUDGETAIRE
# ═══════════════════════════════════════════════════════════

@frappe.whitelist()
def signer_doyen(fiche_name, date_signature):
    """Brouillon → Signé Doyen."""
    doc = frappe.get_doc("Fiche Budgetaire", fiche_name)
    doc.action_signer_doyen(date_signature=date_signature)
    return {"status": doc.status}


@frappe.whitelist()
def envoyer_cf(fiche_name):
    """Signé Doyen → Envoyé CF → Submit (docstatus 0→1)."""
    doc = frappe.get_doc("Fiche Budgetaire", fiche_name)
    doc.action_envoyer_cf()
    return {"status": doc.status, "docstatus": 1}


@frappe.whitelist()
def viser_cf(fiche_name, visa_cf_numero, date_visa_cf):
    """Envoyé CF → Visé CF (docstatus reste 1, allow_on_submit)."""
    doc = frappe.get_doc("Fiche Budgetaire", fiche_name)
    doc.action_viser_cf(
        visa_cf_numero=visa_cf_numero,
        date_visa_cf=date_visa_cf,
    )
    return {"status": doc.status, "docstatus": doc.docstatus}


@frappe.whitelist()
def rejeter_fiche(fiche_name, motif, definitif=0, date_rejet=None):
    """
    Rejet simple ou définitif depuis Envoyé CF ou Signé Doyen.
    - Simple    : status=Rejeté,           docstatus reste 0, Amend dispo
    - Définitif : status=Rejeté Définitif, docstatus→2, Amend bloqué
    """
    doc = frappe.get_doc("Fiche Budgetaire", fiche_name)
    doc.action_rejeter(
        motif=motif,
        date_rejet=date_rejet,
        definitif=bool(int(definitif)),
    )
    return {
        "status":    doc.status,
        "nb_rejets": doc.nb_rejets,
        "message": _(
            "Rejet définitif enregistré. La fiche est annulée sans possibilité de reprise."
            if int(definitif) else
            "Rejet enregistré. Utilisez 'Amend' pour créer une fiche corrigée."
        ),
    }


@frappe.whitelist()
def marquer_corrige_fiche(fiche_name, date_correction=None, corrections=None):
    """Après Amend : enregistre les corrections sur le draft."""
    doc = frappe.get_doc("Fiche Budgetaire", fiche_name)
    doc.action_marquer_corrige(
        date_correction=date_correction,
        corrections=corrections,
    )
    return {"status": doc.status}


@frappe.whitelist()
def get_historique_rejets_fiche(fiche_name):
    """Retourne l'historique des rejets CF d'une fiche."""
    return frappe.get_all(
        "Rejet Fiche Element",
        filters={"parent": fiche_name, "parenttype": "Fiche Budgetaire"},
        fields=["numero_rejet", "date_rejet", "motif_rejet",
                "rejet_definitif", "date_correction", "corrige_par"],
        order_by="numero_rejet asc",
    )
