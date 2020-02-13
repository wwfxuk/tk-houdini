import sgtk

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class FileNodeHandler(HookBaseClass):

    INPUT_PARM = "file"