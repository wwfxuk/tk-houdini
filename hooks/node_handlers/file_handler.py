"""Hook class to handle Houdini file SOP nodes.

Designed to inherit ``base_import_handler`` i.e. define the ``hook`` attribute
in your project configuration settings with the following inheritance:

.. code-block:: yaml
    :caption: env/includes/settings/tk-houdini_node_handlers.yml

    node_handlers.shot_step:
    - node_type: file
      node_category: Sop
      hook: "{self}/node_handlers/base_import_handler.py:{self}/node_handlers/file_handler.py"
      work_template: houdini_shot_work_cache
      publish_template: houdini_shot_publish_cache
      extra_args:
        valid_file_types:
        - "Alembic Cache"
        - "Geometry Cache"

"""

import sgtk


HookBaseClass = sgtk.get_hook_baseclass()


class FileNodeHandler(HookBaseClass):
    """
    A node handler for file input nodes in Houdini.
    """

    INPUT_PARM = "file"
