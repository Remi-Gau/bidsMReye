#!/usr/bin/env python
from __future__ import annotations

import sys

# see https://github.com/python-versioneer/python-versioneer/issues/249#issuecomment-1038184056

sys.path.insert(0, ".")


from setuptools import setup

import versioneer


SETUP_REQUIRES = ["setuptools >= 30.3.0"]
SETUP_REQUIRES += ["wheel"] if "bdist_wheel" in sys.argv else []

if __name__ == "__main__":
    setup(
        setup_requires=SETUP_REQUIRES,
        version=versioneer.get_version(),
        cmdclass=versioneer.get_cmdclass(),
    )
