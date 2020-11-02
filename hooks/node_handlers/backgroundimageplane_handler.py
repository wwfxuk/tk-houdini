"""Hook class to handle Houdini 2D image read nodes.

Designed to inherit ``base_import_handler`` i.e. define the ``hook`` attribute
in your project configuration settings with the following inheritance:

.. code-block:: yaml
    :caption: env/includes/settings/tk-houdini_node_handlers.yml

    node_handlers.asset_step:
    - node_type: backgroundimageplane
      node_category: Object
      hook: "{self}/node_handlers/base_import_handler.py:{self}/node_handlers/backgroundimageplane_handler.py"
      work_template: houdini_asset_render
      publish_template: houdini_asset_publish_render
      extra_args:
        valid_file_types:
        - Image
        - Photoshop Image
        - Rendered Image
        - Texture

"""
import sgtk

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class BackgroundImagePlaneNodeHandler(HookBaseClass):
    """
    A node handler for image file input nodes in Houdini.
    """

    NODE_TYPE = "backgroundimageplane"
    NODE_CATEGORY = "Object"

    INPUT_PARM = "file"
    HOU_FILE_TYPE = hou.fileType.Image
