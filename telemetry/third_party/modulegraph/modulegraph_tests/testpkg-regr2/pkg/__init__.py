"""
Package structure simular to crcmod
"""
from __future__ import absolute_import
try:
    from .pkg.pkg import *
    from . import pkg.base
except ImportError:
    from .pkg import *
    from . import base
