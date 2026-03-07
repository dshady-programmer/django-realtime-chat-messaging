import os
import sys

project = "django-realtime-chat-messaging"
copyright = "2026, Peter Erinfolami"
author = "Peter Erinfolami"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
html_theme = "furo"
html_static_path = ["_static"]

# Logo — requires a transparent-background version of the logo PNG.
# Place the file at docs/source/_static/logo.png
# For the dark sidebar use the same file if it works, or a white-text variant.
html_logo = "_static/logo.png"
html_favicon = "_static/logo.png"   # swap for a proper .ico or 32x32 PNG later

# Wire in custom CSS and JS
html_css_files = ["custom.css"]
html_js_files  = ["custom.js"]

html_theme_options = {
    # Logo is shown — hide the plain text name next to it
    "sidebar_hide_name": True,
    "navigation_with_keys": True,
    "top_of_page_buttons": [],

    # ---- Light mode --------------------------------------------------------
    # Built around the logo's green (#3a9e3f) as primary brand,
    # blue (#2979b0) as content/link colour, orange (#f5a623) as accent.
    "light_css_variables": {
        # Brand
        "color-brand-primary":     "#3a9e3f",   # logo green
        "color-brand-content":     "#2979b0",   # logo blue (links)

        # Sidebar — light green tint
        "color-sidebar-background":              "#f4faf4",
        "color-sidebar-background-border":       "#d6ead6",
        "color-sidebar-brand-text":              "#2d7d32",
        "color-sidebar-link-text":               "#374151",
        "color-sidebar-link-text--top-level":    "#111827",
        "color-sidebar-item-background--hover":  "#e8f5e8",
        "color-sidebar-item-background--current":"#c8e6c8",

        # Content background — clean white
        "color-background-primary":   "#ffffff",
        "color-background-secondary": "#f4faf4",
        "color-background-hover":     "#e8f5e8",
        "color-background-border":    "#cde5cd",

        # Text
        "color-foreground-primary":   "#111827",
        "color-foreground-secondary": "#374151",
        "color-foreground-muted":     "#6b7280",
        "color-foreground-border":    "#d1d5db",

        # Inline code — light green tint
        "color-inline-code-background": "#edf7ed",

        # Admonitions
        "color-admonition-background": "#f0faf0",

        # Fonts
        "font-stack":            "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        "font-stack--monospace": "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
    },

    # ---- Dark mode ---------------------------------------------------------
    # Deep dark green background, bright green primary, blue links, orange accents.
    "dark_css_variables": {
        # Brand
        "color-brand-primary":     "#66bb6a",   # lighter green for dark bg contrast
        "color-brand-content":     "#64b5f6",   # lighter blue for dark bg links

        # Sidebar — very dark green
        "color-sidebar-background":              "#0f1a0f",
        "color-sidebar-background-border":       "#1b2e1b",
        "color-sidebar-brand-text":              "#66bb6a",
        "color-sidebar-link-text":               "#9ca3af",
        "color-sidebar-link-text--top-level":    "#e5e7eb",
        "color-sidebar-item-background--hover":  "#1a2e1a",
        "color-sidebar-item-background--current":"#1f3d1f",

        # Content background — dark green-tinted
        "color-background-primary":   "#111911",
        "color-background-secondary": "#172217",
        "color-background-hover":     "#1c2e1c",
        "color-background-border":    "#253d25",

        # Text
        "color-foreground-primary":   "#f3f4f6",
        "color-foreground-secondary": "#d1d5db",
        "color-foreground-muted":     "#9ca3af",
        "color-foreground-border":    "#374151",

        # Inline code
        "color-inline-code-background": "#1a2e1a",

        # Admonitions
        "color-admonition-background": "#172817",
    },
}

# ---------------------------------------------------------------------------
# sphinx-copybutton
# ---------------------------------------------------------------------------
copybutton_prompt_text = r">>> |\.\.\. |\$ |# "
copybutton_prompt_is_regexp = True

# ---------------------------------------------------------------------------
# Intersphinx
# ---------------------------------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "django": (
        "https://docs.djangoproject.com/en/stable/",
        "https://docs.djangoproject.com/en/stable/_objects/",
    ),
}

# ---------------------------------------------------------------------------
# Napoleon
# ---------------------------------------------------------------------------
napoleon_google_docstring = True
napoleon_numpy_docstring  = False