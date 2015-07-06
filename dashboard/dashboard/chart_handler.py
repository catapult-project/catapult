# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Base class for request handlers that display charts."""

__author__ = 'sullivan@google.com (Annie Sullivan)'

from dashboard import layered_cache
from dashboard import request_handler

# A map of revision type (which should be a "supplemental column" name,
# starting with "r_") to information about that revision type.
_EXTERNAL_REVISION_INFO = {
    'r_chromium_git': {
        'name': 'Chromium Git Hash',
        'url': ('https://chromium.googlesource.com'
                '/chromium/src/+log/{{R1}}..{{R2}}')
    },
    'r_chromium_commit_pos': {
        'name': 'Chromium Commit Position',
        'url': ('http://test-results.appspot.com/revision_range'
                '?start={{R1}}&end={{R2}}'),
    },
    'r_chrome_version': {
        'name': 'Chrome Version',
        'url': ('https://omahaproxy.appspot.com/changelog'
                '?old_version={{R1}}&new_version={{R2}}'),
    },
    'r_cros_version': {
        'name': 'ChromeOS Version',
        'url': ('http://chromeos-images/diff/report'
                '?from={{R1_trim}}&to={{R2_trim}}'),
    },
    'r_clang_rev': {
        'name': 'Clang Revision',
        'url': ('http://llvm.org/viewvc/llvm-project'
                '?view=revision&revision={{R2}}#start={{R1}}'),
    },
    'r_oilpan': {
        'name': 'Oilpan Revision',
        'url': ('http://build.chromium.org'
                '/f/chromium/perf/dashboard/ui/changelog_blink.html'
                '?url=/branches/oilpan&mode=html&range={{R1}}:{{R2}}'),
    },
    'r_v8_git': {
        'name': 'V8 Git Hash',
        'url': 'https://chromium.googlesource.com/v8/v8/+log/{{R1}}..{{R2}}',
    },
    'r_webkit': {
        'name': 'Blink SVN Revision',
        'url': ('http://build.chromium.org'
                '/f/chromium/perf/dashboard/ui/changelog_blink.html'
                '?url=/trunk&mode=html&range={{R1}}:{{R2}}'),
    },
    'r_webkit_git': {
        'name': 'Blink Git Hash',
        'url': ('https://chromium.googlesource.com'
                '/chromium/blink/+log/{{R1}}..{{R2}}'),
    },
    'r_webrtc': {
        'name': 'WebRTC Revision',
        'url': ('http://build.chromium.org'
                '/f/chromium/perf/dashboard/ui/changelog_webrtc.html'
                '?url=/trunk&mode=html&range={{R1}}:{{R2}}'),
    },
}

# Some items in the above list may have alternate names.
# In the dictionary below, keys are aliases, and values already exist above.
_ALIAS_MAP = {
    'r_chromium': 'r_chromium_git',
    'r_commit_pos': 'r_chromium_commit_pos',
    'r_webkit_rev': 'r_webkit',
    'r_webkit_rev_git': 'r_webkit_git',
    'r_webrtc_rev': 'r_webrtc',
}
for alias in _ALIAS_MAP:
  _EXTERNAL_REVISION_INFO[alias] = _EXTERNAL_REVISION_INFO[_ALIAS_MAP[alias]]


class ChartHandler(request_handler.RequestHandler):
  """Base class for requests which display a chart."""

  def RenderHtml(self, template_file, template_values, status=200):
    """Fills in necessary chart values."""
    revision_info = _EXTERNAL_REVISION_INFO

    template_values['revision_info'] = revision_info
    template_values['warning_message'] = layered_cache.Get('warning_message')
    template_values['warning_bug'] = layered_cache.Get('warning_bug')

    return super(ChartHandler, self).RenderHtml(
        template_file, template_values, status)
