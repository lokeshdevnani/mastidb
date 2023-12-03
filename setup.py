import os
from setuptools import setup
from mypyc.build import mypycify

src_dir = "mastidb"
ext_modules = [os.path.join(src_dir, f) for f in os.listdir(src_dir) if f.endswith('.py')]


setup(name='mastidb', 
      version='0.1',
      author='Lokesh Devnani', 
      author_email='lokeshdevnani@gmail.com',
      keywords=['database', 'olap', 'storage-engine'],
      packages=['mastidb'],
      ext_modules=mypycify(ext_modules, 
                           opt_level="3", debug_level="1"),
      entry_points={
        'console_scripts': [
            'mastidb=mastidb.cli:mastidb',
        ],
    },
)
