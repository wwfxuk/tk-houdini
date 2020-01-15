from functools import partial
import glob
import itertools
import os
import re

import sgtk

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class FieldInputError(Exception):
    pass


class ExportNodeHandler(HookBaseClass):
    
    DEFAULT_ERROR_STRING = "'Element' not specified"

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
        self._add_sgtk_parms(node)

    def on_name_changed(self, node=None):
        if not node:
            return
        if node.parm(self.SGTK_OUTPUT):
            self.refresh_file_path({"node": node})

    #############################################################################################
    # UI customisation
    #############################################################################################

    def _add_sgtk_parms(self, node):
        if not node:
            return
        tk_houdini = self.parent.import_module("tk_houdini")
        utils = tk_houdini.utils
        parameter_group = utils.wrap_node_parameter_group(node)

        self.setup_parms(node)
        sgtk_folder = self.create_sgtk_folder(node)
        self._customise_parameter_group(node, parameter_group, sgtk_folder)

        node.setParmTemplateGroup(parameter_group.build())

    def setup_parms(self, node):
        output_parm = node.parm(self.OUTPUT_PARM)
        output_parm.setExpression(self.OUTPUT_PARM_EXPR)
        output_parm.disable(True)

    def _add_identifier_parm_template(self, node, templates):
        pass

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        pass

    def create_sgtk_folder(self, node):
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
            script_callback=self.generate_callback_script_str("validate_parm_and_refresh_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_element.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        sgtk_element.setJoinWithNext(True)
        sgtk_templates.append(sgtk_element)

        sgtk_location = hou.StringParmTemplate(
            self.SGTK_LOCATION,
            "Location",
            1,
            script_callback=self.generate_callback_script_str("validate_parm_and_refresh_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_location.setConditional(
            hou.parmCondType.DisableWhen,
            '{ use_sgtk != 1 } { sgtk_element == "" }'
        )
        sgtk_templates.append(sgtk_location)

        sgtk_variation = hou.StringParmTemplate(
            self.SGTK_VARIATION,
            "Variation",
            1,
            script_callback=self.generate_callback_script_str("validate_parm_and_refresh_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_variation.setConditional(
            hou.parmCondType.DisableWhen,
            '{ use_sgtk != 1 } { sgtk_element == "" }'
        )
        sgtk_variation.setJoinWithNext(True)
        sgtk_templates.append(sgtk_variation)

        self._add_identifier_parm_template(node, sgtk_templates)

        sgtk_output = hou.StringParmTemplate(
            self.SGTK_OUTPUT,
            "Output Picture",
            1,
            default_value=(self.DEFAULT_ERROR_STRING,),
            is_hidden=True
        )
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
        refresh_button.setConditional(
            hou.parmCondType.DisableWhen,
            '{ use_sgtk != 1 } { sgtk_element == "" }'
        )
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

    def _resolve_all_versions_from_fields(self, node, fields):
        versions = set()
        if fields:
            if "version" not in fields:
                fields["version"] = 1
            if "name" not in fields:
                return versions

            def repl(match):
                return "{}*{}".format(match.group(1), match.group(3))

            path = self.get_work_template(node).apply_fields(fields)
            glob_path = re.sub(r"([/_]v)(\d{3})([/\.])", repl, path)
            glob_path = re.sub(r"\$F\d", r"*", glob_path)
            version_paths = glob.iglob(glob_path)
            for key, paths in itertools.groupby(version_paths, key=os.path.dirname):
                version_path = paths.next()
                fields = self.get_work_template(node).get_fields(version_path)
                versions.add(int(fields["version"]))
            versions = list(versions)
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

    def _replace_frame_numbers(self, path):
        def repl(match):
            return ".$F{}.".format(len(match.group(1)))

        return re.sub(r"\.(\d+)\.", repl, path)

    def _remove_expression_for_path(self, parm):
        parm.deleteAllKeyframes()
        path = parm.evalAsString()
        parm.set(self._replace_frame_numbers(path))

    def _enable_sgtk(self, node, sgtk_enabled):
        output_parm = node.parm(self.OUTPUT_PARM)
        if sgtk_enabled:
            expression = self.OUTPUT_PARM_EXPR
            output_parm.setExpression(expression, replace_expression=True)
        else:
            self._remove_expression_for_path(output_parm)
        output_parm.disable(sgtk_enabled)

    def enable_sgtk(self, kwargs):
        node = kwargs["node"]
        use_sgtk = node.parm(self.USE_SGTK)
        value = use_sgtk.eval()
        self._enable_sgtk(node, value)

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

    def _update_template_fields(self, node, fields):
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

    def refresh_file_path(self, kwargs, update_version=True):
        node = kwargs["node"]
        sgtk_output = node.parm(self.SGTK_OUTPUT)

        context = self.parent.context
        fields = context.as_template_fields(self.get_work_template(node), validate=True)

        self._update_template_fields(node, fields)
        
        all_versions = self._resolve_all_versions_from_fields(node, fields)
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
            new_path = self.get_work_template(node).apply_fields(fields)
        except sgtk.TankError:
            new_path = self.DEFAULT_ERROR_STRING

        sgtk_output.set(new_path)

    def _validate_input(self, input_value):
        match = re.match(r"^[a-zA-Z0-9]*$", input_value)
        if not match:
            raise FieldInputError("Input must be alphanumeric.")

    def validate_parm_and_refresh_path(self, kwargs):
        parm = kwargs["parm"]
        value = parm.evalAsString().strip()
        self._validate_input(value)
        self.refresh_file_path(kwargs)

    #############################################################################################
    # Utilities
    #############################################################################################

    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        pass

    def remove_sgtk_parms(self, node):
        use_sgtk = node.parm(self.USE_SGTK)
        use_sgtk.set(False)
        self._enable_sgtk(node, False)
        tk_houdini = self.parent.import_module("tk_houdini")
        utils = tk_houdini.utils
        parameter_group = utils.wrap_node_parameter_group(node)
        self._remove_sgtk_items_from_parm_group(parameter_group)
        node.setParmTemplateGroup(parameter_group.build())

    def _get_template_for_file_path(self, node, file_path):
        return self.get_work_template(node)
    
    def _populate_from_fields(self, node, fields):
        sgtk_element = node.parm(self.SGTK_ELEMENT)
        sgtk_element.set(fields.get("name", ""))

        sgtk_location = node.parm(self.SGTK_LOCATION)
        sgtk_location.set(fields.get("location", ""))

        sgtk_variation = node.parm(self.SGTK_VARIATION)
        sgtk_variation.set(fields.get("variation", ""))

    def _set_version(self, node, current_version):
        sgtk_version = node.parm(self.SGTK_VERSION)
        entries = sgtk_version.menuItems()
        if current_version not in entries:
            index = len(entries)
        else:
            index = entries.index(current_version)
        sgtk_version.set(index)

    def _populate_from_file_path(self, node, file_path, use_next_version):
        template = self._get_template_for_file_path(node, file_path)
        fields = template.validate_and_get_fields(file_path)
        if not fields:
            use_sgtk = node.parm(self.USE_SGTK)
            use_sgtk.set(False)
            self._enable_sgtk(node, False)
            output_parm = node.parm(self.OUTPUT_PARM)
            output_parm.set(file_path)
        else:
            current_version = str(fields.get("version", self.NEXT_VERSION_STR))
            self._populate_from_fields(node, fields)
            self.refresh_file_path({"node": node})
            if not use_next_version:
                self._set_version(node, current_version)
                self.refresh_file_path({"node": node}, update_version=False)

    def populate_sgtk_parms(self, node, use_next_version=True):
        output_parm = node.parm(self.OUTPUT_PARM)
        original_file_path = output_parm.evalAsString()
        self._add_sgtk_parms(node)
        self._populate_from_file_path(node, original_file_path, use_next_version)