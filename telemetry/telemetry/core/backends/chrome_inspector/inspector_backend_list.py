# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import sys

from telemetry.core import exceptions
from telemetry.core.backends.chrome_inspector import inspector_backend


def DebuggerUrlToId(debugger_url):
  return debugger_url.split('/')[-1]


class InspectorBackendList(collections.Sequence):
  """A dynamic sequence of active InspectorBackends."""

  def __init__(self, browser_backend):
    """Constructor.

    Args:
      browser_backend: The BrowserBackend instance to query for
          InspectorBackends.
    """
    self._browser_backend = browser_backend
    # A ordered mapping of context IDs to inspectable contexts.
    self._inspectable_contexts_dict = collections.OrderedDict()
    # A cache of inspector backends, by context ID.
    self._inspector_backend_dict = {}

  @property
  def app(self):
    return self._browser_backend.app

  def GetContextInfo(self, context_id):
    return self._inspectable_contexts_dict[context_id]

  def ShouldIncludeContext(self, _context):
    """Override this method to control which contexts are included."""
    return True

  def CreateWrapper(self, inspector_backend_instance):
    """Override to return the wrapper API over InspectorBackend.

    The wrapper API is the public interface for InspectorBackend. It
    may expose whatever methods are desired on top of that backend.
    """
    raise NotImplementedError

  #TODO(nednguyen): Remove this method and turn inspector_backend_list API to
  # dictionary-like API (crbug.com/398467)
  def __getitem__(self, index):
    self._Update()
    if index >= len(self._inspectable_contexts_dict.keys()):
      logging.error('About to explode: _inspectable_contexts_dict.keys() = %s',
                    repr({
                      "index": index,
                      "keys": self._inspectable_contexts_dict.keys()
                    }))
    context_id = self._inspectable_contexts_dict.keys()[index]
    return self.GetBackendFromContextId(context_id)

  def GetBackendFromContextId(self, context_id):
    self._Update()
    if context_id not in self._inspectable_contexts_dict:
      raise KeyError('Cannot find a context with id=%s' % context_id)
    if context_id not in self._inspector_backend_dict:
      try:
        backend = inspector_backend.InspectorBackend(
            self._browser_backend.app,
            self._browser_backend.devtools_client,
            self._inspectable_contexts_dict[context_id])
      except inspector_backend.InspectorException:
        err_msg = sys.exc_info()[1]
        self._HandleDevToolsConnectionError(err_msg)
      backend = self.CreateWrapper(backend)
      self._inspector_backend_dict[context_id] = backend
    return self._inspector_backend_dict[context_id]

  def __iter__(self):
    self._Update()
    return self._inspectable_contexts_dict.keys().__iter__()

  def __len__(self):
    self._Update()
    return len(self._inspectable_contexts_dict)

  def _Update(self):
    contexts = self._browser_backend.ListInspectableContexts()
    context_ids = [context['id'] for context in contexts]

    # Append all new inspectable contexts to the dict.
    for context in contexts:
      if not self.ShouldIncludeContext(context):
        continue
      if context['id'] in self._inspectable_contexts_dict:
        continue
      self._inspectable_contexts_dict[context['id']] = context

    # Remove all inspectable contexts that have gone away from the dict.
    for context_id in self._inspectable_contexts_dict.keys():
      if context_id not in context_ids:
        del self._inspectable_contexts_dict[context_id]
      else:
        # Also remove inspectable contexts that have no websocketDebuggerUrls.
        context = next(context for context in contexts
                      if context['id'] == context_id)
        if (context_id not in self._inspector_backend_dict.keys() and
            'webSocketDebuggerUrl' not in context):
          logging.debug('webSocketDebuggerUrl missing, removing %s'
                        % context_id)
          del self._inspectable_contexts_dict[context_id]

    # Clean up any backends for contexts that have gone away.
    for context_id in self._inspector_backend_dict.keys():
      if context_id not in self._inspectable_contexts_dict:
        del self._inspector_backend_dict[context_id]

  def _HandleDevToolsConnectionError(self, err_msg):
    """Call when handling errors in connecting to the DevTools websocket.

    This can be overwritten by sub-classes to further specify the exceptions
    which should be thrown.
    """
    raise exceptions.DevtoolsTargetCrashException(self.app, err_msg)
