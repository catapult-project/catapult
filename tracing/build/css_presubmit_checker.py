# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re


class CSSChecker(object):

  def __init__(self, input_api, output_api, file_filter=None):
    self.input_api = input_api
    self.output_api = output_api
    self.file_filter = file_filter

  def RunChecks(self):
    # We use this a lot, so make a nick name variable.
    def _collapseable_hex(s):
      return (len(s) == 6 and s[0] == s[1] and s[2] == s[3] and s[4] == s[5])

    def _is_gray(s):
      return s[0] == s[1] == s[2] if len(s) == 3 else s[0:2] == s[2:4] == s[4:6]

    def _remove_all(s):
      return _remove_grit(_remove_ats(_remove_comments(s)))

    def _remove_ats(s):
      return re.sub(re.compile(r'@\w+.*?{(.*{.*?})+.*?}', re.DOTALL), '\\1', s)

    def _remove_comments(s):
      return re.sub(re.compile(r'/\*.*?\*/', re.DOTALL), '', s)

    def _remove_grit(s):
      grit_reg = r'<if[^>]+>.*?<\s*/\s*if[^>]*>|<include[^>]+>'
      return re.sub(re.compile(grit_reg, re.DOTALL), '', s)

    def _rgb_from_hex(s):
      if len(s) == 3:
        r, g, b = s[0] + s[0], s[1] + s[1], s[2] + s[2]
      else:
        r, g, b = s[0:2], s[2:4], s[4:6]
      return int(r, base=16), int(g, base=16), int(b, base=16)

    def alphabetize_props(contents):
      errors = []
      for rule in re.finditer(r'{(.*?)}', contents, re.DOTALL):
        semis = map(lambda t: t.strip(), rule.group(1).split(';'))[:-1]
        rules = filter(lambda r: ': ' in r, semis)
        props = map(lambda r: r[0:r.find(':')], rules)
        if props != sorted(props):
          errors.append('    %s;\nExpected: %s' % (
                        ';\n    '.join(rules), ','.join(list(sorted(props)))))
      return errors

    def braces_have_space_before_and_nothing_after(line):
      return re.search(r'(?:^|\S){|{\s*\S+\s*$', line)

    def classes_use_dashes(line):
      # Intentionally dumbed down version of CSS 2.1 grammar for class without
      # non-ASCII, escape chars, or whitespace.
      m = re.search(r'\.(-?[_a-zA-Z0-9-]+).*[,{]\s*$', line)
      return (m and (m.group(1).lower() != m.group(1) or
                     m.group(1).find('_') >= 0))

    # Ignore single frames in a @keyframe, i.e. 0% { margin: 50px; }
    frame_reg = r'\s*\d+%\s*{\s*[_a-zA-Z0-9-]+:(\s*[_a-zA-Z0-9-]+)+\s*;\s*}\s*'

    def close_brace_on_new_line(line):
      return (line.find('}') >= 0 and re.search(r'[^ }]', line) and
              not re.match(frame_reg, line))

    def colons_have_space_after(line):
      return re.search(r'(?<!data):(?!//)\S[^;]+;\s*', line)

    def favor_single_quotes(line):
      return line.find('"') >= 0

    # Shared between hex_could_be_shorter and rgb_if_not_gray.
    hex_reg = (r'#([a-fA-F0-9]{3}|[a-fA-F0-9]{6})(?=[^_a-zA-Z0-9-]|$)'
               r'(?!.*(?:{.*|,\s*)$)')

    def hex_could_be_shorter(line):
      m = re.search(hex_reg, line)
      return (m and _is_gray(m.group(1)) and _collapseable_hex(m.group(1)))

    small_seconds = r'(?:^|[^_a-zA-Z0-9-])(0?\.[0-9]+)s(?!-?[_a-zA-Z0-9-])'

    def milliseconds_for_small_times(line):
      return re.search(small_seconds, line)

    def no_data_uris_in_source_files(line):
      return re.search(r'\(\s*\'?\s*data:', line)

    def one_rule_per_line(line):
      return re.search(r'[_a-zA-Z0-9-](?<!data):(?!//)[^;]+;\s*[^ }]\s*', line)

    any_reg = re.compile(r':(?:-webkit-)?any\(.*?\)', re.DOTALL)
    multi_sels = re.compile(r'(?:}[\n\s]*)?([^,]+,(?=[^{}]+?{).*[,{])\s*$',
                            re.MULTILINE)

    def one_selector_per_line(contents):
      errors = []
      for b in re.finditer(multi_sels, re.sub(any_reg, '', contents)):
        errors.append('    ' + b.group(1).strip().splitlines()[-1:][0])
      return errors

    def rgb_if_not_gray(line):
      m = re.search(hex_reg, line)
      return (m and not _is_gray(m.group(1)))

    def suggest_ms_from_s(line):
      ms = int(float(re.search(small_seconds, line).group(1)) * 1000)
      return ' (replace with %dms)' % ms

    def suggest_rgb_from_hex(line):
      suggestions = ['rgb(%d, %d, %d)' % _rgb_from_hex(h.group(1))
                     for h in re.finditer(hex_reg, line)]
      return ' (replace with %s)' % ', '.join(suggestions)

    def suggest_short_hex(line):
      h = re.search(hex_reg, line).group(1)
      return ' (replace with #%s)' % (h[0] + h[2] + h[4])

    hsl = r'hsl\([^\)]*(?:[, ]|(?<=\())(?:0?\.?)?0%'
    zeros = (r'^.*(?:^|\D)'
             r'(?:\.0|0(?:\.0?|px|em|%|in|cm|mm|pc|pt|ex|deg|g?rad|m?s|k?hz))'
             r'(?:\D|$)(?=[^{}]+?}).*$')

    def zero_length_values(contents):
      errors = []
      for z in re.finditer(re.compile(zeros, re.MULTILINE), contents):
        first_line = z.group(0).strip().splitlines()[0]
        if not re.search(hsl, first_line):
          errors.append('    ' + first_line)
      return errors

    added_or_modified_files_checks = [
        {
            'desc': 'Alphabetize properties and list vendor specific (i.e. '
                    '-webkit) above standard.',
            'test': alphabetize_props,
            'multiline': True,
        },
        {
            'desc': 'Start braces ({) end a selector, have a space before them '
                    'and no rules after.',
            'test': braces_have_space_before_and_nothing_after,
        },
        {
            'desc': 'Classes use .dash-form.',
            'test': classes_use_dashes,
        },
        {
            'desc': 'Always put a rule closing brace (}) on a new line.',
            'test': close_brace_on_new_line,
        },
        {
            'desc': 'Colons (:) should have a space after them.',
            'test': colons_have_space_after,
        },
        {
            'desc': 'Use single quotes (\') instead of double quotes (") in '
                    'strings.',
            'test': favor_single_quotes,
        },
        {
            'desc': 'Use abbreviated hex (#rgb) when in form #rrggbb.',
            'test': hex_could_be_shorter,
            'after': suggest_short_hex,
        },
        {
            'desc': 'Use milliseconds for time measurements under 1 second.',
            'test': milliseconds_for_small_times,
            'after': suggest_ms_from_s,
        },
        {
            'desc': 'Don\'t use data URIs in source files. Use grit instead.',
            'test': no_data_uris_in_source_files,
        },
        {
            'desc': 'One rule per line '
                    '(what not to do: color: red; margin: 0;).',
            'test': one_rule_per_line,
        },
        {
            'desc': 'One selector per line (what not to do: a, b {}).',
            'test': one_selector_per_line,
            'multiline': True,
        },
        {
            'desc': 'Use rgb() over #hex when not a shade of gray (like #333).',
            'test': rgb_if_not_gray,
            'after': suggest_rgb_from_hex,
        },
        {
            'desc': 'Make all zero length terms (i.e. 0px) 0 unless inside of '
                    'hsl() or part of @keyframe.',
            'test': zero_length_values,
            'multiline': True,
        },
    ]

    results = []
    affected_files = self.input_api.AffectedFiles(include_deletes=False,
                                                  file_filter=self.file_filter)
    files = []
    for f in affected_files:
      # Remove all /*comments*/, @at-keywords, and grit <if|include> tags; we're
      # not using a real parser. TODO(dbeam): Check alpha in <if> blocks.
      file_contents = _remove_all('\n'.join(f.new_contents))
      files.append((f.filename, file_contents))

    # Only look at CSS files for now.
    for f in filter(lambda f: f[0].endswith('.css'), files):
      file_errors = []
      for check in added_or_modified_files_checks:
        # If the check is multiline, it receieves the whole file and gives us
        # back a list of things wrong. If the check isn't multiline, we pass it
        # each line and the check returns something truthy if there's an issue.
        if ('multiline' in check and check['multiline']):
          check_errors = check['test'](f[1])
          if len(check_errors) > 0:
            # There are currently no multiline checks with ['after'].
            file_errors.append(
                '- %s\n%s' % (check['desc'], '\n'.join(check_errors).rstrip()))
        else:
          check_errors = []
          lines = f[1].splitlines()
          for lnum in range(0, len(lines)):
            line = lines[lnum]
            if check['test'](line):
              error = '    ' + line.strip()
              if 'after' in check:
                error += check['after'](line)
              check_errors.append(error)
          if len(check_errors) > 0:
            file_errors.append(
                '- %s\n%s' % (check['desc'], '\n'.join(check_errors)))
      if file_errors:
        results.append(self.output_api.PresubmitPromptWarning(
            '%s:\n%s' % (f[0], '\n\n'.join(file_errors))))

    if results:
      # Add your name if you're here often mucking around in the code.
      authors = ['dbeam@chromium.org']
      results.append(self.output_api.PresubmitNotifyResult(
          'Was the CSS checker useful? Send feedback or hate mail to %s.' %
          ', '.join(authors)))

    return results
