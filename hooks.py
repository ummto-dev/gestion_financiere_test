app_title = "Gestion Financiere"
app_publisher = "Cellule Developpement UMMTO"
#app_favicon = "/assets/gestion_financiere/image/favicon.ico"
app_description = "Application de gestion financiere universitaire basee sur ERPNext"
app_email = "systeme@ummto.dz"
app_license = "mit"
#app_include_css = "/assets/gestion_financiere/css/custom.css",
#app_include_js = "/assets/gestion_financiere/js/global_list.js"
app_include_js = "/assets/gestion_financiere/js/menunav.js"
# Inclure le CSS dans toutes les pages
app_include_css = "/assets/gestion_financiere/css/custom_logo.css"


fixtures = [
    "Custom Field",
    "Property Setter",
    "Workflow",
    "Workspace",
    "Client Script",
    "Server Script",
    "Faculte",
    "Annee Budgetaire",
    "Budget Article",
    "Budget Chapitre",
    "Fournisseur",
    "Etudiants",
    "Personnel Administratif",
    "Section",
    "Titre",
    "Chapitre",
    "Article",
    "Fiche Budgetaire",
    "Enseignant",
    "Bon Commande",
    "Convention",
    "Depense Interne",
    "Facture Fournisseur",
    "Fiche Transfert Credit",
    "Frais Mission",
    "Mandat Paiement",
    "Situation Paiement",
    "Custom HTML Block",
    "Print Format",
    "Property Setter",
    "Budget Global",
    "Company",
    "Cost Center"
]






# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "gestion_financiere",
# 		"logo": "/assets/gestion_financiere/logo.png",
# 		"title": "Gestion Financière",
# 		"route": "/gestion_financiere",
# 		"has_permission": "gestion_financiere.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/gestion_financiere/css/gestion_financiere.css"
# app_include_js = "/assets/gestion_financiere/js/gestion_financiere.js"

# include js, css files in header of web template
# web_include_css = "/assets/gestion_financiere/css/gestion_financiere.css"
# web_include_js = "/assets/gestion_financiere/js/gestion_financiere.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "gestion_financiere/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "gestion_financiere/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "gestion_financiere.utils.jinja_methods",
# 	"filters": "gestion_financiere.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "gestion_financiere.install.before_install"
# after_install = "gestion_financiere.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "gestion_financiere.uninstall.before_uninstall"
# after_uninstall = "gestion_financiere.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "gestion_financiere.utils.before_app_install"
# after_app_install = "gestion_financiere.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "gestion_financiere.utils.before_app_uninstall"
# after_app_uninstall = "gestion_financiere.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "gestion_financiere.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"gestion_financiere.tasks.all"
# 	],
# 	"daily": [
# 		"gestion_financiere.tasks.daily"
# 	],
# 	"hourly": [
# 		"gestion_financiere.tasks.hourly"
# 	],
# 	"weekly": [
# 		"gestion_financiere.tasks.weekly"
# 	],
# 	"monthly": [
# 		"gestion_financiere.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "gestion_financiere.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "gestion_financiere.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "gestion_financiere.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["gestion_financiere.utils.before_request"]
# after_request = ["gestion_financiere.utils.after_request"]

# Job Events
# ----------
# before_job = ["gestion_financiere.utils.before_job"]
# after_job = ["gestion_financiere.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"gestion_financiere.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

