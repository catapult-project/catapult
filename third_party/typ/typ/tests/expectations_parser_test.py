# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from typ import expectations_parser


class TaggedTestListParserTest(unittest.TestCase):
    def testInitWithGoodData(self):
        good_data = """
# This is a test expectation file.
#
# tags: [ Release Debug ]
# tags: [ Linux
#   Mac Mac10.1 Mac10.2
#   Win ]

crbug.com/12345 [ Mac ] b1/s1 [ Skip ]
crbug.com/23456 [ Mac Debug ] b1/s2 [ Skip ]
"""
        parser = expectations_parser.TaggedTestListParser(good_data)
        tag_sets = [{'Debug', 'Release'},
                    {'Linux', 'Mac', 'Mac10.1', 'Mac10.2', 'Win'}]
        self.assertEqual(tag_sets, parser.tag_sets)
        expected_outcome = [
            expectations_parser.Expectation('crbug.com/12345', 'b1/s1',
                                            ['Mac'], ['SKIP']),
            expectations_parser.Expectation('crbug.com/23456', 'b1/s2',
                                            ['Mac', 'Debug'], ['SKIP'])
        ]
        for i in range(len(parser.expectations)):
            self.assertEqual(parser.expectations[i], expected_outcome[i])

    def testInitWithBadData(self):
        bad_data = """
# This is a test expectation file.
#
# tags: [ tag1 tag2 tag3 ]
# tags: [ tag4 ]

crbug.com/12345 [ Mac b1/s1 [ Skip ]
"""
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(bad_data)

    def testTagAfterExpectationsStart(self):
        bad_data = """
# This is a test expectation file.
#
# tags: [ tag1 tag2 tag3 ]

crbug.com/12345 [ tag1 ] b1/s1 [ Skip ]

# tags: [ tag4 ]
"""
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(bad_data)

    def testParseExpectationLineEverythingThere(self):
        raw_data = '# tags: [ Mac ]\ncrbug.com/23456 [ Mac ] b1/s2 [ Skip ]'
        parser = expectations_parser.TaggedTestListParser(raw_data)
        expected_outcome = [
            expectations_parser.Expectation('crbug.com/23456', 'b1/s2',
                                            ['Mac'], ['SKIP'])
        ]
        for i in range(len(parser.expectations)):
            self.assertEqual(parser.expectations[i], expected_outcome[i])

    def testParseExpectationLineBadTag(self):
        raw_data = '# tags: None\ncrbug.com/23456 [ Mac ] b1/s2 [ Skip ]'
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(raw_data)

    def testParseExpectationLineNoTags(self):
        raw_data = '# tags: [ All ]\ncrbug.com/12345 b1/s1 [ Skip ]'
        parser = expectations_parser.TaggedTestListParser(raw_data)
        expected_outcome = [
            expectations_parser.Expectation('crbug.com/12345', 'b1/s1', [],
                                            ['SKIP']),
        ]
        for i in range(len(parser.expectations)):
            self.assertEqual(parser.expectations[i], expected_outcome[i])

    def testParseExpectationLineNoBug(self):
        raw_data = '# tags: [ All ]\n[ All ] b1/s1 [ Skip ]'
        parser = expectations_parser.TaggedTestListParser(raw_data)
        expected_outcome = [
            expectations_parser.Expectation(None, 'b1/s1', ['All'], ['SKIP']),
        ]
        for i in range(len(parser.expectations)):
            self.assertEqual(parser.expectations[i], expected_outcome[i])

    def testParseExpectationLineNoBugNoTags(self):
        raw_data = '# tags: [ All ]\nb1/s1 [ Skip ]'
        parser = expectations_parser.TaggedTestListParser(raw_data)
        expected_outcome = [
            expectations_parser.Expectation(None, 'b1/s1', [], ['SKIP']),
        ]
        for i in range(len(parser.expectations)):
            self.assertEqual(parser.expectations[i], expected_outcome[i])

    def testParseExpectationLineMultipleTags(self):
        raw_data = ('# tags: [ All None Batman ]\n'
                    'crbug.com/123 [ All ] b1/s1 [ Skip ]\n'
                    'crbug.com/124 [ None ] b1/s2 [ Pass ]\n'
                    'crbug.com/125 [ Batman ] b1/s3 [ Failure ]')
        parser = expectations_parser.TaggedTestListParser(raw_data)
        expected_outcome = [
            expectations_parser.Expectation(
                'crbug.com/123', 'b1/s1', ['All'], ['SKIP']),
            expectations_parser.Expectation(
                'crbug.com/124', 'b1/s2', ['None'], ['PASS']),
            expectations_parser.Expectation(
                'crbug.com/125', 'b1/s3', ['Batman'], ['FAIL'])
        ]
        for i in range(len(parser.expectations)):
            self.assertEqual(parser.expectations[i], expected_outcome[i])

    def testParseExpectationLineBadTagBracket(self):
        raw_data = '# tags: [ Mac ]\ncrbug.com/23456 ] Mac ] b1/s2 [ Skip ]'
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(raw_data)

    def testParseExpectationLineBadResultBracket(self):
        raw_data = '# tags: [ Mac ]\ncrbug.com/23456 ] Mac ] b1/s2 ] Skip ]'
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(raw_data)

    def testParseExpectationLineBadTagBracketSpacing(self):
        raw_data = '# tags: [ Mac ]\ncrbug.com/2345 [Mac] b1/s1 [ Skip ]'
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(raw_data)

    def testParseExpectationLineBadResultBracketSpacing(self):
        raw_data = '# tags: [ Mac ]\ncrbug.com/2345 [ Mac ] b1/s1 [Skip]'
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(raw_data)

    def testParseExpectationLineNoClosingTagBracket(self):
        raw_data = '# tags: [ Mac ]\ncrbug.com/2345 [ Mac b1/s1 [ Skip ]'
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(raw_data)

    def testParseExpectationLineNoClosingResultBracket(self):
        raw_data = '# tags: [ Mac ]\ncrbug.com/2345 [ Mac ] b1/s1 [ Skip'
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(raw_data)

    def testParseExpectationLineUrlInTestName(self):
        raw_data = (
            '# tags: [ Mac ]\ncrbug.com/123 [ Mac ] b.1/http://google.com [ Skip ]'
        )
        expected_outcomes = [
            expectations_parser.Expectation(
                'crbug.com/123', 'b.1/http://google.com', ['Mac'], ['SKIP'])
        ]
        parser = expectations_parser.TaggedTestListParser(raw_data)
        for i in range(len(parser.expectations)):
            self.assertEqual(parser.expectations[i], expected_outcomes[i])

    def testParseExpectationLineEndingComment(self):
        raw_data = ('# tags: [ Mac ]\n'
                    'crbug.com/23456 [ Mac ] b1/s2 [ Skip ] # abc 123')
        parser = expectations_parser.TaggedTestListParser(raw_data)
        expected_outcome = [
            expectations_parser.Expectation('crbug.com/23456', 'b1/s2',
                                            ['Mac'], ['SKIP'])
        ]
        for i in range(len(parser.expectations)):
            self.assertEqual(parser.expectations[i], expected_outcome[i])

    def testParseBadMultiline_1(self):
        raw_data = ('# tags: [ Mac\n'
                    '          Win\n'
                    '# ]\n'
                    'crbug.com/23456 [ Mac ] b1/s2 [ Skip ]')
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(raw_data)

    def testParseTwoSetsOfTagsOnOneLineAreNotAllowed(self):
        raw_data = ('# tags: [ Debug ] [ Release ]\n')
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(raw_data)

    def testParseTrailingTextAfterTagSetIsNotAllowed(self):
        raw_data = ('# tags: [ Debug\n'
                    '#  ] # Release\n')
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(raw_data)

    def testParseBadMultiline_2(self):
        raw_data = ('# tags: [ Mac\n'
                    '          Win ]\n'
                    'crbug.com/23456 [ Mac ] b1/s2 [ Skip ]')
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(raw_data)

    def testParseUnknownResult(self):
        raw_data = ('# tags: [ Mac ]\n'
                    'crbug.com/23456 [ Mac ] b1/s2 [ UnknownResult ]')
        with self.assertRaises(expectations_parser.ParseError):
            expectations_parser.TaggedTestListParser(raw_data)

    def testOneTagInMultipleTagsets(self):
        raw_data = ('# tags: [ Mac Win Linux ]\n'
                    '# tags: [ Mac BMW ]')
        with self.assertRaises(expectations_parser.ParseError) as context:
            expectations_parser.TaggedTestListParser(raw_data)
        self.assertEqual(
            '1: The tag Mac was found in multiple tag sets',
            str(context.exception))

    def testTwoTagsinMultipleTagsets(self):
        raw_data = ('\n# tags: [ Mac Linux ]\n# tags: [ Mac BMW Win ]\n'
                    '# tags: [ Win Android ]\n# tags: [ IOS ]')
        with self.assertRaises(expectations_parser.ParseError) as context:
            expectations_parser.TaggedTestListParser(raw_data)
        self.assertEqual(
            '2: The tags Mac and Win were found in multiple tag sets',
            str(context.exception))

    def testTwoPlusTagsinMultipleTagsets(self):
        raw_data = ('\n\n# tags: [ Mac Linux ]\n# tags: [ Mac BMW Win ]\n'
                    '# tags: [ Win Android ]\n# tags: [ IOS BMW ]')
        with self.assertRaises(expectations_parser.ParseError) as context:
            expectations_parser.TaggedTestListParser(raw_data)
        self.assertEqual(
            '3: The tags BMW, Mac and Win'
            ' were found in multiple tag sets',
            str(context.exception))

    def testTwoTagsetPairsSharingTags(self):
        raw_data = ('\n\n\n# tags: [ Mac Linux Win ]\n# tags: [ Mac BMW Win ]\n'
                    '# tags: [ Android ]\n# tags: [ IOS Android ]')
        with self.assertRaises(expectations_parser.ParseError) as context:
            expectations_parser.TaggedTestListParser(raw_data)
        self.assertEqual(
            '4: The tags Android, Mac and Win'
            ' were found in multiple tag sets',
            str(context.exception))

    def testDisjoinTagsets(self):
        raw_data = ('# tags: [ Mac Win Linux ]\n'
                    '# tags: [ Honda BMW ]')
        expectations_parser.TaggedTestListParser(raw_data)

    def testEachTagInGroupIsNotFromDisjointTagSets(self):
        raw_data = (
            '# tags: [ Mac Win Amd Intel]\n'
            '# tags: [Linux Batman Robin Superman]\n'
            'crbug.com/23456 [ Mac Win Amd Robin Linux ] b1/s1 [ Pass ]\n')
        with self.assertRaises(expectations_parser.ParseError) as context:
            expectations_parser.TaggedTestListParser(raw_data)
        self.assertIn(
            '3: The tag group contains tags '
            'that are part of the same tag set\n',
            str(context.exception))
        self.assertIn('  - Tags Linux and Robin are part of the same tag set',
                      str(context.exception))
        self.assertIn('  - Tags Amd, Mac and Win are part of the same tag set',
                      str(context.exception))

    def testEachTagInGroupIsFromDisjointTagSets(self):
        raw_data = (
            '# tags: [ Mac Win Linux ]\n'
            '# tags: [ Batman Robin Superman ]\n'
            '# tags: [ Android Iphone ]\n'
            'crbug.com/23456 [ Android Mac Superman ] b1/s1 [ Failure ]\n'
            'crbug.com/23457 [ Iphone Win Robin ] b1/s2 [ Pass ]\n'
            'crbug.com/23458 [ Android Linux  ] b1/s3 [ Pass ]\n'
            'crbug.com/23459 [ Batman ] b1/s4 [ Skip ]\n')
        expectations_parser.TaggedTestListParser(raw_data)

    def testDuplicateTagsInGroupRaisesError(self):
        raw_data = (
            '# tags: [ Mac Win Linux ]\n'
            '# tags: [ Batman Robin Superman ]\n'
            'crbug.com/23456 [ Batman Batman Batman ] b1/s1 [ Failure ]\n')
        with self.assertRaises(expectations_parser.ParseError) as context:
            expectations_parser.TaggedTestListParser(raw_data)
        self.assertIn('3: The tag group contains '
                      'tags that are part of the same tag set\n',
                      str(context.exception))
        self.assertIn('  - Tags Batman, Batman and Batman are'
                      ' part of the same tag set', str(context.exception))
