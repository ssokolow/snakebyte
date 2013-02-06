#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A selection of lexers for tokenizing shell command lines

:todo: Figure out how to remove shlex from the coverage report
"""

__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPL 3.0 or later"
__docformat__ = "restructuredtext en"

import logging, shlex
log = logging.getLogger(__name__)

#: Just an internal convenience to avoid duplication
_not_implemented_msg = ("This class merely specifies an interface. "
                        "You must subclass it to use it.")

class LexerInterface(object):
    """A template for creating lexers which take parameters both on
    initialization and on being invoked.

    Simple functions which reproduce the method signature defined by
    `__call__` are also valid as lexers which have no configuration or
    persisted state, provided that they still have a ``name`` member
    which exposes a textual ID for the lexer.
    """

    name = None  #: A textual ID for the lexer following HTML/XML ID rules

    def __init__(self, *args, **kwargs):
        """Override this if you need the lexer to take configuration
        options or to initialize state.

        :attention: All implementations of this should accept ``*args``
            and ``**kwargs`` for forward-compatibility with future
            extensions to this API.
        """
        raise NotImplementedError(_not_implemented_msg)

    def __call__(self, cmd_string, commands):
        """Parse a command line into a ``sys.argv``-compatible list.

        :Parameters:
            cmd_string : basestring
                A raw string such as ``ls -l *.py``
            commands : dict
                A dict mapping valid ``argv[0]`` values to
                ``(opts_list, arg_test_cb)`` tuples.

                  ``opts_list``: ``list``
                    A list of values which the lexer should consider valid
                    arguments for the command given as the dict key.
                  ``arg_test_cb``: ``function`` or ``None``
                    A callable which tests the validity of a command-line
                    argument (eg. a filename). It takes two parameters:

                      ``candidate_str`` : ``basestring``
                        The string to be tested for validity
                      ``argv`` : ``list``
                        The list of tokens already parsed (**do not modify**)

        :attention:
            - Lexers are expected to return an empty list if given an empty
              string, **not** a list containing an empty string.
            - Lexers are free to use as much or as little data from
              ``commands`` as they choose (or to ignore it entirely).
              It is merely provided as a means for commands to provide parsing
              hints to more advanced lexers.
            - For future-compatibility, lexers should deal gracefully with
              non-string values in ``opts_list``.
            - ``arg_test_cb`` should have no side-effects (with the possible
              exception of maintaining a cache for expensive lookups).

        :warning:
            - Behaviour is undefined if ``arg_test_cb`` modifies ``argv``.
            - Lexers may call ``arg_test_cb`` repeatedly (possibly ``N**2``
              times where ``N`` is the number of tokens eventually found)
              and, as such, testing functions should optimize and cache data
              appropriately.


        :rtype: ``list``
        :returns: A ``sys.argv``-compatible list of command line tokens

        :raises ValueError: Failed to parse the provided command line.
        """
        raise NotImplementedError(_not_implemented_msg)

def mirc_lexer(cmd_string, commands):
    """Pseudo-lexer which implements mIRC-style command-line parsing.

    The string is split at the first whitespace into two parts:

    #. The command
    #. The single argument the command will receive

    :Parameters:
        - `cmd_string` A raw command-line string
        - `commands` Ignored. (Required by the API)

    :rtype: ``list``
    :returns: A ``sys.argv``-compatible list of command line tokens
    """
    return cmd_string.split(None, 1)
mirc_lexer.name = 'mirc'

def posix_lexer(cmd_string, commands):
    """This lexer implements POSIX-like command-line parsing.

    More specifically, it wraps Python's ``shlex.split`` in the default
    POSIX-like mode.

    :Parameters:
        - `cmd_string` A raw command-line string
        - `commands` Ignored. (Required by the API)

    :rtype: ``list``
    :returns: A ``sys.argv``-compatible list of command line tokens

    :raises ValueError: Failed to parse the provided command line.
    """

    # If None somehow gets passed in, prevent it from triggering a stdin leak.
    return shlex.split(cmd_string or '')
posix_lexer.name = 'posix'

#TODO: Implement the smart lexer

#: All usable lexers in this module
LEXERS = [mirc_lexer, posix_lexer]
