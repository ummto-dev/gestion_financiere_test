# Copyright (c) 2026, Cellule Developpement UMMTO
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

class Cloturebudgetaire(Document):
    def validate(self):
        # Vérifier cohérence des dates si les deux sont renseignées
        if self.date_ouverture and self.date_cloture:
            date_ouverture = getdate(self.date_ouverture)
            date_cloture = getdate(self.date_cloture)

            if date_cloture <= date_ouverture:
                frappe.throw("La Date de Clôture doit être strictement postérieure à la Date d'Ouverture.")

            # Vérifier que la clôture est en décembre
            if date_cloture.month != 12:
                frappe.msgprint("Règle de gestion : la clôture doit généralement s'effectuer en décembre.")

        # Vérifier cohérence avec le status
        if self.status == "Clôturée":
            if not self.date_cloture:
                frappe.throw("Veuillez saisir la Date de Clôture car le budget est marqué comme Clôturé.")
        # Si status = En cours → pas de contrainte supplémentaire
