import sgtk

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class ArnoldNodeHandler(HookBaseClass):

    NODE_TYPE = "arnold"

    OUTPUT_PARM = "ar_picture"

    # aovs
    AOV_COUNT = "ar_aovs"
    AOV_NAME_TMPL = "ar_aov_exr_layer_name{}"
    AOV_FILE_TMPL = "ar_aov_separate_file{}"

    # mtlx
    AR_MATERIALX_FILE = "ar_materialx_file"

    # ass
    AR_ASS_FILE = "ar_ass_file"

    # shotgun
    SGTK_AOV_NAME_TMPL = "sgtk_aov_exr_layer_name{}"

    # templates
    MTLX_WORK_TEMPLATE = "mtlx_work_template"
    ASS_WORK_TEMPLATE = "ass_work_template"

    # strings
    AOV_ERROR = "Layer Name not defined"

    def _lock_parms(self, node, lock):
        super(ArnoldNodeHandler, self)._lock_parms(node, lock)
        parm_names = (self.AR_MATERIALX_FILE, self.AR_ASS_FILE)
        for parm_name in parm_names:
            parm = node.parm(parm_name)
            parm.lock(lock)

    #############################################################################################
    # Overriden methods
    #############################################################################################

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        properties_folder = parameter_group.get("main6_1")
        output_folder = properties_folder.get("folder0")
        index = output_folder.index_of_template(self.OUTPUT_PARM)
        output_folder.insert_template(index, sgtk_folder)

        ar_aovs = output_folder.get(self.AOV_COUNT)
        ar_aovs_template = ar_aovs.template
        ar_aovs_template.setScriptCallback(
            self.generate_callback_script_str("lock_aov_parms")
        )
        ar_aovs_template.setScriptCallbackLanguage(hou.scriptLanguage.Python)

        index = ar_aovs.index_of_template(self.AOV_NAME_TMPL.format("#"))
        sgtk_aov_name = hou.StringParmTemplate(
            self.SGTK_AOV_NAME_TMPL.format("#"),
            "Layer Name",
            1,
            script_callback=self.generate_callback_script_str("update_aov_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_aov_name.setConditional(
            hou.parmCondType.DisableWhen,
            (
                '{ ar_enable_aov# == 0 } '
                '{ ar_aov_label# == "" } '
                '{ ar_aov_exr_enable_layer_name# == 0 } '
                '{ ar_aov_separate# == 1 '
                    'ar_aov_picture_format# != beauty '
                    'ar_aov_picture_format# != exr '
                    'ar_aov_picture_format# != deepexr } '
                '{ ar_aov_separate# == 0 '
                    'ar_picture_format == tiff } '
                '{ ar_aov_separate# == 0 '
                    'ar_picture_format == jpg } '
                '{ ar_aov_separate# == 0 '
                    'ar_picture_format == png } '
                '{ ar_aov_separate# == 1 '
                    'ar_aov_picture_format# == beauty '
                    'ar_picture_format == tiff } '
                '{ ar_aov_separate# == 1 '
                    'ar_aov_picture_format# == beauty '
                    'ar_picture_format == jpg } '
                '{ ar_aov_separate# == 1 '
                    'ar_aov_picture_format# == beauty '
                    'ar_picture_format == png }'
            )
        )
        sgtk_aov_name.setConditional(
            hou.parmCondType.HideWhen, "{ use_sgtk != 1 }"
        )
        ar_aovs.insert_template(index, sgtk_aov_name)

        vm_channel_plane = ar_aovs.get(self.AOV_NAME_TMPL.format("#"))
        vm_channel_plane_template = vm_channel_plane.template
        vm_channel_plane_template.setConditional(
            hou.parmCondType.HideWhen, "{ use_sgtk == 1 }"
        )

        vm_filename_plane = ar_aovs.get(self.AOV_FILE_TMPL.format("#"))
        vm_filename_plane_template = vm_filename_plane.template
        vm_filename_plane_template.setDefaultValue((self.AOV_ERROR,))

    def _refresh_file_path(self, node, update_version=True):
        super(ArnoldNodeHandler, self)._refresh_file_path(
            node,
            update_version=update_version
        )
        parm_names = (self.AR_MATERIALX_FILE, self.AR_ASS_FILE)
        template_names = (self.MTLX_WORK_TEMPLATE, self.ASS_WORK_TEMPLATE)
        for parm_name, template_name in zip(parm_names, template_names):
            self.update_file_path(node, parm_name, template_name)

    #############################################################################################
    # Utilities
    #############################################################################################

    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        properties_folder = parameter_group.get("main6_1")
        output_folder = properties_folder.get("folder0")
        index = output_folder.index_of_template(self.SGTK_FOLDER)
        output_folder.pop_template(index)

        ar_aovs = output_folder.get(self.AOV_COUNT)
        ar_aovs_template = ar_aovs.template
        ar_aovs_template.setScriptCallback("")

        index = ar_aovs.index_of_template(self.SGTK_AOV_NAME_TMPL.format("#"))
        ar_aovs.pop_template(index)