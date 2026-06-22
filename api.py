import frappe

@frappe.whitelist()
def get_suivi_global():
    return frappe.db.sql("""
        SELECT 
            a.name          AS article,
            a.intitule_article AS intitule_article,
            c.name          AS chapitre,
            c.intitule      AS intitule_chapitre,

            IFNULL(ba.montant, 0) AS budget,

            -- Engagé : Fiche Budgetaire (type Dépense, statuts actifs)
            IFNULL((
                SELECT SUM(fb.montant_operation)
                FROM `tabFiche Budgetaire` fb
                WHERE fb.article = a.name
                  AND fb.status NOT IN ('Brouillon', 'Archivé')
                  AND fb.docstatus != 2
            ), 0) AS engage,

            -- Payé : Mandat Paiement admis
            IFNULL((
                SELECT SUM(mp.montant_total)
                FROM `tabMandat Paiement` mp
                WHERE mp.article = a.name
                  AND mp.status_admission = 'Admis'
                  AND mp.docstatus != 2
            ), 0) AS paye,

            -- Dépensé : Depense Interne validées
            IFNULL((
                SELECT SUM(di.montant_total)
                FROM `tabDepense Interne` di
                WHERE di.article = a.name
                  AND di.status NOT IN ('Brouillon')
                  AND di.docstatus != 2
            ), 0) AS depense

        FROM `tabArticle` a
        LEFT JOIN `tabChapitre` c 
            ON a.chapitre = c.name
        LEFT JOIN `tabBudget Article` ba 
            ON ba.article = a.name

        WHERE ba.montant IS NOT NULL
          AND ba.montant > 0

        ORDER BY c.name, a.name
    """, as_dict=1)