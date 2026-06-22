import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class FraisMission(Document):
    
    def validate(self):
        """Validations."""
        self._validate_doublons_beneficiaires()
        self._validate_type_missionnaire_coherence()
        self._set_type_personne_doctype()
        self._validate_type_compte_coherence()
        self._calculate_montant_total()
        self._set_type_compte_info()

    def _validate_doublons_beneficiaires(self):
        """Empêche d'ajouter la même personne plusieurs fois."""
        if not self.table_beneficiaires:
            return
        
        personnes_vues = {}
        
        for benef in self.table_beneficiaires:
            if not benef.personne:
                continue
            
            if benef.personne in personnes_vues:
                frappe.throw(_(
                    "❌ <b>Doublon détecté</b><br><br>"
                    "La personne <b>{0}</b> apparaît plusieurs fois dans la liste.<br><br>"
                    "Première occurrence : Ligne {1}<br>"
                    "Doublon : Ligne {2}<br><br>"
                    "Chaque personne ne peut être ajoutée qu'une seule fois."
                ).format(
                    benef.nom_prenom or benef.personne,
                    personnes_vues[benef.personne],
                    benef.idx
                ))
            
            personnes_vues[benef.personne] = benef.idx
    
    def _validate_type_missionnaire_coherence(self):
        """Vérifie que tous les bénéficiaires correspondent au type_missionnaire."""
        if not self.type_missionnaire or not self.table_beneficiaires:
            return
        
        # Mapping type_missionnaire → doctype
        doctype_attendu = self._get_doctype_from_type_missionnaire()
        
        # Vérifier que tous les bénéficiaires sont du bon type
        for benef in self.table_beneficiaires:
            if benef.type_personne_doctype and benef.type_personne_doctype != doctype_attendu:
                frappe.throw(_(
                    "⚠️ Incohérence détectée !<br><br>"
                    "Type Missionnaire : <b>{0}</b><br>"
                    "Doctype attendu : <b>{1}</b><br>"
                    "Doctype trouvé : <b>{2}</b><br><br>"
                    "Tous les bénéficiaires doivent être du même type."
                ).format(self.type_missionnaire, doctype_attendu, benef.type_personne_doctype))
    
    def _set_type_personne_doctype(self):
        """Définit automatiquement le type_personne_doctype pour chaque ligne."""
        if not self.type_missionnaire or not self.table_beneficiaires:
            return
        
        doctype = self._get_doctype_from_type_missionnaire()
        
        for benef in self.table_beneficiaires:
            if not benef.type_personne_doctype:
                benef.type_personne_doctype = doctype
    
    def _get_doctype_from_type_missionnaire(self):
        """Retourne le doctype correspondant au type_missionnaire."""
        mapping = {
            "Etudiants": "Etudiants",
            "Enseignant": "Enseignant",
            "Personnel Administratif": "Personnel Administratif"
        }
        return mapping.get(self.type_missionnaire, "")
    
    def _validate_type_compte_coherence(self):
        """
        Validation conditionnelle des types de compte.
        - A Posteriori : BLOQUER si mixte
        - A Priori : AVERTIR si mixte
        """
        if not self.table_beneficiaires:
            return
        
        types_compte = set([
            b.type_compte 
            for b in self.table_beneficiaires 
            if b.type_compte
        ])
        
        if len(types_compte) > 1:
            if self.article:
                type_article = frappe.db.get_value("Budget Article", self.article, "type")
                
                if type_article == "A posteriori":
                    # BLOQUER pour A Posteriori
                    nb_banque = len([b for b in self.table_beneficiaires if b.type_compte == "Banque"])
                    nb_ccp = len([b for b in self.table_beneficiaires if b.type_compte == "CCP"])
                    
                    frappe.throw(_(
                        "⚠️ <b>Article À Posteriori</b><br><br>"
                        "Tous les bénéficiaires doivent avoir le <b>même type de compte</b>.<br><br>"
                        "Types trouvés :<br>"
                        "- {0} avec <b>Banque</b><br>"
                        "- {1} avec <b>CCP</b><br><br>"
                        "💡 <i>Solution : Créez 2 Frais Mission séparés.</i>"
                    ).format(nb_banque, nb_ccp))
                
                elif type_article == "A priori":
                    # AVERTISSEMENT pour A Priori
                    frappe.msgprint(_(
                        "ℹ️ <b>Types de compte mixtes</b><br><br>"
                        "Ce Frais Mission contient Banque ET CCP.<br>"
                        "Lors du mandatement, 2 mandats séparés seront créés."
                    ), alert=True, indicator='blue')
    
    def _set_type_compte_info(self):
        """Détermine les types de compte présents."""
        if not self.table_beneficiaires:
            self.type_compte_unique = ""
            return
        
        types_compte = set([
            b.type_compte 
            for b in self.table_beneficiaires 
            if b.type_compte
        ])
        
        if len(types_compte) == 1:
            self.type_compte_unique = list(types_compte)[0]
        elif len(types_compte) > 1:
            self.type_compte_unique = "Mixte"
        else:
            self.type_compte_unique = ""
    
    def _calculate_montant_total(self):
        """Calcule le montant total."""
        if not self.table_beneficiaires:
            self.montant_total = 0
            return
        
        total = sum(flt(b.montant_mission) for b in self.table_beneficiaires)
        self.montant_total = total


@frappe.whitelist()
def get_doctype_from_type_missionnaire(type_missionnaire):
    """Retourne le doctype correspondant."""
    mapping = {
        "Etudiants": "Etudiants",
        "Enseignant": "Enseignant",
        "Personnel Administratif": "Personnel Administratif"
    }
    return mapping.get(type_missionnaire, "")
