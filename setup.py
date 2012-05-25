from setuptools import setup

from timebook import get_version

setup(
    name='timebook',
    version=get_version(),
    url='http://bitbucket.org/latestrevision/timebook/',
    description='track what you spend time on',
    author='Trevor Caira, Adam Coddington',
    author_email='me@adamcoddington.net',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Utilities',
    ],
    packages=['timebook', 'timebook.migrations',],
    entry_points={'console_scripts': [
        't = timebook.cmdline:run_from_cmdline']},
    install_requires = [
            'python-dateutil<2.0',
        ]
)
