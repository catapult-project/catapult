# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


def GetAnalysis(job_id):
  "Return a TryJob CABE Analysis as a list."
  print(job_id)
  return [{
      'experiment_spec': {
          'common': {},
          'control': {},
          'treatment': {},
          'analysis': {
              'benchmark': {
                  'name': "speedometer2",
                  'workload': "AngularJS-TodoMVC"
              }
          }
      },
      'statistic': {
          'lower': -7.191551318789924,
          'upper': 10.395767084476738,
          'p_value': 0.431640625,
          'control_median': 103.50000000093132,
          'treatment_median': 107.89999999850988,
      }
  }]
