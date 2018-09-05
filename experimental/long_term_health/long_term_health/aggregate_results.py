# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions to aggregate the run result to make the analysis easier."""
import os
import shutil
import subprocess
import tempfile

from long_term_health import utils
# pylint: disable=import-error
# pylint: disable=no-name-in-module
import pandas as pd

TRACING_BIN = os.path.join(utils.APP_ROOT, '..', '..', 'tracing', 'bin')
RESULT_TO_JSON = os.path.join(TRACING_BIN, 'results2json')
JSON_TO_CSV = os.path.join(TRACING_BIN, 'histograms2csv')
JSON_TO_RESULT = os.path.join(TRACING_BIN, 'histograms2html')


def LoadCSV(csv_path):
  with open(os.path.join(csv_path)) as f:
    return pd.read_csv(f)


def HTMLToJSON(path_to_html, path_to_output_json):
  subprocess.call([RESULT_TO_JSON, path_to_html, path_to_output_json])


def JSONToHTML(path_to_json, path_to_output_html):
  subprocess.call(
      [JSON_TO_RESULT, path_to_output_html, '--json=%s' % path_to_json])


def JSONToCSV(path_to_json, path_to_output_csv):
  subprocess.call([JSON_TO_CSV, path_to_json, path_to_output_csv])


def HTMLToCSV(path_to_html, path_to_output_csv):
  temp_json_path = os.path.join(tempfile.gettempdir(), 'temp.json')
  HTMLToJSON(path_to_html, temp_json_path)
  JSONToCSV(temp_json_path, path_to_output_csv)
  os.remove(temp_json_path)


def AggregateCSVs(csv_dir_path, merged_csv_path):
  all_dfs = []
  for csv_ in os.listdir(csv_dir_path):
    df = LoadCSV(os.path.join(csv_dir_path, csv_))
    df['milestone'] = '%s' % csv_.split('.')[0]
    all_dfs.append(df)
  pd.concat(all_dfs, ignore_index=True).to_csv(merged_csv_path, index=False)


def AggregateResults(run_label):
  """Aggregate the run result into a large csv file.

  This function will create a merged csv file and it will also create csv files
  for each milestone and put them into a directory called `csv`.

  Args:
    run_label(string): the run label that the user supplied when the start the
    tool, it will just be the directory name for this run
  """
  temp_dir = tempfile.mkdtemp()
  run_label_path = os.path.join(utils.APP_ROOT, 'results', run_label)

  for directory in os.listdir(run_label_path):
    result_html_path = os.path.join(run_label_path, directory, 'results.html')
    csv_path = os.path.join(temp_dir, '%s.csv' % directory)
    HTMLToCSV(result_html_path, csv_path)

  shutil.copytree(temp_dir, os.path.join(run_label_path, 'csv'))
  AggregateCSVs(temp_dir, os.path.join(run_label_path, 'results.csv'))
  shutil.rmtree(temp_dir)
