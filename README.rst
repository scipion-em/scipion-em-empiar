========================
Scipion Empiar Depositor
========================

This project is a Scipion plugin to make depositions to https://www.ebi.ac.uk/pdbe/emdb/empiar or to download raw data.

.. image:: https://img.shields.io/pypi/v/scipion-em-empiar.svg
        :target: https://pypi.python.org/pypi/scipion-em-empiar
        :alt: PyPI release

.. image:: https://img.shields.io/pypi/l/scipion-em-empiar.svg
        :target: https://pypi.python.org/pypi/scipion-em-empiar
        :alt: License

.. image:: https://img.shields.io/pypi/pyversions/scipion-em-empiar.svg
        :target: https://pypi.python.org/pypi/scipion-em-empiar
        :alt: Supported Python versions

.. image:: https://img.shields.io/sonar/quality_gate/scipion-em_scipion-em-empiar?server=https%3A%2F%2Fsonarcloud.io
        :target: https://sonarcloud.io/dashboard?id=scipion-em_scipion-em-empiar
        :alt: SonarCloud quality gate

.. image:: https://img.shields.io/pypi/dm/scipion-em-empiar
        :target: https://pypi.python.org/pypi/scipion-em-empiar
        :alt: Downloads

=====
Setup
=====

In order to install the plugin follow these instructions:

1. **Install this plugin:**

.. code-block::

    scipion installp -p scipion-em-empiar

or through the **plugin manager** by launching Scipion and following **Configuration** >> **Plugins**


Alternatively, in devel mode:


.. code-block::

    git clone -b devel https://github.com/scipion-em/scipion-em-empiar.git
    scipion installp -p local/path/to/scipion-em-empiar --devel

2. **Download Aspera Connect:**

Go to https://www.ibm.com/aspera/connect/ and download the latest version.

3. Register an account in the EMPIAR deposition and Segmentation Annotation Tool

Go to https://www.ebi.ac.uk/pdbe/emdb/empiar/deposition/register/ and get an API token at **Get empiar-deposition API token** section

4.  Open scipion's config file 'scipion3 config --show' and add the following variables:

.. code-block::

    ASCP = <aspera_binary_path> (usually it is located at $HOME/.aspera/connect/bin/ascp)
    ASPERA_SCP_PASS= <aspera_shares_user_password>
    EMPIAR_TOKEN = <empiar_token>
