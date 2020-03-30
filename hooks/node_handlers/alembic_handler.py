"""Hook class to handle Houdini Alembic write nodes.

Designed to inherit ``base_cache_handler`` i.e. define the ``hook`` attribute
in your project configuration settings with the following inheritance:


.. code-block:: yaml
    :caption: env/includes/settings/tk-houdini_node_handlers.yml

    node_handlers.shot_step:
    - node_type: alembic
      node_category: Driver
      hook: "{self}/node_handlers/base_export_handler.py:{self}/node_handlers/base_cache_handler.py:{self}/node_handlers/alembic_handler.py"
      work_template: houdini_shot_work_alembic_cache
      publish_template: houdini_shot_publish_alembic_cache
      extra_args:
        seq_work_template: houdini_shot_work_alembic_seq_cache
        seq_publish_template: houdini_shot_publish_alembic_seq_cache

"""
import sgtk

import hou


HookBaseClass = sgtk.get_hook_baseclass()


class AlembicNodeHandler(HookBaseClass):
    """
    Node handler for alembic export nodes in houdini.
    """

    NODE_TYPE = "alembic"

    OUTPUT_PARM = "filename"

    SGTK_ABC_INDENTIFIER = "sgtk_abc_identifier"

    def _create_sgtk_parms(self, node):
        """
        Create the parameters that are going to live within the sgtk folder.

        :param node: A :class:`hou.Node` instance.

        :rtype: list(:class:`hou.ParmTemplate`)
        """
        templates = super(AlembicNodeHandler, self)._create_sgtk_parms(node)

        templates[-1].setJoinWithNext(True)

        choices = self.get_work_template(node).keys["identifier"].labelled_choices
        sgtk_abc_identifier = hou.MenuParmTemplate(
            self.SGTK_ABC_INDENTIFIER,
            "Type Identifier",
            choices.keys(),
            menu_labels=choices.values(),
            script_callback=self.generate_callback_script_str("refresh_file_path"),
            script_callback_language=hou.scriptLanguage.Python,
        )
        sgtk_abc_identifier.setConditional(
            hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }"
        )
        sgtk_abc_identifier.setJoinWithNext(True)
        templates.append(sgtk_abc_identifier)

        sgtk_single_frame = self._build_single_file_parm(True)
        templates.append(sgtk_single_frame)

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
        main_folder = parameter_group.get("folder0")
        index = main_folder.index_of_template(self.OUTPUT_PARM)
        main_folder.insert_template(index, sgtk_folder)

    def _update_template_fields(self, node, fields):
        """
        Update template fields from the node's parameter values.

        :param node: A :class:`hou.Node` instance.
        :param dict fields: Template fields.
        """
        super(AlembicNodeHandler, self)._update_template_fields(node, fields)
        sgtk_abc_identifier = node.parm(self.SGTK_ABC_INDENTIFIER)
        abc_identifier = sgtk_abc_identifier.evalAsString()
        fields["identifier"] = abc_identifier

    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        """
        Remove all sgtk parameters from the node's parameter template group.

        :param ParmGroup parameter_group: The parameter group containing sgtk parameters.
        """
        images_folder = parameter_group.get("folder0")
        index = images_folder.index_of_template(self.SGTK_FOLDER)
        images_folder.pop_template(index)

    def _populate_from_fields(self, node, fields):
        """
        Populate the node from template fields.

        :param node: A :class:`hou.Node` instance.
        :param dict fields: The template fields.
        """
        super(AlembicNodeHandler, self)._populate_from_fields(node, fields)
        sgtk_abc_identifier = node.parm(self.SGTK_ABC_INDENTIFIER)
        identifier = fields.get("identifier", "geo")
        entries = sgtk_abc_identifier.menuItems()
        index = entries.index(identifier)
        sgtk_abc_identifier.set(index)
