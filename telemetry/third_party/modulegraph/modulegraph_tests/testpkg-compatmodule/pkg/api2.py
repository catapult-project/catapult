from __future__ import absolute_import
import six.moves.urllib.request, six.moves.urllib.error, six.moves.urllib.parse

# 2To3-division: this file is skipped as this is version specific implemetation.

def div(a, b):
    try:
        return a / b

    except ZeroDivisionError as exc:
        return None

class MyClass (object):
    pass
