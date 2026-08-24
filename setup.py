import os
from setuptools import setup
from mypyc.build import mypycify

src_dir = "mastidb"
file_list = set(os.listdir(src_dir)) - set(('cli.py', '__init__.py', 'demo.py'))
sources = sorted(os.path.join(src_dir, f) for f in file_list if f.endswith('.py'))

ext_modules = mypycify(sources, opt_level="3", debug_level="1")
for extension in ext_modules:
    # Installing without a C toolchain should still give you a working (slower)
    # MastiDB: the .py sources ship alongside the compiled modules, so marking
    # the extensions optional turns a build failure into a warning.
    extension.optional = True

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md'), encoding='utf-8') as readme:
    long_description = readme.read()

# Runtime dependencies. Floors, not pins - pinned versions belong in
# requirements.txt (the dev/build environment), not in a library's metadata.
# mypy is needed to *build* this package, since setup.py compiles with mypyc.
install_requires = [
    'pyroaring>=0.4',       # roaring bitmap indexes
    'mo-sql-parsing>=9.0',  # SQL -> dict
    'mo-parsing>=8.0',      # ParseException surfaced by the console
    'click>=8.0',           # CLI
    'rich>=13.0',           # console tables
    'prompt-toolkit>=3.0',  # console REPL
    'Pygments>=2.10',       # SQL highlighting in the REPL
]

setup(name='mastidb', 
      version='0.4.0',
      author='Lokesh Devnani', 
      author_email='lokeshdevnani@gmail.com',
      description="A 'serious' OLAP database engine written in Python",
      long_description=long_description,
      long_description_content_type='text/markdown',
      url='https://github.com/lokeshdevnani/mastidb',
      project_urls={
        'Source': 'https://github.com/lokeshdevnani/mastidb',
        'Design doc': 'https://github.com/lokeshdevnani/mastidb/blob/main/ARCHITECTURE.md',
      },
      license='MIT',
      keywords=['database', 'olap', 'storage-engine'],
      classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Database :: Database Engines/Servers',
      ],
      packages=['mastidb'],
      python_requires='>=3.9',
      install_requires=install_requires,
      extras_require={
        'dev': ['mypy>=1.7', 'types-Pygments'],
      },
      ext_modules=ext_modules,
      entry_points={
        'console_scripts': [
            'mastidb=mastidb.cli:mastidb',
        ],
    },
)
