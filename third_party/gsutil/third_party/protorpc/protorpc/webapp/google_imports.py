"""Dynamically decide from where to import other SDK modules.

All other protorpc.webapp code should import other SDK modules from
this module. If necessary, add new imports here (in both places).
"""

__author__ = 'yey@google.com (Ye Yuan)'

# pylint: disable=g-import-not-at-top
# pylint: disable=unused-import

import os
import sys

try:
  from google.appengine import ext
  normal_environment = True
except ImportError:
  normal_environment = False


if normal_environment:
  from google.appengine.ext import webapp
  from google.appengine.ext.webapp import util as webapp_util
  from google.appengine.ext.webapp import template
