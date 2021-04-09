========================
Scipion Empiar Depositor
========================

This project is a Scipion plugin to make depositions to https://www.ebi.ac.uk/pdbe/emdb/empiar

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

    git clone https://github.com/scipion-em/scipion-em-empiar.git
    scipion installp -p local/path/to/scipion-em-empiar --devel

2. **Download Aspera Connect:**

Go to https://www.ibm.com/aspera/connect/ and download the latest version.

3. Register an account in the EMPIAR deposition and Segmentation Annotation Tool

Go to https://www.ebi.ac.uk/pdbe/emdb/empiar/deposition/register/ and get an API token at **Get empiar-deposition API token** section

4.  Add the following variables at ~/.config/scipion/scipion.conf file:

.. code-block::

    ASCP = <aspera_binary_path> (usually it is located at ~/.aspera/connect/bin/ascp)
    ASPERA_SCP_PASS= <aspera_shares_user_password>
    EMPIAR_TOKEN = <empiar_token>