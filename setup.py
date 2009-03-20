from setuptools import setup

from timebook import get_version

setup(
    name='timebook',
    version=get_version(),
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
    entry_points={'console_scripts': [
        't = timebook.cmdline:run_from_cmdline']},
)
