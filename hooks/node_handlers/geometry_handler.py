"""Hook class to handle Houdini bgeo cache read nodes.

Designed to inherit ``base_cache_handler`` i.e. define the ``hook`` attribute
in your project configuration settings with the following inheritance:

.. code-block:: yaml
    :caption: env/includes/settings/tk-houdini_node_handlers.yml

    node_handlers.asset_step:
    - node_type: geometry
      node_category: Driver
      hook: "{self}/node_handlers/base_export_handler.py:{self}/node_handlers/base_cache_handler.py:{self}/node_handlers/geometry_handler.py"
      work_template: houdini_asset_work_cache
      publish_template: houdini_asset_publish_cache
      extra_args:
        seq_work_template: houdini_asset_work_seq_cache
        seq_publish_template: houdini_asset_publish_seq_cache

"""
import sgtk

import hou


HookBaseClass = sgtk.get_hook_baseclass()


class GeometryNodeHandler(HookBaseClass):
    """
    Node handler for geometry export nodes in Houdini.
    """

    NODE_TYPE = "geometry"

    OUTPUT_PARM = "sopoutput"

    SGTK_CACHE_EXTENSION = "sgtk_cache_extension"

    def _create_sgtk_parms(self, node):
        """
        Create the parameters that are going to live within the sgtk folder.

        :param node: A :class:`hou.Node` instance.

        :rtype: list(:class:`hou.ParmTemplate`)
        """
        templates = super(GeometryNodeHandler, self)._create_sgtk_parms(node)

        templates[-1].setJoinWithNext(True)

        sgtk_single_frame = self._build_single_file_parm(False)
        sgtk_single_frame.setJoinWithNext(True)
        templates.append(sgtk_single_frame)

        choices = self.get_work_template(node).keys["extension"].labelled_choices

        ordered_keys = sorted(choices.keys())
        ordered_values = []
        for key in ordered_keys:
            ordered_values.append(choices[key])

        sgtk_cache_ext = hou.MenuParmTemplate(
            self.SGTK_CACHE_EXTENSION,
            "File Extension",
            ordered_keys,
            menu_labels=ordered_values,
            script_callback=self.generate_callback_script_str("refresh_file_path"),
            script_callback_language=hou.scriptLanguage.Python,
        )
        sgtk_cache_ext.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        templates.append(sgtk_cache_ext)

        return templates

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        """
        Here is where you define where the sgtk folder is to be placed, but also
        any other parameters that you wish to add to the node.

        :param node: A :class:`hou.Node` instance.
        :param parameter_group: The node's :class:`ParmGroup`.
        :param sgtk_folder: A :class:`hou.ParmFolderTemplate` containing sgtk
            parameters.
        """
        index = parameter_group.index_of_template(self.OUTPUT_PARM)
        parameter_group.insert_template(index, sgtk_folder)

    def _update_template_fields(self, node, fields):
        """
        Update template fields from the node's parameter values.

        :param node: A :class:`hou.Node` instance.
        :param dict fields: Template fields.
        """
        super(GeometryNodeHandler, self)._update_template_fields(node, fields)
        extension_parm = node.parm(self.SGTK_CACHE_EXTENSION)
        extension = extension_parm.evalAsString()
        fields["extension"] = extension

    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        """
        Remove all sgtk parameters from the node's parameter template group.

        :param ParmGroup parameter_group: The parameter group containing sgtk parameters.
        """
        index = parameter_group.index_of_template(self.SGTK_FOLDER)
        parameter_group.pop_template(index)

    def _populate_from_fields(self, node, fields):
        """
        Populate the node from template fields.

        :param node: A :class:`hou.Node` instance.
        :param dict fields: The template fields.
        """
        super(GeometryNodeHandler, self)._populate_from_fields(node, fields)
        sgtk_cache_extension = node.parm(self.SGTK_CACHE_EXTENSION)
        identifier = fields.get("extension", "geo")
        entries = sgtk_cache_extension.menuItems()
        index = entries.index(identifier)
        sgtk_cache_extension.set(index)
