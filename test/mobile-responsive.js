/* Mobile Responsive JavaScript for Lead Analytics Dashboard */
/* Add this script to each HTML page */

(function() {
    'use strict';

    // Wait for DOM to be ready
    document.addEventListener('DOMContentLoaded', function() {

        // Mobile sidebar toggle
        const sidebarToggle = document.getElementById('sidebarToggle');
        const sidebar = document.querySelector('.sidebar');

        if (sidebarToggle && sidebar) {
            // Create overlay for mobile
            const overlay = document.createElement('div');
            overlay.className = 'sidebar-overlay';
            document.body.appendChild(overlay);

            // Toggle sidebar on mobile
            sidebarToggle.addEventListener('click', function() {
                sidebar.classList.toggle('active');
                overlay.classList.toggle('active');
            });

            // Close sidebar when clicking overlay
            overlay.addEventListener('click', function() {
                sidebar.classList.remove('active');
                overlay.classList.remove('active');
            });
        }

        // Detect mobile device
        function isMobile() {
            return window.innerWidth <= 640;
        }

        // Handle window resize
        let resizeTimer;
        window.addEventListener('resize', function() {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function() {
                // Refresh charts on resize for responsiveness
                if (typeof Chart !== 'undefined' && Chart.instances) {
                    Object.values(Chart.instances).forEach(chart => {
                        chart.resize();
                    });
                }
            }, 250);
        });

        // Make tables horizontally scrollable on mobile
        const tables = document.querySelectorAll('.overflow-x-auto');
        tables.forEach(function(table) {
            if (isMobile()) {
                table.classList.add('table-scroll-hint');
            }
        });

        // Add touch-friendly spacing for mobile
        if (isMobile()) {
            document.body.classList.add('mobile-view');
        }

        // Collapse expandable rows on mobile by default
        if (isMobile()) {
            const expandableRows = document.querySelectorAll('.expandable-content');
            expandableRows.forEach(function(row) {
                row.classList.add('hidden');
            });
        }

        // Optimize select dropdowns for mobile
        const selects = document.querySelectorAll('select');
        selects.forEach(function(select) {
            if (isMobile()) {
                select.style.fontSize = '16px'; // Prevent zoom on iOS
            }
        });

        // Handle table horizontal scroll indicator
        tables.forEach(function(tableWrapper) {
            const table = tableWrapper.querySelector('table');
            if (table && isMobile()) {
                function checkScroll() {
                    const isScrollable = table.scrollWidth > table.clientWidth;
                    const isAtEnd = table.scrollLeft + table.clientWidth >= table.scrollWidth - 1;

                    if (isScrollable && !isAtEnd) {
                        tableWrapper.setAttribute('data-scroll-hint', 'true');
                    } else {
                        tableWrapper.removeAttribute('data-scroll-hint');
                    }
                }

                table.addEventListener('scroll', checkScroll);
                checkScroll(); // Initial check
            }
        });

        // Mobile-friendly date picker
        if (isMobile()) {
            const dateInputs = document.querySelectorAll('input[type="date"]');
            dateInputs.forEach(function(input) {
                input.style.fontSize = '16px'; // Prevent zoom on iOS
            });
        }

        // Prevent double-tap zoom on buttons
        let lastTouchEnd = 0;
        document.addEventListener('touchend', function(event) {
            const now = Date.now();
            if (now - lastTouchEnd <= 300) {
                event.preventDefault();
            }
            lastTouchEnd = now;
        }, false);

        // Add pull-to-refresh hint on mobile
        if (isMobile() && 'ontouchstart' in window) {
            let touchStartY = 0;

            document.addEventListener('touchstart', function(e) {
                touchStartY = e.touches[0].clientY;
            });

            document.addEventListener('touchmove', function(e) {
                const touchY = e.touches[0].clientY;
                const touchDiff = touchY - touchStartY;

                if (touchDiff > 0 && window.scrollY === 0) {
                    // Pulled down at top of page - refresh hint
                    console.log('Pull to refresh');
                }
            });
        }

        // Console log for mobile debugging
        console.log('Mobile responsive scripts loaded');
        console.log('Is mobile:', isMobile());
        console.log('Screen width:', window.innerWidth);
    });
})();
