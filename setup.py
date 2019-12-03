# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
from os         import path


readme_path = path.join(path.dirname(__file__), 'README')

setup(
  name='python-cvmfsutils',
  version='0.4.1',
  url='http://cernvm.cern.ch',
  author='Rene Meusel',
  author_email='rene.meusel@cern.ch',
  license='(c) 2015 CERN - BSD License',
  description='Inspect CernVM-FS repositories',
  # read the first paragraph
  long_description=open(readme_path).read().split("\n\n")[0],
  classifiers= [
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: BSD License',
    'Natural Language :: English',
    'Operating System :: POSIX :: Linux',
    'Operating System :: MacOS :: MacOS X',
    'Topic :: Software Development',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Topic :: System :: Filesystems',
    'Topic :: System :: Networking :: Monitoring',
    'Topic :: System :: Systems Administration'
  ],
  packages=find_packages(),
  scripts=['utils/big_catalogs', 'utils/catdirusage'],
  zip_safe=False,
  test_suite='cvmfs.test',
  tests_require='xmlrunner',
  install_requires=[ # for pip; don't forget the similar RPM dependencies!
    'python-dateutil >= 1.4.1',
    'requests >= 1.1.0',
    'M2Crypto >= 0.20.0'
  ]
)
