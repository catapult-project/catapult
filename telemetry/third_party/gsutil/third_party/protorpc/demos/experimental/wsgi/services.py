from google.appengine.ext.webapp import util

from protorpc.experimental import wsgi_service
from protorpc.experimental import util as wsgi_util
from protorpc import protobuf
from protorpc import protojson

from protorpc import registry

protocols = wsgi_util.Protocols()
protocols.add_protocol(protobuf, 'protobuf')
protocols.add_protocol(protojson, 'json')

reg = {'/protorpc': registry.RegistryService}
registry_service = registry.RegistryService.new_factory(reg)
application = wsgi_service.service_app(registry_service,
                                       '/protorpc',
                                       protocols=protocols)


def main():
  util.run_bare_wsgi_app(application)


if __name__ == '__main__':
  main()
