#!/usr/bin/env python
from setuptools import setup

setup(
    name="SnakeByte",
    version="0.1",
    description="Python components for building solid IRC scripts.",
    long_description="""\
While not yet usable on its own, this package will eventually provide a
complete set of components for building all common types of IRC scripts
quickly, easily, and reliably.""",
    author="Stephan Sokolow",
    author_email="http://www.ssokolow.com/ContactMe",  # No spam harvesting
    url="http://ssokolow.com/snakebyte/",
    packages=['snakebyte'],

    download_url="https://github.com/ssokolow/snakebyte/",
    zip_safe=True
)
