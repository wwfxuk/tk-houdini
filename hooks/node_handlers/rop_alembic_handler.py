"""Hook class to handle Houdini Alembic write nodes.

Designed to inherit ``base_cache_handler`` i.e. define the ``hook`` attribute
in your project configuration settings with the following inheritance:


.. code-block:: yaml
    :caption: env/includes/settings/tk-houdini_node_handlers.yml

    node_handlers.shot_step:
    - node_type: rop_alembic
      node_category: Sop
      hook: "{self}/node_handlers/base_export_handler.py\
            :{self}/node_handlers/base_cache_handler.py\
            :{self}/node_handlers/alembic_handler.py\
            :{self}/node_handlers/rop_alembic_handler.py"
      work_template: houdini_shot_work_alembic_cache
      publish_template: houdini_shot_publish_alembic_cache
      extra_args:
        seq_work_template: houdini_shot_work_alembic_seq_cache
        seq_publish_template: houdini_shot_publish_alembic_seq_cache

"""
import sgtk


HookBaseClass = sgtk.get_hook_baseclass()


class RopAlembicNodeHandler(HookBaseClass):
    """
    Node handler for rop alembic export nodes in houdini.
    """

    NODE_TYPE = "rop_alembic"
    NODE_CATEGORY = "Sop"
