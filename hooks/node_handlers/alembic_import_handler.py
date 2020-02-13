import sgtk

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class AlembicImportNodeHandler(HookBaseClass):

    INPUT_PARM = "fileName"
