#!/usr/bin/env python3
from setuptools import setup, find_packages

from ganttcharts import __version__


setup(
    name='gantt-charts',
    version=__version__,
    author='Thomas Leese',
    author_email='inbox@thomasleese.me',
    packages=find_packages(exclude=['tests*']),
    zip_safe=True,
    setup_requires=[
        'Sphinx >=1.3, <2'
    ],
    install_requires=[
        'Cerberus >=0.9, <1',
        'Flask >=0.10, <1',
        'passlib >=1.6, <2',
        'SQLAlchemy >=1.0, <2',
        'numpy >=1.9, <2',
        'pandas >=0.16, <1',
        'psycopg2 >=2.5, <3',
        'alembic >=0.7, <1',
        'WTForms >=2.0, <3',
        'WTForms-JSON >=0.2, <1',
        'reportlab >=3.2, <4',
    ],
    test_suite='tests',
    entry_points={
        'console_scripts': [
            'ganttchartsctl = ganttcharts.cli.__main__:main'
        ]
    }
)
