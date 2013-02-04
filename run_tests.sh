#!/bin/sh
#TODO: Integrate this into setup.py once I can make "setup.py install" work

nosetests -v --with-coverage --cover-tests --cover-branches || status=$?
pyflakes *.py || status=$(($? || status))
pep8 --show-source --show-pep8 *.py || status=$(($? || status))
epydoc -v --simple-term --docformat=restructuredtext --fail-on-docstring-warning *.py || status=$(($? || status))
exit $status
