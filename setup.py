#!/usr/bin/env python3
# coding: utf-8
"""
@author: Ping Qiu  qiuping1@genomics.cn
@last modified by: Ping Qiu
@file:setup.py
@time:2021/03/02
"""
from setuptools import setup, find_packages
import sys
from pathlib import Path

if sys.version_info < (3, 6):
    sys.exit('stereo requires Python >= 3.6')


setup(
    name='stereo',
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    description='Spatial transcriptomic analysis in python.',
    long_description=Path('README.md').read_text('utf-8'),
    url='https://github.com/BGIResearch/stereopy-release',
    author='BGIResearch',
    author_email='qiuping1@genomics.cn',
    python_requires='>=3.6',
    install_requires=[
        l.strip() for l in Path('requirements.txt').read_text('utf-8').splitlines()
    ],
    extras_require=dict(
        visualization=['bokeh>=1.4.0'],
        doc=['sphinx>=3.2'],
        test=['pytest>=4.4', 'pytest-nunit'],
    ),
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        'Topic :: Scientific/Engineering :: Visualization',
    ],
)
