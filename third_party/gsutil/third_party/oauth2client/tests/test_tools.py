"""Unit tests for oauth2client.tools."""

import unittest
from oauth2client import tools
from six.moves.urllib import request
import threading

class TestClientRedirectServer(unittest.TestCase):
    """Test the ClientRedirectServer and ClientRedirectHandler classes."""

    def test_ClientRedirectServer(self):
        # create a ClientRedirectServer and run it in a thread to listen
        # for a mock GET request with the access token
        # the server should return a 200 message and store the token
        httpd = tools.ClientRedirectServer(('localhost', 0), tools.ClientRedirectHandler)
        code = 'foo'
        url = 'http://localhost:%i?code=%s' % (httpd.server_address[1], code)
        t = threading.Thread(target = httpd.handle_request)
        t.setDaemon(True)
        t.start()
        f = request.urlopen( url )
        self.assertTrue(f.read())
        t.join()
        httpd.server_close()
        self.assertEqual(httpd.query_params.get('code'),code)


if __name__ == '__main__':
    unittest.main()

