/* ==========================================================================
   django-realtime-chat-messaging — Custom Documentation JS
   Placed at: docs/source/_static/custom.js
   ========================================================================== */

document.addEventListener("DOMContentLoaded", function () {

    // -----------------------------------------------------------------------
    // 1. CODE BLOCK LANGUAGE LABELS
    // Reads the highlight class (e.g. "highlight-python") and sets a
    // data-lang attribute so CSS can display it as a ::before label.
    // -----------------------------------------------------------------------
    const LANG_LABELS = {
        python:     "Python",
        javascript: "JavaScript",
        js:         "JavaScript",
        json:       "JSON",
        bash:       "Shell",
        shell:      "Shell",
        text:       "Text",
        rst:        "reStructuredText",
        yaml:       "YAML",
        ini:        "INI",
        nginx:      "Nginx",
    };

    document.querySelectorAll("div[class*='highlight-']").forEach(function (block) {
        const match = block.className.match(/highlight-(\w+)/);
        if (!match) return;
        const lang = match[1].toLowerCase();
        if (lang === "default" || lang === "none") return;
        const label = LANG_LABELS[lang] || lang;
        block.setAttribute("data-lang", label);
    });


    // -----------------------------------------------------------------------
    // 2. SMOOTH SCROLL FOR ANCHOR LINKS
    // Overrides default jump-to-anchor with a smooth scroll.
    // -----------------------------------------------------------------------
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
        anchor.addEventListener("click", function (e) {
            const target = document.querySelector(this.getAttribute("href"));
            if (!target) return;
            e.preventDefault();
            target.scrollIntoView({ behavior: "smooth", block: "start" });
            // Update URL without triggering scroll again
            history.pushState(null, "", this.getAttribute("href"));
        });
    });


    // -----------------------------------------------------------------------
    // 3. ACTIVE SECTION HIGHLIGHT IN TOC SIDEBAR
    // Adds an "active" class to the sidebar TOC link matching the section
    // currently in the viewport, so users always know where they are.
    // -----------------------------------------------------------------------
    const headings = document.querySelectorAll("article h2, article h3");
    const tocLinks = document.querySelectorAll(".toc-tree a");

    if (headings.length && tocLinks.length) {
        const observer = new IntersectionObserver(
            function (entries) {
                entries.forEach(function (entry) {
                    if (!entry.isIntersecting) return;
                    const id = entry.target.getAttribute("id");
                    if (!id) return;
                    tocLinks.forEach(function (link) {
                        link.classList.remove("toc-active");
                        if (link.getAttribute("href") === "#" + id) {
                            link.classList.add("toc-active");
                        }
                    });
                });
            },
            { rootMargin: "0px 0px -60% 0px", threshold: 0 }
        );

        headings.forEach(function (h) { observer.observe(h); });
    }


    // -----------------------------------------------------------------------
    // 4. EXTERNAL LINK INDICATOR
    // Adds a small arrow icon after links that open outside the docs site,
    // so readers know they are leaving without being surprised.
    // -----------------------------------------------------------------------
    document.querySelectorAll("article a[href^='http']").forEach(function (link) {
        // Skip links that already have an icon or are images
        if (link.querySelector("img") || link.classList.contains("no-ext")) return;
        link.setAttribute("target", "_blank");
        link.setAttribute("rel", "noopener noreferrer");
        const icon = document.createElement("span");
        icon.textContent = " ↗";
        icon.style.cssText = "font-size:0.75em; opacity:0.6; user-select:none;";
        link.appendChild(icon);
    });


    // -----------------------------------------------------------------------
    // 5. TABLE ENHANCEMENTS
    // Makes wide tables scrollable on mobile instead of overflowing.
    // -----------------------------------------------------------------------
    document.querySelectorAll("table.docutils").forEach(function (table) {
        if (table.parentElement.classList.contains("table-wrapper")) return;
        const wrapper = document.createElement("div");
        wrapper.className = "table-wrapper";
        wrapper.style.cssText = "overflow-x: auto; -webkit-overflow-scrolling: touch;";
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
    });

});
