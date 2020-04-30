"""Hook class to handle Houdini Alembic read nodes.

Designed to inherit ``base_import_handler`` i.e. define the ``hook`` attribute
in your project configuration settings with the following inheritance:


.. code-block:: yaml
    :caption: env/includes/settings/tk-houdini_node_handlers.yml

    node_handlers.shot_step:
    - node_type: alembicarchive
      node_category: Object
      hook: "{self}/node_handlers/base_import_handler.py:{self}/node_handlers/alembicarchive_import_handler.py"
      work_template: houdini_shot_work_alembic_cache
      publish_template: houdini_shot_publish_alembic_cache
      extra_args:
        valid_file_types:
        - "Alembic Cache"

"""
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()


class AlembicArchiveImportNodeHandler(HookBaseClass):
    """
    A node handler for alembic input nodes in Houdini.
    """
    NODE_TYPE = "alembicarchive"
    NODE_CATEGORY = "Object"

    INPUT_PARM = "fileName"
