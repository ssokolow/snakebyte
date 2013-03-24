# Testing Instructions

1. Install Python 2.5, 2.6, 2.7, 3.1, 3.2, 3.3, PyPy, and Jython
2. `pip install tox`
3. `tox`

Ubuntu users can install all but Jython using this sequence of commands:

    sudo add-apt-repository ppa:fkrull/deadsnakes
    sudo apt-get update
    sudo apt-get install python{2.7,3.2} python{2.5,2.6,3.1,3.3}-complete pypy
    sudo pip install tox
    tox

**The repository-provided version of Jython 2.5.1 for Ubuntu 12.04 is broken.**
You will need to run `jython-installer-2.5.3.jar` from
[Jython.org](http://www.jython.org/) and then symlink `$PREFIX/bin/jython` into
 your `$PATH` to test under it.

# Known Issues

## Jython under Ubuntu 12.04 LTS

Jython 2.5.1, as included with Ubuntu 12.04 LTS, is incompatible with
virtualenv and, therefore, with the tox texting harness.

## Python/Jython 2.5 and PyPI

As of this writing, the tox+virtualenv+pip stack can't connect to PyPI under
Python 2.5 or Jython 2.5 without `--insecure`.

This is very complicated to resolve properly because Python 2.5's SSL module
expects SSLv2 to be available in OpenSSL but modern Ubuntu builds disable it
at compile time for security reasons.

(You need to install `libssl-dev` and, for unknown reasons, `libbluetooth-dev`,
rebuild either libssl or a patched Python 2.5, and then install the backported
`ssl` module and set `sitepackages = True` in `tox.ini`.)

While I wait for a proper resolution, I'll risk loading PyPI modules for 2.5
without SSL.
