"""Hook class to handle Houdini bgeo cache read nodes.

Designed to inherit ``base_cache_handler`` i.e. define the ``hook`` attribute
in your project configuration settings with the following inheritance:

.. code-block:: yaml
    :caption: env/includes/settings/tk-houdini_node_handlers.yml

    node_handlers.asset_step:
    - node_type: geometry
      node_category: Driver
      hook: "{self}/node_handlers/base_export_handler.py\
          :{self}/node_handlers/base_cache_handler.py\
          :{self}/node_handlers/geometry_handler.py\
          :{self}/node_handlers/rop_geometry_handler.py"
      work_template: houdini_asset_work_cache
      publish_template: houdini_asset_publish_cache
      extra_args:
        seq_work_template: houdini_asset_work_seq_cache
        seq_publish_template: houdini_asset_publish_seq_cache

"""
import sgtk


HookBaseClass = sgtk.get_hook_baseclass()


class RopGeometryNodeHandler(HookBaseClass):
    """
    Node handler for geometry export nodes in Houdini.
    """

    NODE_TYPE = "rop_geometry"
    NODE_CATEGORY = "Sop"
