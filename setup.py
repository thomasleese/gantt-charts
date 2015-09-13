#!/usr/bin/env python3
from setuptools import setup, find_packages

from ganttchart import __version__


setup(
    name='ganttchart',
    version=__version__,
    author='Tom Leese',
    author_email='inbox@tomleese.me.uk',
    packages=find_packages(exclude=['tests*']),
    zip_safe=True,
    setup_requires=[
        'nose >=1.3, <2',
        'Sphinx >=1.3, <2'
    ],
    install_requires=[
        'Flask >=0.10, <1',
        'passlib >=1.6, <2',
        'SQLAlchemy >=0.9, <1',
        'pandas >=0.16, <1',
        'psycopg2 >=2.5, <3',
        'alembic >=0.7, <1',
        'WTForms >=2.0, <3',
        'WTForms-JSON >=0.2, <1',
    ],
    test_suite='nose.collector',
)
