# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
def _tokenize_js(text):
  rest = text
  tokens = ["//", "/*", "*/", "\n"]
  while len(rest):
    indices = [rest.find(token) for token in tokens]
    found_indices = [index for index in indices if index >= 0]

    if len(found_indices) == 0:
      # end of string
      yield rest
      return

    min_index = min(found_indices)
    token_with_min = tokens[indices.index(min_index)]

    if min_index > 0:
      yield rest[:min_index]

    yield rest[min_index:min_index + len(token_with_min)]
    rest = rest[min_index + len(token_with_min):]

def strip_js_comments(text):
  result_tokens = []
  token_stream = _tokenize_js(text).__iter__()
  while True:
    try:
      t = token_stream.next()
    except StopIteration:
      break

    if t == "//":
      while True:
        try:
          t2 = token_stream.next()
          if t2 == "\n":
            break
        except StopIteration:
          break
    elif t == '/*':
      nesting = 1
      while True:
        try:
          t2 = token_stream.next()
          if t2 == "/*":
            nesting += 1
          elif t2 == "*/":
            nesting -= 1
            if nesting == 0:
              break
        except StopIteration:
          break
    else:
      result_tokens.append(t)
  return "".join(result_tokens)
