frappe.ready(function() {
    // Masquer la sidebar et le toggle au départ
    $('.sidebar-toggle-placeholder, .layout-side-section, .list-sidebar').hide();

    // Bouton pour tester la réouverture (optionnel)
    $('<button id="toggleSidebarBtn">Toggle Sidebar</button>')
        .appendTo('body')
        .css({
            position: 'fixed',
            top: '10px',
            right: '10px',
            zIndex: 9999
        })
        .on('click', function() {
            $('.sidebar-toggle-placeholder').toggle(); // toggle natif
        });

    // Observer les changements du DOM pour sidebars dynamiques
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            // Masquer la sidebar uniquement au chargement initial ou si besoin
            if ($('.layout-side-section').length && !$('.layout-side-section').is(':visible')) {
                $('.layout-side-section, .list-sidebar').hide();
            }
        });
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
});

