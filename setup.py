from setuptools import setup

from timebook import __version__

setup(
    name='timebook',
    version='.'.join(str(bit) for bit in __version__),
    url='http://bitbucket.org/trevor/timebook/',
    description='track what you spend time on',
    author='Trevor Caira',
    author_email='trevor@caira.com',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Utilities',
    ],
    packages=['timebook'],
    scripts=['t'],
)
