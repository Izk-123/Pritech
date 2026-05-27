(function ($) {
    "use strict";

    // Spinner
    $(window).on('load', function () {
        $('#spinner').removeClass('show');
    });

    // WOW.js
    new WOW().init();

    // Lenis Smooth Scroll (if CDN loaded)
    if (typeof Lenis !== 'undefined') {
        const lenis = new Lenis({ duration: 1.2, easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)) });
        function raf(time) { lenis.raf(time); requestAnimationFrame(raf); }
        requestAnimationFrame(raf);
    }

    // Reading Progress Bar
    function updateProgressBar() {
        const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
        const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
        const scrolled = (winScroll / height) * 100;
        document.querySelector('.reading-progress-bar')?.setAttribute('style', `width: ${scrolled}%`);
    }
    window.addEventListener('scroll', updateProgressBar);

    // Dark Mode Toggle
    const darkModeToggle = () => {
        const isDark = localStorage.getItem('darkMode') === 'true';
        if (isDark) {
            document.body.classList.add('dark-mode');
            $('.dark-mode-toggle i').removeClass('fa-moon').addClass('fa-sun');
        } else {
            document.body.classList.remove('dark-mode');
            $('.dark-mode-toggle i').removeClass('fa-sun').addClass('fa-moon');
        }
    };
    darkModeToggle();
    $(document).on('click', '.dark-mode-toggle', function () {
        document.body.classList.toggle('dark-mode');
        localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
        darkModeToggle();
    });

    // Scroll Spy
    const sections = document.querySelectorAll('section, div[id]');
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    function updateActiveNav() {
        let current = '';
        const scrollPos = window.scrollY + 150;
        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionBottom = sectionTop + section.offsetHeight;
            if (scrollPos >= sectionTop && scrollPos < sectionBottom) {
                current = section.getAttribute('id');
            }
        });
        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === `#${current}`) {
                link.classList.add('active');
            }
        });
    }
    window.addEventListener('scroll', updateActiveNav);
    window.addEventListener('load', updateActiveNav);

    // Sticky Navbar + Back-to-top
    var ticking = false;
    $(window).on('scroll', function () {
        if (!ticking) {
            window.requestAnimationFrame(function () {
                var scrollTop = $(window).scrollTop() || 0;
                if (scrollTop > 45) $('.navbar').addClass('sticky-top shadow-sm');
                else $('.navbar').removeClass('sticky-top shadow-sm');
                if (scrollTop > 100) $('.back-to-top').fadeIn('slow');
                else $('.back-to-top').fadeOut('slow');
                ticking = false;
            });
            ticking = true;
        }
    });

    // Dropdown hover (desktop)
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
                        $(this).addClass(showClass);
                        $(this).find($dropdownToggle).attr("aria-expanded", "true");
                        $(this).find($dropdownMenu).addClass(showClass);
                    },
                    function () {
                        $(this).removeClass(showClass);
                        $(this).find($dropdownToggle).attr("aria-expanded", "false");
                        $(this).find($dropdownMenu).removeClass(showClass);
                    }
                );
            } else {
                $dropdown.off("mouseenter mouseleave");
            }
        }, 200);
    });

    // Back to top smooth
    $('.back-to-top').click(function (e) {
        e.preventDefault();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    // Animated Counters
    function animateCounters() {
        $('.counter').each(function () {
            const $this = $(this);
            const target = parseInt($this.data('target'));
            let current = 0;
            const suffix = $this.data('target').toString().includes('%') ? '%' : '';
            const updateCounter = setInterval(() => {
                if (current >= target) {
                    clearInterval(updateCounter);
                    $this.text(target + suffix);
                    return;
                }
                current += Math.ceil(target / 40);
                if (current > target) current = target;
                $this.text(current + suffix);
            }, 25);
        });
    }
    const heroSection = document.querySelector('#home');
    if (heroSection) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => { if (entry.isIntersecting) { animateCounters(); observer.unobserve(entry.target); } });
        }, { threshold: 0.4 });
        observer.observe(heroSection);
    }

    // Instant Form Validation
    const contactForm = document.querySelector('#contact form');
    if (contactForm) {
        const inputs = contactForm.querySelectorAll('input, textarea');
        inputs.forEach(input => {
            input.addEventListener('input', function () {
                if (this.checkValidity()) this.classList.remove('is-invalid');
                else this.classList.add('is-invalid');
            });
        });
        contactForm.addEventListener('submit', function (e) {
            if (!this.checkValidity()) {
                e.preventDefault();
                alert('Please fill all required fields correctly.');
            }
        });
    }

    // Magnetic hover effect
    $('.btn:not(.btn-link)').on('mousemove', function(e) {
        const rect = this.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        $(this).css('transform', `translate(${(x - rect.width/2) * 0.05}px, ${(y - rect.height/2) * 0.05}px)`);
    }).on('mouseleave', function() {
        $(this).css('transform', 'translate(0, 0)');
    });

})(jQuery);