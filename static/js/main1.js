(function ($) {
    "use strict";

    // Spinner – hide when the whole page has loaded
    $(window).on('load', function () {
        $('#spinner').removeClass('show');
    });

    // Initiate the wowjs
    new WOW().init();

    // Sticky Navbar & Back-to-top – throttled with requestAnimationFrame
    var ticking = false;
    $(window).on('scroll', function () {
        if (!ticking) {
            window.requestAnimationFrame(function () {
                var scrollTop = $(window).scrollTop() || 0;

                // Sticky navbar
                if (scrollTop > 45) {
                    $('.navbar').addClass('sticky-top shadow-sm');
                } else {
                    $('.navbar').removeClass('sticky-top shadow-sm');
                }

                // Back-to-top visibility
                if (scrollTop > 100) {
                    $('.back-to-top').fadeIn('slow');
                } else {
                    $('.back-to-top').fadeOut('slow');
                }

                ticking = false;
            });
            ticking = true;
        }
    });

    // Dropdown on mouse hover – desktop only, with resize debounce
    const $dropdown = $(".dropdown");
    const $dropdownToggle = $(".dropdown-toggle");
    const $dropdownMenu = $(".dropdown-menu");
    const showClass = "show";
    var resizeTimer;

    $(window).on("load resize", function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            if (window.matchMedia("(min-width: 992px)").matches) {
                $dropdown.hover(
                    function () {
                        const $this = $(this);
                        $this.addClass(showClass);
                        $this.find($dropdownToggle).attr("aria-expanded", "true");
                        $this.find($dropdownMenu).addClass(showClass);
                    },
                    function () {
                        const $this = $(this);
                        $this.removeClass(showClass);
                        $this.find($dropdownToggle).attr("aria-expanded", "false");
                        $this.find($dropdownMenu).removeClass(showClass);
                    }
                );
            } else {
                $dropdown.off("mouseenter mouseleave");
            }
        }, 200); // 200ms debounce
    });

    // Back to top button – native smooth scroll
    $('.back-to-top').click(function (e) {
        e.preventDefault();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

})(jQuery);