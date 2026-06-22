# # Copyright (c) 2026, Cellule Developpement UMMTO and contributors
# # For license information, please see license.txt


# import frappe
# from frappe.model.document import Document

# class Article(Document):
#     def autoname(self):
#         """
#         Génère un nom unique pour l'article en utilisant l'ID du chapitre comme base
#         Format: [ID_Chapitre]-[Code_Article] ou [ID_Chapitre]-[Code_Article]-[Partie]
#         """
#         # ✅ Génère un nom SEULEMENT pour les nouveaux documents
#         if not self.name or self.name.startswith('new-'):
#             # Récupérer l'ID du chapitre (qui contient déjà toutes les informations)
#             chapitre = frappe.get_doc("Chapitre", self.chapitre)
#             chapitre_id = chapitre.name  # ex: 2026-32324-FR-26-22.01
            
#             # Formater le code article (toujours sur 2 chiffres)
#             article_code = str(self.code_article).zfill(2)
            
#             # Construction de l'ID
#             if self.has_partition and self.code_partie:
#                 # Ajouter la partie (sur 2 chiffres)
#                 partie_code = str(self.code_partie).zfill(2)
#                 self.name = f"{chapitre_id}-{article_code}-{partie_code}"
#             else:
#                 # Sans partition
#                 self.name = f"{chapitre_id}-{article_code}"
    
# # Copyright (c) 2026, Cellule Developpement UMMTO and contributors
# # For license information, please see license.txt

import frappe
from frappe.model.document import Document

class Article(Document):
    def autoname(self):
        """
        Génère un nom unique pour l'article en utilisant l'ID du chapitre comme base
        Format: [ID_Chapitre]-[Code_Article] ou [ID_Chapitre]-[Code_Article]-[Partie]
        """
        if not self.name or self.name.startswith('new-'):
            chapitre = frappe.get_doc("Chapitre", self.chapitre)
            chapitre_id = chapitre.name
            article_code = str(self.code_article).zfill(2)
            if self.has_partition and self.code_partie:
                partie_code = str(self.code_partie).zfill(2)
                self.name = f"{chapitre_id}-{article_code}-{partie_code}"
            else:
                self.name = f"{chapitre_id}-{article_code}"
    
    # Supprimé la méthode validate qui causait l'erreur
    # La validation d'unicité est déjà gérée par Frappe
