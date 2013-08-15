# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class CamelCaseConverter(object):
  """Helper class which helps convert between the camel case and
     underscore naming conventions.
  """

  @classmethod
  def FromCamelCase(cls, obj):
    """Descends recursively into the object obj, converting all
       attributes' names from camelCase to underscore naming
       convention. Returns a newly allocated object of the same
       structure as the input. Handles nested structures of
       dictionaries and lists.
    """

    output = None
    if isinstance(obj, dict):
      output = dict()
      for k, v in obj.iteritems():
        output[cls.__CamelCaseToUnderscore(k)] = cls.FromCamelCase(v)
    elif isinstance(obj, list):
      output = []
      for item in obj:
        output.append(cls.FromCamelCase(item))
    else:
      output = obj
    return output

  @classmethod
  def __CamelCaseToUnderscore(cls, input_string):
    result = ""
    for c in input_string:
      if c.isupper():
        result += "_" + c.lower()
      else:
        result += c
    return result
