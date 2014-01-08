# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

{
  'targets' : [
    {
      'target_name': 'bitmaptools',
      'type': 'none',
      'variables': {
        'output_path': '<(PRODUCT_DIR)',
      },
      'conditions': [
        ['OS=="linux" or OS=="mac" or OS=="android"', {
          'variables': {
            'python_extension': '.so'
          },
        }],
        ['OS=="win"', {
          'variables': {
            'python_extension': '.pyd'
          },
        }],
        ['OS=="win" or OS=="linux" or OS=="mac" or OS=="android"', {
          'actions': [{
            'action_name': 'bitmaptools',
            'inputs': [
              'telemetry/core/build_extension.py',
              'telemetry/core/bitmaptools/bitmaptools.cc',
            ],
            'outputs': [
              '<(output_path)/bitmaptools>(python_extension)'
            ],
            'action': [
              'python',
              '<@(_inputs)',
              '<(output_path)',
              'bitmaptools',
            ]
          }],
        }],
      ]
    },
  ],
}
