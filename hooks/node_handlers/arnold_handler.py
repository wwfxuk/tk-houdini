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
    AOV_USE_FILE_TMPL = "ar_aov_separate{}"

    # mtlx
    AR_MATERIALX_FILE = "ar_materialx_file"
    AR_MATERIALX_ENABLE = "ar_materialx_enable"

    # ass
    ARCHIVE_ENABLED = "ar_ass_export_enable"
    ARCHIVE_OUTPUT = "ar_ass_file"

    # shotgun
    SGTK_AOV_NAME_TMPL = "sgtk_aov_exr_layer_name{}"

    # templates
    MTLX_WORK_TEMPLATE = "mtlx_work_template"
    MTLX_PUBLISH_TEMPLATE = "mtlx_publish_template"
    ARCHIVE_WORK_TEMPLATE = "ass_work_template"
    ARCHIVE_PUBLISH_TEMPLATE = "ass_publish_template"

    # strings
    AOV_ERROR = "Layer Name not defined"

    def _lock_parms(self, node, lock):
        super(ArnoldNodeHandler, self)._lock_parms(node, lock)
        ar_materialx_file = node.parm(self.AR_MATERIALX_FILE)
        ar_materialx_file.lock(lock)

    #############################################################################################
    # Overriden methods
    #############################################################################################

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        index = parameter_group.index_of_template("main6")
        parameter_group.insert_template(index, sgtk_folder)

        properties_folder = parameter_group.get("main6_1")
        output_folder = properties_folder.get("folder0")
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
        self.update_file_path(node, self.AR_MATERIALX_FILE, self.MTLX_WORK_TEMPLATE)

    #############################################################################################
    # Utilities
    #############################################################################################

    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        index = parameter_group.index_of_template(self.SGTK_FOLDER)
        parameter_group.pop_template(index)

        properties_folder = parameter_group.get("main6_1")
        output_folder = properties_folder.get("folder0")

        ar_aovs = output_folder.get(self.AOV_COUNT)
        ar_aovs_template = ar_aovs.template
        ar_aovs_template.setScriptCallback("")
        ar_aovs_template.setScriptCallbackLanguage(hou.scriptLanguage.Hscript)

        index = ar_aovs.index_of_template(self.SGTK_AOV_NAME_TMPL.format("#"))
        ar_aovs.pop_template(index)
    
    def _get_output_paths_and_templates(self, node):
        paths_and_templates = super(ArnoldNodeHandler, self)._get_output_paths_and_templates(node)

        # material x
        if node.parm(self.AR_MATERIALX_ENABLE).eval():
            self._get_output_path_and_templates_for_parm(
                node,
                self.AR_MATERIALX_FILE,
                self._get_template(self.MTLX_WORK_TEMPLATE),
                self._get_template(self.MTLX_PUBLISH_TEMPLATE),
                paths_and_templates
            )

        # ass files
        if node.parm(self.ARCHIVE_ENABLED).eval():
            self._get_output_path_and_templates_for_parm(
                node,
                self.ARCHIVE_OUTPUT,
                self._get_template(self.ARCHIVE_WORK_TEMPLATE),
                self._get_template(self.ARCHIVE_PUBLISH_TEMPLATE),
                paths_and_templates
            )

        return paths_and_templates