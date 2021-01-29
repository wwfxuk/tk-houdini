"""Base Hook for other Houdini export/output node handlers.

These include:

- ``base_cache_handler``
    - ``alembic_handler``
    - ``geometry_handler``
- ``base_render_handler``
    - ``arnold_handler``
    - ``ifd_handler``

"""
import copy
import glob
import json
import os
import re

import sgtk
from sgtk.platform.qt import QtGui

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class FieldInputError(ValueError):
    """Error for when a parameter field is entered incorrectly.
    Example::
        >>> regex = r"^[a-zA-Z0-9]*$"
        >>> text = "--- nope ---"
        >>> if not re.match(regex, text):
        ...     raise FieldInputError(regex, text)
        ...
        Traceback (most recent call last):
          File "<string>", line 1, in <module>
        FieldInputError: Input does not match "^[a-zA-Z0-9]*$": "--- nope ---"
    """

    TEMPLATE = 'Input does not match "{}": "{}"'

    def __init__(self, regex, invalid_value):
        message = self.TEMPLATE.format(regex, invalid_value)
        super(FieldInputError, self).__init__(message)
        self.regex = regex
        self.invalid_value = invalid_value


class ExportNodeHandler(HookBaseClass):
    """
    Base class for all export handlers.

    Build the basic parameter templates for all export node types.
    """

    DEFAULT_ERROR_STRING = "'Element' not specified"
    NEXT_VERSION_STR = "<NEXT>"

    VERSION_POLICIES = [NEXT_VERSION_STR]

    OUTPUT_PARM = None

    SGTK_ELEMENT = "sgtk_element"
    SGTK_LOCATION = "sgtk_location"
    SGTK_VARIATION = "sgtk_variation"

    OPTIONAL_KEYS = "sgtk_optional_keys"
    USING_NEXT_VERSION = "sgtk_using_next_version"

    #############################################################################################
    # houdini callback overrides
    #############################################################################################

    def on_name_changed(self, node=None):
        """
        Method to run on houdini's OnNameChanged callback.

        :param node: A :class:`hou.Node` instance.
        """
        if not node:
            return
        parm = node.parm(self.USE_SGTK)
        if parm and parm.eval():
            self._refresh_file_path(node)

    #############################################################################################
    # UI customisation
    #############################################################################################

    def _add_optional_key_parm(self, node, parameter_group):
        """
        Add special parameter to node to store optional template keys and their values.

        :param node: A :class:`hou.Node` instance.
        :param parameter_group: The node's :class:`ParmGroup`.
        """
        optional_keys = hou.StringParmTemplate(
            self.OPTIONAL_KEYS,
            "optional keys",
            1,
            default_value=("{}",),
            is_hidden=True,
        )
        parameter_group.append_template(optional_keys)

    def _add_using_next_parm(self, node, parameter_group):
        """
        Add special parameter to node to store the last state of the version drop down.

        :param node: A :class:`hou.Node` instance.
        :param parameter_group: The node's :class:`ParmGroup`.
        """
        using_next = hou.ToggleParmTemplate(
            self.USING_NEXT_VERSION,
            "using next version",
            default_value=True,
            is_hidden=True,
        )
        parameter_group.append_template(using_next)

    def _set_up_node(self, node, parameter_group):
        """
        Set up a node for use with shotgun pipeline.

        :param node: A :class:`hou.Node` instance.
        :param parameter_group: A :class:`ParmGroup` instance.
        """
        self._add_optional_key_parm(node, parameter_group)
        self._add_using_next_parm(node, parameter_group)
        super(ExportNodeHandler, self)._set_up_node(node, parameter_group, hou=hou)

    def _set_up_parms(self, node):
        """
        Set up the given node's parameters.

        :param node: A :class:`hou.Node` instance.
        """
        output_parm = node.parm(self.OUTPUT_PARM)
        output_parm.set(self.DEFAULT_ERROR_STRING)
        output_parm.lock(True)

    def _create_sgtk_parms(self, node):
        """
        Create the parameters that are going to live within the sgtk folder.

        :param node: A :class:`hou.Node` instance.

        :rtype: list(:class:`hou.ParmTemplate`)
        """
        templates = super(ExportNodeHandler, self)._create_sgtk_parms(node)
        sgtk_element = hou.StringParmTemplate(
            self.SGTK_ELEMENT,
            "Element",
            1,
            script_callback=self.generate_callback_script_str(
                "validate_parm_and_refresh_path"
            ),
            script_callback_language=hou.scriptLanguage.Python,
        )
        sgtk_element.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        sgtk_element.setJoinWithNext(True)
        templates.append(sgtk_element)

        sgtk_location = hou.StringParmTemplate(
            self.SGTK_LOCATION,
            "Location",
            1,
            script_callback=self.generate_callback_script_str(
                "validate_parm_and_refresh_path"
            ),
            script_callback_language=hou.scriptLanguage.Python,
        )
        sgtk_location.setConditional(
            hou.parmCondType.DisableWhen, '{ use_sgtk != 1 } { sgtk_element == "" }'
        )
        templates.append(sgtk_location)

        sgtk_variation = hou.StringParmTemplate(
            self.SGTK_VARIATION,
            "Variation",
            1,
            script_callback=self.generate_callback_script_str(
                "validate_parm_and_refresh_path"
            ),
            script_callback_language=hou.scriptLanguage.Python,
        )
        sgtk_variation.setConditional(
            hou.parmCondType.DisableWhen, '{ use_sgtk != 1 } { sgtk_element == "" }'
        )
        templates.append(sgtk_variation)

        return templates

    def _create_sgtk_folder(self, node):
        """
        Create the sgtk folder template.

        This contains the common parameters used by all node handlers.

        :param node: A :class:`hou.Node` instance.
        """
        return super(ExportNodeHandler, self)._create_sgtk_folder(node, hou=hou)

    #############################################################################################
    # UI Callbacks
    #############################################################################################

    def _get_sequence_glob_path(self, path, template, fields):
        """
        From the given path, shotgun template and fields, derive a glob search path.

        :param str path: The path.
        :param template: The relating :class:`sgtk.Template`.
        :param dict fields: The template fields.

        :returns: The glob path.
        """
        glob_path = path
        frame_key = template.keys.get("SEQ")
        if frame_key:
            frame_format_string = frame_key._extract_format_string(fields["SEQ"])
            frame_spec = frame_key._resolve_frame_spec(
                frame_format_string, frame_key.format_spec
            )
            glob_path = re.sub(re.escape(frame_spec), r"*", glob_path)
        return glob_path

    def _resolve_version(self, all_versions, current):
        """
        From a given string, resolve the current version.
        Either a specified version or the next version in the sequence.

        :param list(int) all_versions: All the existing versions.
        :param str current: The currently selected version option.

        :rtype: int
        """
        if current != self.NEXT_VERSION_STR:
            resolved = int(current)
            every_version = all_versions + [max(all_versions or [0]) + 1]
            if resolved not in every_version:
                resolved = max(every_version)
            return resolved
        return max(all_versions or [0]) + 1

    def _enable_sgtk(self, node, sgtk_enabled):
        """
        Enable/disable the sgtk parameters.

        :param node: A :class:`hou.Node` instance.
        :param bool sgtk_enabled: The state to set the parameters to.
        """
        super(ExportNodeHandler, self)._enable_sgtk(node, sgtk_enabled)
        output_parm = node.parm(self.OUTPUT_PARM)
        output_parm.lock(sgtk_enabled)

    def _update_template_fields(self, node, fields):
        """
        Update template fields from the node's parameter values.

        :param node: A :class:`hou.Node` instance.
        :param dict fields: Template fields.
        """
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
        """
        Update the optional keys parameter to include the currently 'in use'
        fields and their values.

        :param node: A :class:`hou.Node` instance.
        :param template: An :class:`sgtk.Template`.
        :param dict fields: The template fields.
        """
        optional_fields = {}
        for key_name in self.get_optional_keys(template):
            field = fields.get(key_name)
            if field:
                optional_fields[key_name] = field
        parm = node.parm(self.OPTIONAL_KEYS)
        if parm:
            parm.set(json.dumps(optional_fields))

    def _update_all_versions(self, node, all_versions):
        """
        Update all the versions that exist on disk.

        :param node: A :class:`hou.Node` instance.
        :param list(int) all_versions: Updated list of all versions.
        """
        if all_versions != self._get_all_versions(node):
            all_versions_str = ",".join(map(str, all_versions))
            sgtk_all_versions = node.parm(self.SGTK_ALL_VERSIONS)
            sgtk_all_versions.set(all_versions_str)

    def refresh_file_path_from_version(self, kwargs):
        """
        Callback to refresh the file paths generated by the node handler when the
        version is updated.
        """
        node = kwargs["node"]
        using_next_parm = node.parm(self.USING_NEXT_VERSION)
        sgtk_version = node.parm(self.SGTK_VERSION)
        using_next = sgtk_version.evalAsString() in self.VERSION_POLICIES
        using_next_parm.set(using_next)
        self._refresh_file_path(node)

    def on_loaded(self, node=None):
        """Ensure data is loaded back into the version menus and resolved."""
        super(ExportNodeHandler, self).on_loaded(node=node)
        if isinstance(node, hou.Node):
            self._refresh_file_path(node)

            # These don't get saved with the scene, need to re-bind
            # on every new scene load
            node.addEventCallback(
                [hou.nodeEventType.AppearanceChanged], self.on_node_event
            )

    def on_node_event(self, event_type, **kwargs):
        self.logger.debug("node_event[%s]: %s", event_type, kwargs)
        if event_type == hou.nodeEventType.AppearanceChanged:
            node = kwargs["node"]
            change_type = kwargs["change_type"]
            if change_type == hou.appearanceChangeType.Pick and node.isPicked():
                self._refresh_file_path(node)
                self.logger.debug("Refreshed versions: %s", node.path())

    def _refresh_file_path(self, node):
        """
        Refresh the file paths generated by the node handler.

        :param node: A :class:`hou.Node` instance.
        """
        output_parm = node.parm(self.OUTPUT_PARM)

        context = self.parent.context
        template = self.get_work_template(node)
        fields = context.as_template_fields(template, validate=True)

        self._update_template_fields(node, fields)
        self._update_optional_keys(node, template, fields)

        all_versions = self._resolve_all_versions_from_fields(fields, template)
        sgtk_version = node.parm(self.SGTK_VERSION)

        value_before_update = sgtk_version.evalAsString()
        self._update_all_versions(node, all_versions)
        current = sgtk_version.evalAsString()
        if value_before_update in sgtk_version.menuItems():
            current = value_before_update
        sgtk_version.set(current)  # Force update UI: Ensure index is re-corrected

        using_next = current in self.VERSION_POLICIES
        using_next_parm = node.parm(self.USING_NEXT_VERSION)
        if using_next_parm:
            using_next_parm.set(using_next)
            if using_next_parm.eval():
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
            self.parent.logger.exception('Failed to calculate path for "%s"', node)

        output_parm.lock(False)
        output_parm.set(new_path)
        output_parm.lock(True)

    def _validate_input(self, input_value):
        """
        Validate the user input. Must be alphanumeric.

        :param str input_value: The input value.

        :raises: :class:`FieldInputError` when the validation fails.
        """
        match = re.match(r"^[a-zA-Z0-9]*$", input_value)
        if not match:
            raise FieldInputError("only letters and numbers", input_value)

    def _validate_parm(self, parm):
        """
        Run the validation on the given parameter.
        Resets the parm to empty if fails and shows a message box
        to inform the user.

        :param parm: A :class:`hou.Parm` instance.

        :returns: :class:`bool`. The status of the validation. True
            is a pass.
        """
        value = parm.evalAsString().strip()
        try:
            self._validate_input(value)
            return True
        except FieldInputError as error:
            parm.set("")
            QtGui.QMessageBox.warning(
                self.parent._get_dialog_parent(), "Input Error", str(error)
            )
            return False

    def validate_parm_and_refresh_path(self, kwargs):
        """
        Callback to validate the parm and refresh the file path
        accordingly.
        """
        if self._validate_parm(kwargs["parm"]):
            self._refresh_file_path(kwargs["node"])

    #############################################################################################
    # Utilities
    #############################################################################################

    @staticmethod
    def get_optional_keys(template):
        """
        Get the optional keys from the given template.

        :param template: An :class:`sgtk.Template` instance.

        :rtype: list(:class:`sgtk.TemplateKey`)
        """
        return list(filter(template.is_optional, template.keys.keys()))

    def _get_template_for_file_path(self, node, file_path):
        """
        Get the template for the given file path.
        For the most part, this will liekly be the work_template.

        :param node: A :class:`hou.Node` instance.
        :param str file_path: The file path the check against.

        :rtype: :class:`sgtk.Template`
        """
        return self.get_work_template(node)

    def _populate_from_fields(self, node, fields):
        """
        Populate the node from template fields.

        :param node: A :class:`hou.Node` instance.
        :param dict fields: The template fields.
        """
        sgtk_element = node.parm(self.SGTK_ELEMENT)
        sgtk_element.set(fields.get("name", ""))

        sgtk_location = node.parm(self.SGTK_LOCATION)
        sgtk_location.set(fields.get("location", ""))

        sgtk_variation = node.parm(self.SGTK_VARIATION)
        sgtk_variation.set(fields.get("variation", ""))

    def _set_version(self, node, current_version):
        """
        Set the index of the versions drop down from the given version.

        :param node: A :class:`hou.Node` instance.
        :param int current_version: The version to set.
        """
        version_str = str(current_version)
        sgtk_version = node.parm(self.SGTK_VERSION)
        using_next = node.parm(self.USING_NEXT_VERSION)
        entries = sgtk_version.menuItems()
        if using_next and using_next.eval():
            if self.NEXT_VERSION_STR in entries:
                index = entries.index(self.NEXT_VERSION_STR)
            else:
                index = len(entries)
        elif version_str in entries:
            index = entries.index(version_str)
        else:
            index = len(entries)
        sgtk_version.set(index)

    def _get_optional_fields(self, node, template):
        """
        Get the optional fields from the sgtk_optional_keys parm.

        :param node: A :class:`hou.Node` instance.
        :param template: An :class:`sgtk.Template` instance.

        :rtype: dict
        """
        parm = node.parm(self.OPTIONAL_KEYS)
        if parm:
            return json.loads(parm.evalAsString())
        return {}

    def _populate_from_file_path(self, node, file_path):
        """
        Populate a node's sgtk parms from a file path.
        If the file path doesn't match the template, disable the
        use of shotgun on this node.

        :param node: A :class:`hou.Node` instance.
        :param str file_path: The file path to populate from.
        """
        template = self._get_template_for_file_path(node, file_path)
        skip_keys = self.get_optional_keys(template)
        fields = template.validate_and_get_fields(file_path, skip_keys=skip_keys)
        if fields:
            fields.update(self._get_optional_fields(node, template))
            if "SEQ" in fields:
                fields["SEQ"] = "FORMAT: $F"
            current_version = fields.get("version", self.NEXT_VERSION_STR)
            all_versions = self._resolve_all_versions_from_fields(fields, template)
            self._populate_from_fields(node, fields)
            self._update_all_versions(node, all_versions)
            self._set_version(node, current_version)
            self._refresh_file_path(node)
        else:
            use_sgtk = node.parm(self.USE_SGTK)
            use_sgtk.set(False)
            self._enable_sgtk(node, False)
            output_parm = node.parm(self.OUTPUT_PARM)
            output_parm.set(file_path)

    def _restore_sgtk_parms(self, node):
        """
        Restore any removed sgtk parameters onto the given node.

        :param node: A :class:`hou.Node` instance containing sgtk parameters.
        """
        output_parm = node.parm(self.OUTPUT_PARM)
        original_file_path = output_parm.unexpandedString() if output_parm else None
        self.add_sgtk_parms(node)
        if original_file_path is not None:
            self._populate_from_file_path(node, original_file_path)

    def _get_sequence_paths(self, path, template, fields):
        """
        Get all the paths relating to a sequence.

        :param str path: The sequence path.
        :param template: An :class:`sgtk.Template`.
        :param dict fields: The template fields.

        :returns: A list of file paths
        """
        fields = copy.deepcopy(fields)
        sequence_paths = []
        if "SEQ" in fields:
            fields["SEQ"] = "FORMAT: $F"
            path = template.apply_fields(fields)
            glob_path = self._get_sequence_glob_path(path, template, fields)
            sequence_paths = glob.glob(glob_path)
        return sequence_paths

    def _make_sgtk_compliant_path(self, path, template):
        """
        Take the path and make the sequence field shotgun compliant (%04d).

        :param str path: The sequence path.
        :param template: An :class:`sgtk.Template`.

        :rtype: str
        """
        fields = template.get_fields(path)
        if "SEQ" in fields:
            fields["SEQ"] = "FORMAT: %d"
        return template.apply_fields(fields)

    def _get_output_path_and_templates_for_parm(
        self,
        node,
        parm_name,
        work_template,
        publish_template,
        paths_and_templates,
        is_deep=False,
    ):
        """
        Get the output path and the templates used for the given parm.

        :param node: A :class:`hou.Node` instance.
        :param str parm_name: The name of the parameter to query.
        :param work_template: The work :class:`sgtk.Template` for this parm.
        :param publish_template: The publish :class:`sgtk.Template` for this parm.
        :param list paths_and_templates: The current list of paths and templates
            to append to.
        :param bool is_deep: Is the parm a deep output or not.
        """
        parm = node.parm(parm_name)
        path = parm.evalAsString()

        item = {"work_template": work_template, "publish_template": publish_template}
        fields = work_template.get_fields(path)

        sequence_paths = self._get_sequence_paths(path, work_template, fields)
        if sequence_paths:
            item["sequence_paths"] = sequence_paths
        elif not os.path.exists(path):
            # if nothing exists on disk
            # lets get the last rendered one because it might be "<Next>"
            # and it's evaluated to the next available version
            all_versions = self._get_all_versions(node)
            if not all_versions:
                # no versions so nothing's been rendered
                return
            fields["version"] = max(all_versions)
            path = work_template.apply_fields(fields)
            sequence_paths = self._get_sequence_paths(path, work_template, fields)
            if sequence_paths:
                item["sequence_paths"] = sequence_paths

        item["path"] = self._make_sgtk_compliant_path(path, work_template)

        if is_deep:
            item["is_deep"] = True
        paths_and_templates.append(item)

    def _get_output_paths_and_templates(self, node):
        """
        Go through the node's specified parameters and get the output paths,
        work and publish templates.

        Returns a list of dictionaries, each containing, at least:
        - work template
        - publish template
        - file name

        and optionally:
        - any sequence paths
        - whether the output is a deep image

        :param node: A :class:`hou.Node` instance.

        :rtype: list(dict)
        """
        paths_and_templates = []

        work_template = self.get_work_template(node)
        publish_template = self.get_publish_template(node)
        self._get_output_path_and_templates_for_parm(
            node, self.OUTPUT_PARM, work_template, publish_template, paths_and_templates
        )

        return paths_and_templates

    def get_output_paths_and_templates(self, node):
        """
        Go through the node's specified parameters and get the output paths,
        work and publish templates.


        :param node: A :class:`hou.Node` instance.

        :rtype: list(dict)
        """
        parm = node.parm(self.USE_SGTK)
        results = []
        if parm and parm.eval():
            results = self._get_output_paths_and_templates(node)
        return results
