"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='scipion-em-empiar',
    version='1.0.1',
    description='A Scipion plugin to make depositions to EMPIAR',
    long_description=long_description,
    url='https://github.com/scipion-em/scipion-em-empiar',
    author='I2PC',
    author_email='scipion@cnb.csic.es',
    keywords='scipion empiar scipion-1.2',
    packages=find_packages(),
    install_requires=['empiar-depositor', 'jsonschema'],
    package_data={
       'empiar': ['EMPIAR_logo.png', 'empiar_deposition.schema.json', 'empiar_deposition_template.json'],
    }
)
