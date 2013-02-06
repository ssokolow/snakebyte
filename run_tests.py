#!/usr/bin/env python2
"""Temporary test runner for projects not yet ready to `setup.py install`

(Using this filename is both a reminder to the developer to remedy the problem
and a courtesy to users who oftem assume "setup.py" means "setup.py install")

:todo: Integrate this into setup.py once I can make "setup.py install" work
:todo: Make colorization support cross-platform (http://tinyurl.com/bymwyfp)
:todo: Explore the feasibility of displaying all messages using ``logging``
"""

import os, sys
from subprocess import call

retcode = 0
def test(msg, command):
    global retcode

    print('\x1b[1;34m --== %s ==-- \x1b[0m' % msg)
    retcode = call(command) or retcode

if __name__ == '__main__':
    candidates = [x for x in os.listdir('.') if x.endswith('.py') or
            os.path.exists(os.path.join(x, '__init__.py'))]

    # TODO: Figure out how to get --cover-min-percentage working
    test("Test Suite (With Branch Coverage)", "nosetests")
    test("Static Analysis (PyFlakes)", ['pyflakes'] + candidates)
    test("Coding Style Check (PEP8)", "pep8")
    test("Documentation Syntax Check (EPyDoc, reStructuredText)",
        ["epydoc", "--config", "setup.cfg"] + candidates)

    if retcode:
        print("\x1b[1;31m\n"
              "WARNING: This result will cause Travis CI to announce a test\n"
              "         run failure if it is the newest commit when you next\n"
              "         push this branch to GitHub.\x1b[0m")
    else:
        print("\x1b[1;32mNo failures detected.\x1b[0m")
    sys.exit(retcode)
