def webapp_add_wsgi_middleware(app):
  """Configure additional middlewares for webapp.

  This function is called automatically by webapp.util.run_wsgi_app
  to give the opportunity for an application to register additional
  wsgi middleware components.

  See http://http://code.google.com/appengine/docs/python/tools/appstats.html
  for more information about configuring and running appstats.
  """
  from google.appengine.ext.appstats import recording
  app = recording.appstats_wsgi_middleware(app)
  return app

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
