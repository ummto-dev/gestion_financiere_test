# Copyright (c) 2026, Cellule Developpement UMMTO and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate

class AnneeBudgetaire(Document):
    def validate(self):
        # 1. Contrôles de dates
        self.validate_dates()

        # 2. Vérifier qu'une seule année est active pour cette faculté
        self.validate_unique_active_year()

    def validate_dates(self):
        # Vérification que l'année des dates correspond au champ 'annee'
        if self.annee:
            if getdate(self.date_ouverture).year != int(self.annee):
                frappe.throw(_("La date d'ouverture doit être en {0}").format(self.annee))

            if self.date_cloture and getdate(self.date_cloture).year != int(self.annee):
                frappe.throw(_("La date de clôture doit être en {0}").format(self.annee))

        # Vérification de l'ordre chronologique
        if self.date_ouverture and self.date_cloture:
            if getdate(self.date_cloture) <= getdate(self.date_ouverture):
                frappe.throw(_("La date de clôture doit être postérieure à la date d'ouverture"))

        # Si l'année est inactive, la date de clôture est obligatoire
        if not self.active and not self.date_cloture:
            frappe.throw(_("Veuillez saisir une date de clôture car cette année budgétaire n'est plus active."))

    def validate_unique_active_year(self):
        if self.active:
            # On cherche s'il existe une autre année active pour la même faculté
            existing_active = frappe.db.exists('Annee Budgetaire', {
                'faculte': self.faculte,
                'active': 1,
                'name': ['!=', self.name]  # Exclure le document actuel
            })

            if existing_active:
                frappe.throw(_("Il existe déjà une année budgétaire active pour la faculté {0}. "
                               "Veuillez clôturer l'année précédente avant d'en activer une nouvelle.")
                             .format(self.faculte))
