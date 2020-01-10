import sgtk


HookBaseClass = sgtk.get_hook_baseclass()


class AlembicNodeHandler(HookBaseClass):

    NODE_TYPE = "alembic"

    OUTPUT_PARM = "filename"

    def _customise_parameter_group(self, parameter_group, sgtk_folder):
        main_folder = parameter_group.get("folder0")
        index = main_folder.index_of_template(self.OUTPUT_PARM)
        main_folder.insert_template(index, sgtk_folder)
