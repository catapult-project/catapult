# -*- coding: utf-8 -*-
#
# oauth2client documentation build configuration file, created by
# sphinx-quickstart on Wed Dec 17 23:13:19 2014.
#

import sys
import os

# -- General configuration ------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.coverage',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
]
templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'

# General information about the project.
project = u'oauth2client'
copyright = u'2014, Google, Inc'

# Version info
import oauth2client
version = oauth2client.__version__
release = oauth2client.__version__

exclude_patterns = ['_build']

# In order to load django before 1.7, we need to create a faux
# settings module and load it.
import django
if django.VERSION[1] < 7:
  sys.path.insert(0, '.')
  os.environ['DJANGO_SETTINGS_MODULE'] = 'django_settings'

# -- Options for HTML output ----------------------------------------------

# We want to set the RTD theme, but not if we're on RTD.
if os.environ.get('READTHEDOCS', '') != 'True':
  import sphinx_rtd_theme
  html_theme = 'sphinx_rtd_theme'
  html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

html_static_path = ['_static']
html_logo = '_static/google_logo.png'
htmlhelp_basename = 'oauth2clientdoc'

# -- Options for LaTeX output ---------------------------------------------

latex_elements = {}
latex_documents = [
    ('index', 'oauth2client.tex', u'oauth2client Documentation',
     u'Google, Inc.', 'manual'),
]

# -- Options for manual page output ---------------------------------------

man_pages = [
    ('index', 'oauth2client', u'oauth2client Documentation',
     [u'Google, Inc.'], 1)
]

# -- Options for Texinfo output -------------------------------------------

texinfo_documents = [
    ('index', 'oauth2client', u'oauth2client Documentation',
     u'Google, Inc.', 'oauth2client', 'One line description of project.',
     'Miscellaneous'),
]
