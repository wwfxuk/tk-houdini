"""Hook class to handle Houdini 2D image read nodes.

Designed to inherit ``base_import_handler`` i.e. define the ``hook`` attribute
in your project configuration settings with the following inheritance:

.. code-block:: yaml
    :caption: env/includes/settings/tk-houdini_node_handlers.yml

    node_handlers.asset_step:
    - node_type: file
      node_category: Cop2
      hook: "{self}/node_handlers/base_import_handler.py:{self}/node_handlers/image_handler.py"
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

HookBaseClass = sgtk.get_hook_baseclass()


class ImageNodeHandler(HookBaseClass):
    """
    A node handler for image file input nodes in Houdini.
    """

    NODE_TYPE = "file"
    NODE_CATEGORY = "Cop2"

    INPUT_PARM = "filename1"

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        """
        Here is where you define where the sgtk folder is to be placed, but also
        any other parameters that you wish to add to the node.

        :param node: A :class:`hou.Node` instance.
        :param parameter_group: The node's :class:`ParmGroup`.
        :param sgtk_folder: A :class:`hou.ParmFolderTemplate` containing sgtk
            parameters.
        """
        index = parameter_group.index_of_template("stdswitcher")
        parameter_group.insert_template(index, sgtk_folder)
