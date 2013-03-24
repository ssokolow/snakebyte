#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test Suite for shell lexer code for SnakeByte FServe

:todo: Figure out how to have all tests for concrete lexers inherit from a
       base class with a single definition of the tests for API compliance
       without having Nose attempt to run the tests in the base class.
"""

__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 3.0 or later"
__docformat__ = "restructuredtext en"

import logging, sys
log = logging.getLogger(__name__)

if sys.version_info[0] == 2 and sys.version_info[1] < 7:  # pragma: no cover
    import unittest2 as unittest
    unittest  # Silence erroneous PyFlakes warning
else:                                                     # pragma: no cover
    import unittest

from snakebyte.shell_lexers import LexerInterface, mirc_lexer, posix_lexer

class TestLexerInterface(unittest.TestCase):
    """Test that the lexer interface is accurately unimplemented."""
    def test_abstractness(self):
        """Test that LexerInterface is suitably not implemented."""
        # Must not be possible to instantiate without subclassing
        self.assertRaises(NotImplementedError, LexerInterface)

        # Can't be a static or class method
        self.assertRaises(TypeError, LexerInterface.__call__)

        # Sneaky trick to let me test __call__
        LexerInterface.__init__ = lambda x: None
        self.assertRaises(NotImplementedError, LexerInterface(), None, None)

class TestMircLexer(unittest.TestCase):
    """Test that the mIRC lexer is accurately dumb."""

    test_pairs = {
            '': [],
            'cmd': ['cmd'],
            'ls -l': ['ls', '-l'],
            'cd --version': ['cd', '--version'],
            'foo My File.bin': ['foo', 'My File.bin'],
            'bar the "thing" thing.txt': ['bar', 'the "thing" thing.txt'],
            "bar the 'thing' thing.abc": ['bar', "the 'thing' thing.abc"],
            'bar the "A B C" thing.xyz': ['bar', 'the "A B C" thing.xyz'],
            "bar the 'A B C' thing.ijk": ['bar', "the 'A B C' thing.ijk"],
            "baz The O'Neill story.txt": ['baz', "The O'Neill story.txt"],
    }

    bad_hints = {
            'foo': (['My'], None),
            'bar': (['the'], None),
            'baz': ([], lambda x, y: True),  # pragma: no cover
    }  #: Broken hints that, if followed, cause tests to fail

    def test_basic_functionality(self):
        """Test basic mIRC lexer functionality"""
        for inStr, outList in self.test_pairs.items():
            self.assertEqual(mirc_lexer(inStr, {}), outList)

    def test_ignore_hints(self):
        """Test that mIRC lexer ignores any provided hints"""
        for inStr, outList in self.test_pairs.items():
            self.assertEqual(mirc_lexer(inStr, self.bad_hints), outList)

    def test_name_accessibility(self):
        """Test that mIRC lexer exposes a name properly"""
        self.assertEqual(mirc_lexer.name, 'mirc',
                "Classes or functions, lexers require a 'name' member.")

class TestPosixLexer(unittest.TestCase):
    """Test that the POSIX lexer is accurately featureful."""

    test_pairs = {
            '': [],
            'cmd': ['cmd'],
            'ls -l': ['ls', '-l'],
            'cd --version': ['cd', '--version'],
            'foo My File.bin': ['foo', 'My', 'File.bin'],
            'bar the\r"thing" thing.txt': ['bar', 'the', "thing", 'thing.txt'],
            "bar the\n'thing' thing.abc": ['bar', "the", 'thing', "thing.abc"],
            'bar the  "A B C" thing.xyz': ['bar', 'the', "A B C", 'thing.xyz'],
            "bar the 'A B\tC' thing.ij": ['bar', "the", 'A B\tC', "thing.ij"],
            "baz \"O'Neill\r\n story.txt\"": ['baz', "O'Neill\r\n story.txt"],
            "'spaced command' foo.txt": ['spaced command', 'foo.txt'],
            "America is #1.epub": ['America', "is", "#1.epub"],  # comments
            "1!2@3$4$5%6^7&8*9(0)": ["1!2@3$4$5%6^7&8*9(0)"],  # non-wordchars
            "'\"' \"\\'\" \"\\\"\"": ['"', "\\'", '"'],  # escapes and quoting
    }

    bad_hints = {
            'bar': (['A', 'B', 'A B', 'C'], None),
            'bar': (["O'Neill"], None),
            'America': ([], lambda x, y: True),  # pragma: no cover
    }  #: Broken hints that, if followed, cause tests to fail

    def test_stdin_safety(self):
        """Test that POSIX lexer doesn't blindly pass None to shlex.split()"""
        self.assertEqual(posix_lexer(None, {}), [],
                "POSIX lexer must not let shlex.split() treat None input as "
                "an excuse to read from stdin.")

    def test_bad_quoting(self):
        """Test reaction to unbalanced quotes"""
        self.assertRaises(ValueError, posix_lexer,
                "The O'Neill story.txt", {})
        self.assertRaises(ValueError, posix_lexer,
                'My 25" afro.pdf', {})

    def test_basic_functionality(self):
        """Test basic POSIX lexer functionality"""
        for inStr, outList in self.test_pairs.items():
            self.assertEqual(posix_lexer(inStr, {}), outList)

    def test_quoting_and_escapes(self):
        """Test POSIX lexer quoting and escapes"""

        # Basic quoting
        self.assertEqual(posix_lexer('"1  2"a \' 4\' "5\t\r\n6" " "\' \'', {}),
                ['1  2a', ' 4', '5\t\r\n6', '  '],
                "Single and double quotes must not split/munge whitespace")
        self.assertEqual(posix_lexer(r'''"'" '"' ''', {}), ["'", '"'],
                "Single and double quotes must be able to quote each other")

        # Escaping
        self.assertEqual(posix_lexer(r'"\""', {}), ['"'],
                "Double quotes must process escapes")
        self.assertEqual(posix_lexer(r'foo\" bar', {}), ['foo"', 'bar'],
                "Escapes must be allowed outside of quotes")

        # Quote stripping
        self.assertEqual(posix_lexer(r'"Quotes"Are"Stripped"Out', {}),
                ['QuotesAreStrippedOut'],
                "POSIX parsing should strip out unescaped double quotes")
        self.assertEqual(posix_lexer(r"'Quotes'Are'Stripped'Out", {}),
                ['QuotesAreStrippedOut'],
                "POSIX parsing should strip out unescaped single quotes")

        self.assertEqual(posix_lexer(r"foo '' bar", {}), ['foo', '', 'bar'],
                "In POSIX rules, quotes allow empty tokens")

        # In POSIX rules, can't even quote a quote inside single quotes
        self.assertRaises(ValueError, posix_lexer, r"'\''", {})

    def test_ignore_hints(self):
        """Test that POSIX lexer ignores any provided hints"""
        for inStr, outList in self.test_pairs.items():
            self.assertEqual(posix_lexer(inStr, self.bad_hints), outList)

    def test_name_accessibility(self):
        """Test that POSIX lexer exposes a name properly"""
        self.assertEqual(posix_lexer.name, 'posix',
                "Classes or functions, lexers require a 'name' member.")
