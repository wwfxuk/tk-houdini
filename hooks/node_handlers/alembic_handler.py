import sgtk

import hou


HookBaseClass = sgtk.get_hook_baseclass()


class AlembicNodeHandler(HookBaseClass):

    NODE_TYPE = "alembic"

    OUTPUT_PARM = "filename"

    SGTK_ABC_INDENTIFIER = "sgtk_abc_identifier"
    SGTK_SINGLE_FRAME = "sgtk_single_frame"

    def _is_single_frame(self):
        node = hou.pwd()
        sgtk_single_frame = node.parm(self.SGTK_SINGLE_FRAME)
        if sgtk_single_frame:
            return bool(sgtk_single_frame.eval())
        else:
            return True

    @property
    def work_template(self):
        if self._is_single_frame():
            return self._work_template
        else:
            return self._get_template("seq_work_template")

    @property
    def publish_template(self):
        if self._is_single_frame():
            return self._publish_template
        else:
            return self._get_template("seq_publish_template")

    def _add_identifier_parm_template(self, templates):
        choices = self.work_template.keys["identifier"].labelled_choices
        sgtk_abc_identifier = hou.MenuParmTemplate(
            self.SGTK_ABC_INDENTIFIER,
            "Type Identifier",
            choices.keys(),
            menu_labels=choices.values(),
            script_callback=self.generate_callback_script_str("refresh_file_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_abc_identifier.setConditional(
            hou.parmCondType.DisableWhen,
            '{ use_sgtk != 1 }'
        )
        sgtk_abc_identifier.setJoinWithNext(True)
        templates.append(sgtk_abc_identifier)

        sgtk_single_frame = hou.ToggleParmTemplate(
            self.SGTK_SINGLE_FRAME,
            "Single Frame",
            default_value=True,
            script_callback=self.generate_callback_script_str("refresh_file_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_single_frame.setConditional(
            hou.parmCondType.DisableWhen,
            '{ use_sgtk != 1 }'
        )
        templates.append(sgtk_single_frame)

    def _customise_parameter_group(self, parameter_group, sgtk_folder):
        main_folder = parameter_group.get("folder0")
        index = main_folder.index_of_template(self.OUTPUT_PARM)
        main_folder.insert_template(index, sgtk_folder)

    def _update_template_fields(self, node, fields):
        super(AlembicNodeHandler, self)._update_template_fields(node, fields)
        sgtk_abc_identifier= node.parm(self.SGTK_ABC_INDENTIFIER)
        abc_identifier = sgtk_abc_identifier.evalAsString()
        fields["identifier"] = abc_identifier

    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        images_folder = parameter_group.get("folder0")
        index = images_folder.index_of_template(self.SGTK_FOLDER)
        images_folder.pop_template(index)