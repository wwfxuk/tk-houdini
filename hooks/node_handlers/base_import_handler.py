import sgtk

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class ImportNodeHandler(HookBaseClass):

    INPUT_PARM = None

    LASTEST_VERSION_STR = "<LATEST>"
    LATEST_APPR_VERSION_STR = "<LATEST APPROVED>"

    VERSION_POLICIES = [LASTEST_VERSION_STR, LATEST_APPR_VERSION_STR]

    #############################################################################################
    # houdini callback overrides
    #############################################################################################

    #############################################################################################
    # UI customisation
    #############################################################################################

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        index = parameter_group.index_of_template(self.INPUT_PARM)
        parameter_group.insert_template(index, sgtk_folder)

    def _setup_parms(self, node):
        pass

    def _create_sgtk_parms(self, node):
        templates = super(ImportNodeHandler, self)._create_sgtk_parms(node, hou=hou)


        

        return templates

    def _create_sgtk_folder(self, node):
        return super(ImportNodeHandler, self)._create_sgtk_folder(node, hou=hou)

    #############################################################################################
    # UI Callbacks
    #############################################################################################
    
    def _enable_sgtk(self, node, sgtk_enabled):
        pass

    def _get_all_versions(self, node):
        pass

    def _refresh_file_path(self, node, update_version=True):
        pass

    #############################################################################################
    # Utilities
    #############################################################################################
    
    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        pass

    def _populate_from_file_path(self, node, file_path, use_next_version):
        pass
