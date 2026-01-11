# Configuration file for the Sphinx documentation builder.
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
import django

# Add your package to the Python path
sys.path.insert(0, os.path.abspath('../..'))

# Django setup for autodoc
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.settings')
try:
    django.setup()
except Exception:
    pass  # Allow building without full Django setup

# -- Project information -----------------------------------------------------
project = 'Django Realtime Chat Messaging'
copyright = '2024, Your Name'
author = 'Your Name'
release = '0.1.0'
version = '0.1.0'

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.githubpages',
    'sphinx_autodoc_typehints',
    'sphinx_copybutton',  # Adds copy button to code blocks
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = []

# The suffix(es) of source filenames.
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

# -- Options for HTML output -------------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Theme options
html_theme_options = {
    'navigation_depth': 4,
    'collapse_navigation': False,
    'sticky_navigation': True,
    'includehidden': True,
    'titles_only': False,
    'display_version': True,
    'prev_next_buttons_location': 'both',
    'style_external_links': True,
}

# Custom CSS (optional)
html_css_files = [
    'custom.css',
]

# The master toctree document.
master_doc = 'index'

# Logo and favicon
html_logo = '_static/logo.png'  # Add your logo
html_favicon = '_static/favicon.ico'  # Add your favicon

# -- Extension configuration -------------------------------------------------

# Napoleon settings for Google/NumPy style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# Autodoc settings
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '__weakref__'
}

autodoc_typehints = 'description'
autodoc_typehints_description_target = 'documented'

# Intersphinx mapping
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'django': ('https://docs.djangoproject.com/en/stable/', 
               'https://docs.djangoproject.com/en/stable/_objects/'),
    'channels': ('https://channels.readthedocs.io/en/stable/', None),
    'drf': ('https://www.django-rest-framework.org/', None),
}

# Todo extension
todo_include_todos = True

# GitHub integration
html_context = {
    "display_github": True,
    "github_user": "shady-cj",
    "github_repo": "django-realtime-chat-messaging",
    "github_version": "develop",
    "conf_py_path": "/docs/source/",
}

# Copy button configuration
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True

# Add custom CSS
def setup(app):
    app.add_css_file('custom.css')