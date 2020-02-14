import sgtk

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class ImageNodeHandler(HookBaseClass):

    INPUT_PARM = "filename1"

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        index = parameter_group.index_of_template("stdswitcher")
        parameter_group.insert_template(index, sgtk_folder)
