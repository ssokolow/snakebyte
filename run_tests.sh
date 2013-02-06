#!/usr/bin/env bash
#TODO: Integrate this into setup.py once I can make "setup.py install" work

function print_error()   { printf '\033[1;31m%s\033[0m\n' "$*"; }
function print_status()  { printf '\033[1;34m%s\033[0m\n' "$*"; }
function print_success() { printf '\033[1;32m%s\033[0m\n' "$*"; }

function run() {
    "$@" || status=$(($? || status))
    printf "\n"
}

print_status " --== Test Suite (With Branch Coverage) ==--"
run nosetests
# TODO: Figure out how to get --cover-min-percentage working

print_status " --== Static Analysis (PyFlakes) ==--"
run pyflakes *.py

print_status " --== Coding Style Check (PEP8) ==--"
run pep8 *.py

print_status " --== Documentation Syntax Check (EPyDoc, reStructuredText) ==--"
run epydoc --config setup.cfg *.py

if [ "$status" ]; then
    print_error
    print_error "WARNING: This result will cause Travis CI to announce a test run"
    print_error "         failure if it is the newest commit when you next push to"
    print_error "         this branch to GitHub."
else
    print_success "No failures detected."
fi
exit $status
