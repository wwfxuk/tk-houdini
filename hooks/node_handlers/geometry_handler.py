import sgtk

import hou


HookBaseClass = sgtk.get_hook_baseclass()


class GeometryNodeHandler(HookBaseClass):

    NODE_TYPE = "geometry"

    OUTPUT_PARM = "sopoutput"

    SGTK_CACHE_EXTENSION = "sgtk_cache_extension"

    def _add_identifier_parm_template(self, node, templates):
        sgtk_single_frame = self._build_single_file_parm(False)
        sgtk_single_frame.setJoinWithNext(True)
        templates.append(sgtk_single_frame)

        choices = self.get_work_template(node).keys["extension"].labelled_choices
        sgtk_cache_ext = hou.MenuParmTemplate(
            self.SGTK_CACHE_EXTENSION,
            "File Extension",
            choices.keys(),
            menu_labels=choices.values(),
            script_callback=self.generate_callback_script_str("refresh_file_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_cache_ext.setConditional(
            hou.parmCondType.DisableWhen,
            '{ use_sgtk != 1 }'
        )
        templates.append(sgtk_cache_ext)

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        index = parameter_group.index_of_template(self.OUTPUT_PARM)
        parameter_group.insert_template(index, sgtk_folder)

    def _update_template_fields(self, node, fields):
        super(GeometryNodeHandler, self)._update_template_fields(node, fields)
        extension_parm = node.parm(self.SGTK_CACHE_EXTENSION)
        extension = extension_parm.evalAsString()
        fields["extension"] = extension

    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        index = parameter_group.index_of_template(self.SGTK_FOLDER)
        parameter_group.pop_template(index)    

    def _populate_from_fields(self, node, fields):
        super(GeometryNodeHandler, self)._populate_from_fields(node, fields)
        sgtk_cache_extension = node.parm(self.SGTK_CACHE_EXTENSION)
        identifier = fields.get("extension", "geo")
        entries = sgtk_cache_extension.menuItems()
        index = entries.index(identifier)
        sgtk_cache_extension.set(index)