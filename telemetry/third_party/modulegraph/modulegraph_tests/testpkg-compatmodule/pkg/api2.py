import urllib2

# 2To3-division: this file is skipped as this is version specific implemetation.

def div(a, b):
    try:
        return a / b

    except ZeroDivisionError as exc:
        return None

class MyClass (object):
    pass
