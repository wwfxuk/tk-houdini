import glob
import itertools
import re

import sgtk

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class ExportNodeHandler(HookBaseClass):
    
    OUTPUT_PARM = None

    OUTPUT_PARM_EXPR = 'chs("./sgtk_output")'
    SGTK_OUTPUT = "sgtk_output"
    SGTK_ELEMENT = "sgtk_element"
    SGTK_LOCATION = "sgtk_location"
    SGTK_VARIATION = "sgtk_variation"
    SGTK_ALL_VERSIONS = "sgtk_all_versions"
    SGTK_VERSION = "sgtk_version"
    SGTK_REFRESH_VERSIONS = "sgtk_refresh_versions"
    SGTK_RESOLVED_VERSION = "sgtk_resolved_version"
    SGTK_FOLDER = "sgtk_folder"
    USE_SGTK = "use_sgtk"
    NEXT_VERSION_STR = "<NEXT>"

    #############################################################################################
    # houdini callback overrides
    #############################################################################################

    def on_created(self, node=None):
        if not node:
            return
        tk_houdini = self.parent.import_module("tk_houdini")
        utils = tk_houdini.utils
        parameter_group = utils.wrap_node_parameter_group(node)

        self.setup_parms(node)
        sgtk_folder = self.create_sgtk_folder()
        self._customise_parameter_group(parameter_group, sgtk_folder)

        node.setParmTemplateGroup(parameter_group.build())

    def on_name_changed(self, node=None):
        if not node:
            return
        if node.parm(self.SGTK_OUTPUT):
            self.refresh_file_path({"node": node})

    #############################################################################################
    # UI customisation
    #############################################################################################

    def setup_parms(self, node):
        output_parm = node.parm(self.OUTPUT_PARM)
        output_parm.setExpression(self.OUTPUT_PARM_EXPR)
        output_parm.disable(True)

    def create_sgtk_folder(self):
        sgtk_templates = []

        use_sgtk = hou.ToggleParmTemplate(
            self.USE_SGTK,
            "Use Shotgun",
            default_value=True,
            script_callback=self.generate_callback_script_str("enable_sgtk"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_templates.append(use_sgtk)

        sgtk_element = hou.StringParmTemplate(
            self.SGTK_ELEMENT,
            "Element",
            1,
            script_callback=self.generate_callback_script_str("refresh_file_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_element.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        sgtk_templates.append(sgtk_element)

        sgtk_location = hou.StringParmTemplate(
            self.SGTK_LOCATION,
            "Location",
            1,
            script_callback=self.generate_callback_script_str("refresh_file_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_location.setConditional(
            hou.parmCondType.DisableWhen,
            "{ use_sgtk != 1 } { sgtk_element == "" }"
        )
        sgtk_location.setJoinWithNext(True)
        sgtk_templates.append(sgtk_location)

        sgtk_variation = hou.StringParmTemplate(
            self.SGTK_VARIATION,
            "Variation",
            1,
            script_callback=self.generate_callback_script_str("refresh_file_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_variation.setConditional(
            hou.parmCondType.DisableWhen,
            "{ use_sgtk != 1 } { sgtk_element == "" }"
        )
        sgtk_variation.setJoinWithNext(True)
        sgtk_templates.append(sgtk_variation)

        sgtk_output = hou.StringParmTemplate(
            self.SGTK_OUTPUT,
            "Output Picture",
            1,
            is_hidden=True
        )
        sgtk_output.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        sgtk_templates.append(sgtk_output)

        all_versions = hou.StringParmTemplate(
            self.SGTK_ALL_VERSIONS,
            "All Versions",
            1,
            is_hidden=True
        )
        sgtk_templates.append(all_versions)

        version = hou.MenuParmTemplate(
            self.SGTK_VERSION,
            "Version",
            tuple(),
            item_generator_script=self.generate_callback_script_str("populate_versions"),
            item_generator_script_language=hou.scriptLanguage.Python,
            script_callback=self.generate_callback_script_str("refresh_file_path_from_version"),
            script_callback_language=hou.scriptLanguage.Python
        )
        version.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        version.setJoinWithNext(True)
        sgtk_templates.append(version)

        refresh_button = hou.ButtonParmTemplate(
            self.SGTK_REFRESH_VERSIONS,
            "Refresh Versions",
            script_callback=self.generate_callback_script_str("refresh_file_path_from_version"),
            script_callback_language=hou.scriptLanguage.Python
        )
        refresh_button.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        refresh_button.setJoinWithNext(True)
        sgtk_templates.append(refresh_button)

        resolved_version = hou.StringParmTemplate(
            self.SGTK_RESOLVED_VERSION,
            "Resolved Version",
            1,
            default_value=("1",)
        )
        resolved_version.setConditional(hou.parmCondType.DisableWhen, "{ sgtk_version != -1 }")
        sgtk_templates.append(resolved_version)

        sgtk_folder = hou.FolderParmTemplate(
            self.SGTK_FOLDER,
            "SGTK",
            parm_templates=sgtk_templates,
            folder_type=hou.folderType.Simple
        )
        return sgtk_folder

    #############################################################################################
    # UI Callbacks
    #############################################################################################

    def _get_all_versions(self, node):
        sgtk_all_versions = node.parm(self.SGTK_ALL_VERSIONS)
        all_versions_str = sgtk_all_versions.evalAsString()
        all_versions = filter(None, all_versions_str.split(","))
        all_versions = map(int, all_versions)
        return all_versions

    def _resolve_all_versions_from_fields(self, fields):
        versions = []
        if fields:
            if "version" in fields:
                del fields["version"]
            if "name" not in fields:
                return versions
            version_paths = self.parent.sgtk.abstract_paths_from_template(
                self.work_template,
                fields
            )
            for version_path in version_paths:
                if not glob.glob(re.sub(r"\$F\d", r"*", version_path)):
                    continue
                fields = self.work_template.get_fields(version_path)
                versions.append(int(fields["version"]))
            versions.sort()
        return versions

    def _resolve_version(self, all_versions, current):
        if current != self.NEXT_VERSION_STR:
            resolved = int(current)
            every_version = all_versions + [max(all_versions or [0]) + 1]
            if resolved not in every_version:
                resolved = max(every_version)
            return resolved
        return max(all_versions or [0]) + 1

    def enable_sgtk(self, kwargs):
        node = kwargs["node"]
        use_sgtk = kwargs["parm"]
        value = use_sgtk.eval()
        output_parm = node.parm(self.OUTPUT_PARM)
        if value:
            expression = self.OUTPUT_PARM_EXPR
            output_parm.setExpression(expression, replace_expression=True)
        else:
            output_parm.deleteAllKeyframes()
        output_parm.disable(value)

    def populate_versions(self, kwargs):
        node = kwargs["node"]
        all_versions = self._get_all_versions(node)
        versions = map(str, all_versions)
        versions.append(self.NEXT_VERSION_STR)
        return list(itertools.chain(*zip(versions, versions)))

    def refresh_file_path_from_version(self, kwargs):
        node = kwargs["node"]
        sgtk_version = node.parm(self.SGTK_VERSION)
        update_version = sgtk_version.evalAsString() == self.NEXT_VERSION_STR
        self.refresh_file_path(kwargs, update_version=update_version)

    def refresh_file_path(self, kwargs, update_version=True):
        node = kwargs["node"]
        sgtk_output = node.parm(self.SGTK_OUTPUT)

        context = self.parent.context
        fields = context.as_template_fields(self.work_template, validate=True)

        fields["node"] = node.name()
        fields["SEQ"] = "FORMAT: $F"

        sgtk_element = node.parm(self.SGTK_ELEMENT)
        sgtk_location = node.parm(self.SGTK_LOCATION)
        sgtk_variation = node.parm(self.SGTK_VARIATION)

        name = sgtk_element.evalAsString().strip()
        if name:
            fields["name"] = name
        else:
            # Lets clear these as we can't have just location and variation without element
            sgtk_location.set("")
            sgtk_variation.set("")

        location = sgtk_location.evalAsString().strip() or None
        fields["location"] = location

        variation = sgtk_variation.evalAsString().strip() or None
        fields["variation"] = variation
        
        all_versions = self._resolve_all_versions_from_fields(fields)
        sgtk_version = node.parm(self.SGTK_VERSION)
        if all_versions != self._get_all_versions(node):
            all_versions_str = ",".join(map(str, all_versions))
            sgtk_all_versions = node.parm(self.SGTK_ALL_VERSIONS)
            sgtk_all_versions.set(all_versions_str)
        
        if update_version:
            sgtk_version.set(len(all_versions))
        current = sgtk_version.evalAsString()
        resolved_version = self._resolve_version(all_versions, current)

        sgtk_resolved_version = node.parm(self.SGTK_RESOLVED_VERSION)
        sgtk_resolved_version.set(str(resolved_version))
        
        fields["version"] = resolved_version
        try:
            new_path = self.work_template.apply_fields(fields)
        except sgtk.TankError as error:
            new_path = str(error)

        sgtk_output.set(new_path)