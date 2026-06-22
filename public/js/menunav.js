// ─────────────────────────────────────────────
//  FBSBA Sidebar — v2.3
// ─────────────────────────────────────────────

(function () {

  function el(tag, props, children) {
    var node = document.createElement(tag);
    Object.keys(props || {}).forEach(function (key) {
      if (key === 'className') {
        node.className = props[key];
      } else if (key === 'style') {
        node.style.cssText = props[key];
      } else {
        node.setAttribute(key, props[key]);
      }
    });
    [].concat(children || []).forEach(function (child) {
      if (typeof child === 'string') {
        node.appendChild(document.createTextNode(child));
      } else if (child instanceof Node) {
        node.appendChild(child);
      }
    });
    return node;
  }

  // ══════════════════════════════════════════
  //  VERROU + CACHE
  // ══════════════════════════════════════════

  var _building = false;
  var _cachedLabel = null;

  // ══════════════════════════════════════════
  //  DONNÉES
  // ══════════════════════════════════════════

  var MENUS = [
    {
      icon: '💰', label: 'Budget',
      items: [
        { icon: '📊', bg: '#121a24', label: 'Budget Article',         sub: 'Dotations par article',       list: '/app/budget-article',         new_: '/app/budget-article/new-budget-article-1' },
        { icon: '📋', bg: '#dcfce7', label: 'Budget Chapitre',        sub: 'Dotations par chapitre',      list: '/app/budget-chapitre',        new_: '/app/budget-chapitre/new-budget-chapitre-1' },
        { icon: '🔄', bg: '#fef3c7', label: 'Fiche Transfert Crédit', sub: 'Transferts de crédits',       list: '/app/fiche-transfert-credit', new_: '/app/fiche-transfert-credit/new-fiche-transfert-credit-1' },
        { icon: '📑', bg: '#ede9fe', label: 'Situation Paiement',     sub: 'Suivi paiements conventions', list: '/app/situation-paiement',     new_: '/app/situation-paiement/new-situation-paiement-1' },
      ]
    },
    {
      icon: '💸', label: 'Dépense',
      items: [
        { icon: '💸', bg: '#ffe4e6', label: 'Dépense Interne',      sub: 'Dépenses A posteriori',        list: '/app/depense-interne',        new_: '/app/depense-interne/new-depense-interne-1' },
        { icon: '📄', bg: '#dcfce7', label: 'Fiche Budgétaire',     sub: 'Fiches A priori / Provisions', list: '/app/fiche-budgetaire',       new_: '/app/fiche-budgetaire/new-fiche-budgetaire-1' },
        { icon: '✈️', bg: '#fef3c7', label: 'Frais Mission',        sub: 'Missions et déplacements',     list: '/app/frais-mission',          new_: '/app/frais-mission/new-frais-mission-1' },
        { icon: '🛒', bg: '#dbeafe', label: 'Bon Commande',         sub: 'Bons de commande',             list: '/app/bon-commande',           new_: '/app/bon-commande/new-bon-commande-1' },
        { icon: '🧾', bg: '#fce7f3', label: 'Facture Fournisseur',  sub: 'Factures reçues',              list: '/app/facture-fournisseur',    new_: '/app/facture-fournisseur/new-facture-fournisseur-1' },
        { icon: '📃', bg: '#f0fdf4', label: 'Convention',           sub: 'Conventions et contrats',      list: '/app/convention',             new_: '/app/convention/new-convention-1' },
        { icon: '🏦', bg: '#ede9fe', label: 'Mandat Paiement',      sub: 'Mandats de paiement',          list: '/app/mandat-paiement',        new_: '/app/mandat-paiement/new-mandat-paiement-1' },
      ]
    },
    {
      icon: '👥', label: 'Bénéficiaires',
      items: [
        { icon: '🏢', bg: '#fef3c7', label: 'Fournisseur',             sub: 'Prestataires & fournisseurs', list: '/app/fournisseur',             new_: '/app/fournisseur/new-fournisseur-1' },
        { icon: '🎓', bg: '#ede9fe', label: 'Enseignant',              sub: 'Corps enseignant',            list: '/app/enseignant',              new_: '/app/enseignant/new-enseignant-1' },
        { icon: '🎒', bg: '#fce7f3', label: 'Etudiants',               sub: 'Étudiants',                   list: '/app/etudiants',               new_: '/app/etudiants/new-etudiants-1' },
        { icon: '👔', bg: '#e0f2fe', label: 'Personnel Administratif', sub: 'Personnel administratif',     list: '/app/personnel-administratif', new_: '/app/personnel-administratif/new-personnel-administratif-1' },
      ]
    },
    {
      icon: '⚙️', label: 'Référentiels',
      items: [
        { icon: '📁', bg: '#f3f4f6', label: 'Section',          sub: 'Sections budgétaires',      list: '/app/section',          new_: '/app/section/new-section-1' },
        { icon: '📌', bg: '#dbeafe', label: 'Titre',            sub: 'Titres budgétaires',        list: '/app/titre',            new_: '/app/titre/new-titre-1' },
        { icon: '🗂️', bg: '#dcfce7', label: 'Chapitre',        sub: 'Chapitres budgétaires',     list: '/app/chapitre',         new_: '/app/chapitre/new-chapitre-1' },
        { icon: '📝', bg: '#fef3c7', label: 'Article',          sub: 'Articles budgétaires',      list: '/app/article',          new_: '/app/article/new-article-1' },
        { icon: '🏛️', bg: '#ede9fe', label: 'Faculte',         sub: 'Facultés / Établissements', list: '/app/faculte',          new_: '/app/faculte/new-faculte-1' },
        { icon: '📅', bg: '#fce7f3', label: 'Annee Budgetaire', sub: 'Années budgétaires',        list: '/app/annee-budgetaire', new_: '/app/annee-budgetaire/new-annee-budgetaire-1' },
      ]
    },
  ];

  // ══════════════════════════════════════════
  //  CSS
  // ══════════════════════════════════════════

  function injectCSS() {
    if (document.getElementById('fbsba-nav-css')) return;
    var style = el('style', { id: 'fbsba-nav-css' });
    style.textContent = `
#fbsba-sidebar {
    position: fixed; left: 0; top: 50%;
    transform: translateY(-50%);
    z-index: 9998;
    display: flex; flex-direction: column;
    background: #1a2332;
    border-radius: 0 14px 14px 0;
    box-shadow: 4px 0 20px rgba(0,0,0,.25);
    max-height: 85vh; overflow: hidden;
    width: 46px; transition: width .25s ease;
    font-family: 'Segoe UI', sans-serif;
}
#fbsba-sidebar:hover { width: 240px; overflow-y: auto; scrollbar-width: thin; scrollbar-color: #334155 transparent; }
#fbsba-sidebar::-webkit-scrollbar { width: 4px; }
#fbsba-sidebar::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }

.fbsba-sb-brand { display: flex; align-items: center; gap: 10px; padding: 12px 10px 10px; border-bottom: 1px solid rgba(255,255,255,.08); text-decoration: none; overflow: hidden; flex-shrink: 0; }
.fbsba-sb-brand-icon { font-size: 18px; flex-shrink: 0; }
.fbsba-sb-brand-label { font-size: 12px; font-weight: 800; color: #3b82f6; letter-spacing: .06em; white-space: nowrap; opacity: 0; transition: opacity .2s .05s; }
#fbsba-sidebar:hover .fbsba-sb-brand-label { opacity: 1; }

.fbsba-sb-section { display: flex; align-items: center; gap: 10px; padding: 8px 10px 4px; overflow: hidden; flex-shrink: 0; }
.fbsba-sb-section-icon { font-size: 15px; flex-shrink: 0; opacity: .5; }
.fbsba-sb-section-label { font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: .08em; white-space: nowrap; opacity: 0; transition: opacity .2s .05s; }
#fbsba-sidebar:hover .fbsba-sb-section-label { opacity: 1; }

.fbsba-sb-item { display: flex; align-items: center; gap: 10px; padding: 7px 10px; cursor: pointer; color: rgba(255,255,255,.7); transition: all .15s; white-space: nowrap; overflow: hidden; text-decoration: none; flex-shrink: 0; border-left: 3px solid transparent; }
.fbsba-sb-item:hover { color: #fff; background: rgba(59,130,246,.12); border-left-color: #3b82f6; text-decoration: none; }

.fbsba-sb-icon-wrap { width: 26px; height: 26px; border-radius: 7px; display: flex; align-items: center; justify-content: center; font-size: 13px; flex-shrink: 0; }
.fbsba-sb-item-label { display: flex; flex-direction: column; opacity: 0; transition: opacity .2s .05s; }
#fbsba-sidebar:hover .fbsba-sb-item-label { opacity: 1; }
.fbsba-sb-item-name { font-size: 12px; font-weight: 600; color: #fff; }
.fbsba-sb-item-sub  { font-size: 10px; color: #64748b; margin-top: 1px; }

.fbsba-sb-actions { display: none; gap: 5px; padding: 2px 10px 6px 46px; flex-shrink: 0; }
#fbsba-sidebar:hover .fbsba-sb-actions { display: flex; }
.fbsba-sb-action { font-size: 10px; font-weight: 600; padding: 2px 9px; border-radius: 20px; text-decoration: none; transition: all .12s; }
.fbsba-sb-action.list { background: rgba(59,130,246,.15); color: #93c5fd; border: 1px solid rgba(59,130,246,.3); }
.fbsba-sb-action.list:hover { background: rgba(59,130,246,.3); color: #fff; text-decoration: none; }
.fbsba-sb-action.new  { background: rgba(34,197,94,.12);  color: #86efac; border: 1px solid rgba(34,197,94,.25); }
.fbsba-sb-action.new:hover  { background: rgba(34,197,94,.25);  color: #fff; text-decoration: none; }

.fbsba-sb-divider { height: 1px; background: rgba(255,255,255,.07); margin: 3px 10px; flex-shrink: 0; }
.fbsba-sb-logout:hover { background: rgba(239,68,68,.12) !important; border-left-color: #ef4444 !important; }

.fbsba-sb-home { display: flex; align-items: center; gap: 10px; padding: 10px 10px 12px; border-top: 1px solid rgba(255,255,255,.08); text-decoration: none; overflow: hidden; flex-shrink: 0; margin-top: auto; }
.fbsba-sb-home:hover { text-decoration: none; }
.fbsba-sb-home-icon { font-size: 17px; flex-shrink: 0; }
.fbsba-sb-home-label { font-size: 12px; font-weight: 600; color: rgba(255,255,255,.6); white-space: nowrap; opacity: 0; transition: opacity .2s .05s; }
#fbsba-sidebar:hover .fbsba-sb-home-label { opacity: 1; }
#fbsba-sidebar:hover .fbsba-sb-home-label:hover { color: #fff; }

#fbsba-logout-overlay {
    position: fixed; inset: 0;
    background: rgba(0,0,0,.45);
    z-index: 99999;
    display: flex; align-items: center; justify-content: center;
}
#fbsba-logout-modal {
    background: #1a2332;
    border: 1px solid rgba(255,255,255,.1);
    border-radius: 14px;
    padding: 28px 32px;
    width: 320px;
    text-align: center;
    box-shadow: 0 8px 40px rgba(0,0,0,.5);
}
#fbsba-logout-modal .fbsba-modal-icon  { font-size: 36px; margin-bottom: 12px; }
#fbsba-logout-modal .fbsba-modal-title { font-size: 15px; font-weight: 700; color: #fff; margin-bottom: 6px; }
#fbsba-logout-modal .fbsba-modal-sub   { font-size: 12px; color: #64748b; margin-bottom: 22px; }
#fbsba-logout-modal .fbsba-modal-actions { display: flex; gap: 10px; justify-content: center; }
.fbsba-modal-btn { padding: 7px 22px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; transition: all .15s; }
.fbsba-modal-btn.cancel  { background: rgba(255,255,255,.08); color: #94a3b8; }
.fbsba-modal-btn.cancel:hover  { background: rgba(255,255,255,.14); color: #fff; }
.fbsba-modal-btn.confirm { background: #ef4444; color: #fff; }
.fbsba-modal-btn.confirm:hover { background: #dc2626; }
    `;
    document.head.appendChild(style);
  }

  // ══════════════════════════════════════════
  //  CONSTRUCTION SIDEBAR
  // ══════════════════════════════════════════

  function buildSidebar(brandLabel) {
    if (document.getElementById('fbsba-sidebar')) return;

    var sidebar = el('div', { id: 'fbsba-sidebar' });

    sidebar.appendChild(
      el('a', { className: 'fbsba-sb-brand', href: '/app/centre-financier' }, [
        el('span', { className: 'fbsba-sb-brand-icon' }, '🏛'),
        el('span', { className: 'fbsba-sb-brand-label' }, brandLabel),
      ])
    );

    sidebar.appendChild(buildNavItem('🏠', '#dbeafe', 'Dashboard', 'Centre financier', '/app/centre-financier'));
    sidebar.appendChild(el('div', { className: 'fbsba-sb-divider' }));

    MENUS.forEach(function (menu, idx) {
      if (idx > 0) sidebar.appendChild(el('div', { className: 'fbsba-sb-divider' }));
      sidebar.appendChild(
        el('div', { className: 'fbsba-sb-section' }, [
          el('span', { className: 'fbsba-sb-section-icon' }, menu.icon),
          el('span', { className: 'fbsba-sb-section-label' }, menu.label),
        ])
      );
      menu.items.forEach(function (item) {
        var wrap = el('div', {});
        wrap.appendChild(buildNavItem(item.icon, item.bg, item.label, item.sub, item.list));
        wrap.appendChild(buildActions(item.list, item.new_));
        sidebar.appendChild(wrap);
      });
    });

    sidebar.appendChild(
      el('a', { className: 'fbsba-sb-home', href: '/app/centre-financier' }, [
        el('span', { className: 'fbsba-sb-home-icon' }, '🏠'),
        el('span', { className: 'fbsba-sb-home-label' }, 'Dashboard'),
      ])
    );

    sidebar.appendChild(el('div', { className: 'fbsba-sb-divider' }));
    var logoutBtn = el('div', { className: 'fbsba-sb-item fbsba-sb-logout', title: 'Se déconnecter' }, [
      el('div', { className: 'fbsba-sb-icon-wrap', style: 'background:#3b1a1a' }, '⏻'),
      el('div', { className: 'fbsba-sb-item-label' }, [
        el('span', { className: 'fbsba-sb-item-name', style: 'color:#f87171' }, 'Déconnexion'),
        el('span', { className: 'fbsba-sb-item-sub' }, 'Quitter la session'),
      ]),
    ]);
    logoutBtn.addEventListener('click', function () { showLogoutModal(); });
    sidebar.appendChild(logoutBtn);

    document.body.appendChild(sidebar);
  }

  function buildNavItem(icon, bg, name, sub, href) {
    return el('a', { className: 'fbsba-sb-item', href: href, title: name }, [
      el('div', { className: 'fbsba-sb-icon-wrap', style: 'background:' + bg }, icon),
      el('div', { className: 'fbsba-sb-item-label' }, [
        el('span', { className: 'fbsba-sb-item-name' }, name),
        el('span', { className: 'fbsba-sb-item-sub'  }, sub),
      ]),
    ]);
  }

  function buildActions(listHref, newHref) {
    return el('div', { className: 'fbsba-sb-actions' }, [
      el('a', { className: 'fbsba-sb-action list', href: listHref }, '📋 Lister'),
      el('a', { className: 'fbsba-sb-action new',  href: newHref  }, '＋ Nouveau'),
    ]);
  }

  // ══════════════════════════════════════════
  //  DÉCONNEXION
  // ══════════════════════════════════════════

  function showLogoutModal() {
    if (document.getElementById('fbsba-logout-overlay')) return;

    var overlay    = el('div', { id: 'fbsba-logout-overlay' });
    var btnCancel  = el('button', { className: 'fbsba-modal-btn cancel'  }, 'Annuler');
    var btnConfirm = el('button', { className: 'fbsba-modal-btn confirm' }, 'Se déconnecter');

    var modal = el('div', { id: 'fbsba-logout-modal' }, [
      el('div', { className: 'fbsba-modal-icon'    }, '🔐'),
      el('div', { className: 'fbsba-modal-title'   }, 'Déconnexion'),
      el('div', { className: 'fbsba-modal-sub'     }, 'Voulez-vous vraiment quitter la session ?'),
      el('div', { className: 'fbsba-modal-actions' }, [btnCancel, btnConfirm]),
    ]);

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    overlay.addEventListener('click', function (e) { if (e.target === overlay) overlay.remove(); });
    btnCancel.addEventListener('click', function () { overlay.remove(); });
    btnConfirm.addEventListener('click', function () {
      btnConfirm.textContent = 'Déconnexion…';
      btnConfirm.disabled = true;
      frappe.call({ method: 'logout' })
        .then(function ()  { window.location.href = '/login'; })
        .catch(function () { window.location.href = '/login'; });
    });
  }

  // ══════════════════════════════════════════
  //  UTILISATEUR — Label avec cache
  // ══════════════════════════════════════════

  function parseFaculteLabel(faculte) {
    if (!faculte || typeof faculte !== 'string') return 'FBSBA';
    var parts = faculte.split('-');
    return parts.length > 1 ? parts.slice(1).join('-') : faculte;
  }

  function loadUserAndBuild() {
    if (document.getElementById('fbsba-sidebar')) return;
    if (_building) return;
    _building = true;

    // Label déjà en cache → injection immédiate sans appel réseau
    if (_cachedLabel) {
      injectCSS();
      buildSidebar(_cachedLabel);
      patchLogoRedirect();
      _building = false;
      return;
    }

    var isAdmin = frappe.user_roles && frappe.user_roles.includes('Administrator');

    if (isAdmin) {
      _cachedLabel = 'Admin';
      injectCSS();
      buildSidebar(_cachedLabel);
      patchLogoRedirect();
      _building = false;
      return;
    }

    frappe.db.get_doc('User', frappe.session.user)
      .then(function (user) {
        _cachedLabel = parseFaculteLabel(user.faculte);
        injectCSS();
        buildSidebar(_cachedLabel);
        patchLogoRedirect();
      })
      .catch(function (err) {
        console.warn('[FBSBA] Impossible de récupérer l\'utilisateur.', err);
      })
      .finally(function () {
        _building = false;
      });
  }

  // ══════════════════════════════════════════
  //  LOGO REDIRECT
  // ══════════════════════════════════════════

  function patchLogoRedirect() {
    var logo = document.querySelector('.navbar-brand.navbar-home');
    if (logo) {
      logo.style.cursor = 'pointer';
      logo.addEventListener('click', function (e) {
        e.preventDefault();
        window.location.href = '/app/centre-financier';
      });
    }
  }

  // ══════════════════════════════════════════
  //  ATTENTE FRAPPE
  // ══════════════════════════════════════════

  function waitForFrappe(callback, maxRetries) {
    maxRetries = maxRetries || 30;
    var tries = 0;
    var interval = setInterval(function () {
      tries++;
      if (
        typeof frappe !== 'undefined' &&
        frappe.session &&
        frappe.session.user &&
        frappe.session.user !== 'Guest' &&
        typeof frappe.db !== 'undefined'
      ) {
        clearInterval(interval);
        callback();
      } else if (tries >= maxRetries) {
        clearInterval(interval);
        console.warn('[FBSBA] frappe.session non disponible après ' + maxRetries + ' tentatives.');
      }
    }, 300);
  }

  // ══════════════════════════════════════════
  //  POINT D'ENTRÉE
  // ══════════════════════════════════════════

  function init() {

    // MutationObserver permanent
    var observer = new MutationObserver(function () {
      if (!document.getElementById('fbsba-sidebar')) {
        loadUserAndBuild();
      }
    });

    if (document.body) {
      waitForFrappe(function () {
        loadUserAndBuild();

        // Hook natif Frappe router
        frappe.router.on('change', function () {
          if (!document.getElementById('fbsba-sidebar')) {
            loadUserAndBuild();
          }
        });

        // Observer sur body
        observer.observe(document.body, { childList: true, subtree: false });

        // Intervalle de secours
        setInterval(function () {
          if (!document.getElementById('fbsba-sidebar')) {
            loadUserAndBuild();
          }
        }, 800);
      });
    } else {
      var bodyObserver = new MutationObserver(function (_, obs) {
        if (document.body) {
          obs.disconnect();
          waitForFrappe(function () {
            loadUserAndBuild();
            frappe.router.on('change', function () {
              if (!document.getElementById('fbsba-sidebar')) {
                loadUserAndBuild();
              }
            });
            observer.observe(document.body, { childList: true, subtree: false });
            setInterval(function () {
              if (!document.getElementById('fbsba-sidebar')) {
                loadUserAndBuild();
              }
            }, 800);
          });
        }
      });
      bodyObserver.observe(document.documentElement, { childList: true, subtree: true });
    }
  }

  init();

})();

// ── Cacher les éléments du menu utilisateur pour les non-admins ──
setInterval(function () {
  var isAdmin = frappe.user_roles && frappe.user_roles.includes('Administrator');
  if (!isAdmin && $('#toolbar-user').hasClass('show')) {
    $('#toolbar-user .dropdown-item').each(function () {
      var text = $(this).text().trim();
      var allowed = [
        'Mon profil',
        'Changer l\'affichage en pleine largeur',
        'Basculer le thème',
        'Log out',
        'My Profile',
        'Toggle Full Width',
        'Toggle Theme',
        'Log out',
      ];
      if (!allowed.includes(text)) {
        $(this).hide();
      }
    });
    $('#toolbar-user .dropdown-divider').hide();
  }
}, 200);