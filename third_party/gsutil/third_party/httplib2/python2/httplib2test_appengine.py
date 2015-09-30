"""
httplib2test_appengine

A set of unit tests for httplib2.py on Google App Engine

"""

__author__ = "Joe Gregorio (joe@bitworking.org)"
__copyright__ = "Copyright 2011, Joe Gregorio"

import os
import sys
import unittest

# The test resources base uri
base = 'http://bitworking.org/projects/httplib2/test/'
#base = 'http://localhost/projects/httplib2/test/'
cacheDirName = ".cache"
APP_ENGINE_PATH='../../google_appengine'

sys.path.insert(0, APP_ENGINE_PATH)

import dev_appserver
dev_appserver.fix_sys_path()

from google.appengine.ext import testbed
testbed = testbed.Testbed()
testbed.activate()
testbed.init_urlfetch_stub()

from google.appengine.runtime import DeadlineExceededError

import httplib2

class AppEngineHttpTest(unittest.TestCase):
    def setUp(self):
        if os.path.exists(cacheDirName):
            [os.remove(os.path.join(cacheDirName, file)) for file in os.listdir(cacheDirName)]

        if sys.version_info < (2, 6):
            disable_cert_validation = True
        else:
            disable_cert_validation = False

    def test(self):
        h = httplib2.Http()
        response, content = h.request("http://bitworking.org")
        self.assertEqual(httplib2.SCHEME_TO_CONNECTION['https'],
                         httplib2.AppEngineHttpsConnection)
        self.assertEquals(1, len(h.connections))
        self.assertEquals(response.status, 200)
        self.assertEquals(response['status'], '200')

    # It would be great to run the test below, but it really tests the
    # aberrant behavior of httplib on App Engine, but that special aberrant
    # httplib only appears when actually running on App Engine and not when
    # running via the SDK. When running via the SDK the httplib in std lib is
    # loaded, which throws a different error when a timeout occurs.
    #
    #def test_timeout(self):
    #    # The script waits 3 seconds, so a timeout of more than that should succeed.
    #    h = httplib2.Http(timeout=7)
    #    r, c = h.request('http://bitworking.org/projects/httplib2/test/timeout/timeout.cgi')
    #
    #    import httplib
    #    print httplib.__file__
    #    h = httplib2.Http(timeout=1)
    #    try:
    #      r, c = h.request('http://bitworking.org/projects/httplib2/test/timeout/timeout.cgi')
    #      self.fail('Timeout should have raised an exception.')
    #    except DeadlineExceededError:
    #      pass



    def test_proxy_info_ignored(self):
        h = httplib2.Http(proxy_info='foo.txt')
        response, content = h.request("http://bitworking.org")
        self.assertEquals(response.status, 200)

if __name__ == '__main__':
    unittest.main()
