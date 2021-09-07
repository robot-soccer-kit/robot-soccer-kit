var current_tab = null;

$(document).ready(function() {
    function setTab(page) {
        current_tab = page;
        
        $('.page').hide();
        $('.page-'+page).show();
        $('.nav-item a').removeClass('active');
        $('.nav-item[rel="'+page+'"] a').addClass('active');
    }

    $('.nav-item.nav-tab').click(function() {
        setTab($(this).attr('rel'));
    });

    setTab('control');
});