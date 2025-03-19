# Copyright 2025 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides fnmatch-style glob matching, but only for *.

This avoids having to escape non-asterisk patterns when we only want to match
* wildcards.
"""

ESCAPED_WILDCARD = '\\*'
UNESCAPED_WILDCARD = '*'


class ReducedGlob:
    """Class representing a glob that only matches * wildcards."""

    def __init__(self, pattern):
        """Args:
            pattern: A string containing the pattern to match. * characters can
                be escaped by a backslash, e.g. \\*.
        """
        self._pattern = pattern
        self._substrings = []
        self._compute_substrings()

    def _compute_substrings(self):
        """Performs the one-time split of a pattern into substrings."""
        assert not self._substrings

        # Find all indices of * characters, ignoring those that are escaped via
        # \*. Then, use that to create an ordered list of substrings that we
        # need to have, with any number of characters permitted in between them.

        # Calculate indices of un-escaped wildcards.
        all_wildcard_indices = _find_all_indices(self._pattern,
                                                 UNESCAPED_WILDCARD)
        escaped_wildcard_indices = _find_all_indices(self._pattern,
                                                     ESCAPED_WILDCARD)
        # Offset by 1 so that the indices match those in all_wildcard_indices.
        escaped_wildcard_indices = [i + 1 for i in escaped_wildcard_indices]
        unescaped_wildcard_indices = [
            i for i in all_wildcard_indices
            if i not in escaped_wildcard_indices]

        # Split |self._pattern| into strings to match using the calculated
        # indices.
        previous_index = 0
        for i in unescaped_wildcard_indices:
            self._substrings.append(self._pattern[previous_index:i])
            previous_index = i + 1
        self._substrings.append(self._pattern[previous_index:])
        self._substrings = [s.replace(ESCAPED_WILDCARD, UNESCAPED_WILDCARD)
                            for s in self._substrings]

    def matchcase(self, name):
        """Test if |name| matches the stored pattern. Case-sensitive.

        Args:
            name: A string containing a string to test.

        Returns:
            True if |name| matches the stored pattern, otherwise False.
        """
        # Look for each substring in order, shifting the starting point to avoid
        # anything we've matched already.
        starting_index = 0
        for i, substr in enumerate(self._substrings):
            substr_start_index = name.find(substr, starting_index)
            if substr_start_index == -1:
                return False

            # The first substring is special since we need to ensure that |name|
            # starts with it. Otherwise, we could find a match later in the
            # string, which would implicitly add a * to the front of the stored
            # pattern.
            if i == 0 and substr_start_index != 0:
                return False

            # Similarly, the last substring is special since we need to ensure
            # that all characters in |name| were matched. Otherwise, we would
            # implicitly add a * to the end of the stored pattern.
            if i + 1 == len(self._substrings) and not name.endswith(substr):
                return False

            # Consume everything we just matched.
            starting_index = substr_start_index + len(substr)
        return True


def _find_all_indices(s, substr):
    all_indices = []
    index = s.find(substr)
    while index != -1:
        all_indices.append(index)
        index = s.find(substr, index + 1)
    return all_indices
