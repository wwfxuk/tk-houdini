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
    NEXT_VERSION_STR = "<NEXT>"

    VERSION_POLICIES = [NEXT_VERSION_STR]

    OUTPUT_PARM = None

    SGTK_ELEMENT = "sgtk_element"
    SGTK_LOCATION = "sgtk_location"
    SGTK_VARIATION = "sgtk_variation"

    OPTIONAL_KEY_PARM_TMPL = "sgtk_optional_key_{}"
    PRESENT_OPTIONAL_KEYS = "sgtk_present_optional_keys"

    #############################################################################################
    # houdini callback overrides
    #############################################################################################

    def on_name_changed(self, node=None):
        if not node:
            return
        parm = node.parm(self.USE_SGTK)
        if parm and parm.eval():
            self._refresh_file_path(node)

    #############################################################################################
    # UI customisation
    #############################################################################################

    def _add_optional_key_parms(self, node, parameter_group):
        if self.PRESENT_OPTIONAL_KEYS in parameter_group:
            return
        template = self.get_work_template(node)

        templates = []
        for key_name in self.get_optional_keys(template):
            parm_name = self.OPTIONAL_KEY_PARM_TMPL.format(key_name)
            parm_template = hou.ToggleParmTemplate(
                parm_name,
                key_name,
                default_value=True,
                is_hidden=True
            )
            templates.append(parm_template)

        folder = hou.FolderParmTemplate(
            self.PRESENT_OPTIONAL_KEYS,
            "present optional keys",
            parm_templates=templates,
            folder_type=hou.folderType.Simple,
            is_hidden=True
        )
        parameter_group.append_template(folder)

    def _set_up_node(self, node, parameter_group):
        self._add_optional_key_parms(node, parameter_group)
        super(ExportNodeHandler, self)._set_up_node(node, parameter_group, hou=hou)

    def _set_up_parms(self, node):
        output_parm = node.parm(self.OUTPUT_PARM)
        output_parm.set(self.DEFAULT_ERROR_STRING)
        output_parm.lock(True)

    def _create_sgtk_parms(self, node):
        templates = super(ExportNodeHandler, self)._create_sgtk_parms(node, hou=hou)
        sgtk_element = hou.StringParmTemplate(
            self.SGTK_ELEMENT,
            "Element",
            1,
            script_callback=self.generate_callback_script_str("validate_parm_and_refresh_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_element.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        sgtk_element.setJoinWithNext(True)
        templates.append(sgtk_element)

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
        templates.append(sgtk_location)

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
        templates.append(sgtk_variation)

        return templates

    def _create_sgtk_folder(self, node):
        return super(ExportNodeHandler, self)._create_sgtk_folder(node, hou=hou)

    #############################################################################################
    # UI Callbacks
    #############################################################################################

    def _resolve_all_versions_from_fields(self, node, fields):
        versions = set()
        if fields:
            if "version" not in fields:
                fields["version"] = 1
            if "name" not in fields:
                return versions

            def repl_version(match):
                return "{}*{}".format(match.group(1), match.group(3))

            work_template = self.get_work_template(node)
            path = work_template.apply_fields(fields)
            glob_path = path

            version_key = work_template.keys.get("version")
            if version_key:
                format_spec = version_key.format_spec or ""
                match = version_key._FORMAT_SPEC_RE.match(format_spec)
                if match:
                    pad_char = match.groups()[0]
                    min_width = int(match.groups()[-1])
                else:
                    pad_char = "0"
                    min_width = 1
                max_pad_width = min_width - 1
                padded_version_regex = r"{pad}{{0,{max}}}\d{{1,}}".format(pad=pad_char, max=max_pad_width)
                regex = r"([/_\.][vV])({})([/_\.])".format(padded_version_regex)
                glob_path = re.sub(regex, repl_version, glob_path)
            
            frame_key = work_template.keys.get("SEQ")
            if frame_key:
                frame_format_string = frame_key._extract_format_string(fields["SEQ"])
                frame_spec = frame_key._resolve_frame_spec(frame_format_string, frame_key.format_spec)
                glob_path = re.sub(re.escape(frame_spec), r"*", glob_path)

            version_paths = glob.iglob(glob_path)
            for key, paths in itertools.groupby(version_paths, key=os.path.dirname):
                version_path = paths.next()
                fields = work_template.get_fields(version_path)
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

    def _enable_sgtk(self, node, sgtk_enabled):
        output_parm = node.parm(self.OUTPUT_PARM)
        output_parm.lock(sgtk_enabled)

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

    def _update_optional_keys(self, node, template, fields):
        for key_name in self.get_optional_keys(template):
            parm = node.parm(self.OPTIONAL_KEY_PARM_TMPL.format(key_name))
            parm.set(bool(fields.get(key_name)))

    def _update_all_versions(self, node, all_versions):
        if all_versions != self._get_all_versions(node):
            all_versions_str = ",".join(map(str, all_versions))
            sgtk_all_versions = node.parm(self.SGTK_ALL_VERSIONS)
            sgtk_all_versions.set(all_versions_str)
            
    def _refresh_file_path(self, node, update_version=True):
        output_parm = node.parm(self.OUTPUT_PARM)

        context = self.parent.context
        template = self.get_work_template(node)
        fields = context.as_template_fields(template, validate=True)

        self._update_template_fields(node, fields)
        self._update_optional_keys(node, template, fields)
        
        all_versions = self._resolve_all_versions_from_fields(node, fields)
        sgtk_version = node.parm(self.SGTK_VERSION)
        self._update_all_versions(node, all_versions)
        
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

        output_parm.lock(False)
        output_parm.set(new_path)
        output_parm.lock(True)

    def _validate_input(self, input_value):
        match = re.match(r"^[a-zA-Z0-9]*$", input_value)
        if not match:
            raise FieldInputError("Input must be alphanumeric.")

    def _validate_parm(self, parm):
        value = parm.evalAsString().strip()
        try:
            self._validate_input(value)
        except FieldInputError:
            parm.set("")
            raise

    def validate_parm_and_refresh_path(self, kwargs):
        try:
            self._validate_parm(kwargs["parm"])
        finally:
            self._refresh_file_path(kwargs["node"])

    #############################################################################################
    # Utilities
    #############################################################################################

    @staticmethod
    def get_optional_keys(template):
        return filter(
            template.is_optional,
            template.keys.keys()
        )

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
        version_str = str(current_version)
        sgtk_version = node.parm(self.SGTK_VERSION)
        entries = sgtk_version.menuItems()
        if version_str not in entries:
            index = len(entries)
        else:
            index = entries.index(version_str)
        sgtk_version.set(index)

    def _get_skip_keys(self, node, template):
        skip_keys = []
        for key_name in self.get_optional_keys(template):
            parm = node.parm(self.OPTIONAL_KEY_PARM_TMPL.format(key_name))
            if not parm:
                continue
            if not parm.eval():
                skip_keys.append(key_name)
        return skip_keys

    def _populate_from_file_path(self, node, file_path):
        template = self._get_template_for_file_path(node, file_path)
        skip_keys = self._get_skip_keys(node, template)
        fields = template.validate_and_get_fields(file_path, skip_keys=skip_keys)
        if not fields:
            use_sgtk = node.parm(self.USE_SGTK)
            use_sgtk.set(False)
            self._enable_sgtk(node, False)
            output_parm = node.parm(self.OUTPUT_PARM)
            output_parm.set(file_path)
        else:
            fields["SEQ"] = "FORMAT: $F"
            current_version = fields.get("version", self.NEXT_VERSION_STR)
            all_versions = self._resolve_all_versions_from_fields(node, fields)
            self._populate_from_fields(node, fields)
            self._update_all_versions(node, all_versions)
            self._set_version(node, current_version)
            self._refresh_file_path(node, update_version=False)

    def _restore_sgtk_parms(self, node):
        output_parm = node.parm(self.OUTPUT_PARM)
        original_file_path = output_parm.evalAsString()
        self.add_sgtk_parms(node)
        self._populate_from_file_path(node, original_file_path)