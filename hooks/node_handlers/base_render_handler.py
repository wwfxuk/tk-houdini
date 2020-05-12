"""Base Hook for other Houdini renderer node handlers.

These include:

- ``arnold_handler``
- ``ifd_handler``

This hook is designed to inherit from ``base_export_handler`` hook.
"""
import sgtk

import hou


HookBaseClass = sgtk.get_hook_baseclass()


class BaseRenderNodeHandler(HookBaseClass):
    """
    Base class for all render output nodes.
    """

    SGTK_PASS_NAME = "sgtk_pass_name"

    # aovs
    AOV_COUNT = ""
    AOV_NAME_TMPL = "{}"
    AOV_FILE_TMPL = "{}"
    AOV_USE_FILE_TMPL = "{}"

    # archives
    ARCHIVE_ENABLED = ""
    ARCHIVE_OUTPUT = ""

    # templates
    AOV_WORK_TEMPLATE = "aov_work_template"
    AOV_PUBLISH_TEMPLATE = "aov_publish_template"
    ARCHIVE_WORK_TEMPLATE = ""
    ARCHIVE_PUBLISH_TEMPLATE = ""

    # strings
    AOV_ERROR = ""

    def _get_template_fields_from(self, node, additional_fields=None):
        """
        Get shotgun template fields from the given node and update with any additional
        fields.

        :param node: A :class:`hou.Node` instance.
        :param dict additional_fields: Any fields to override with.

        :returns: The template fields updated with the additional_fields
        """
        output_parm = node.parm(self.OUTPUT_PARM)
        file_path = output_parm.unexpandedString()
        fields = self.get_work_template(node).validate_and_get_fields(file_path)
        if not fields:
            mesage = 'Can not extract Shotgun fields from "{}": "{}"'
            raise sgtk.TankError(mesage.format(output_parm.path(), file_path))
        if "SEQ" in fields:
            fields["SEQ"] = "FORMAT: $F"
        fields.update(additional_fields or {})
        return fields

    def generate_aov_path(self, node, channel, template_name):
        """
        Generate the file path for the given aov name.

        :param node: A :class:`hou.Node` instance.
        :param str channel: The aov name.
        :param str template_name: The name of the shotgun template to use.

        :returns: The file path for the aov output.
        """
        try:
            fields = self._get_template_fields_from(node)
            template = self._get_template(template_name)
        except sgtk.TankError as error:
            return str(error)
        if channel:
            fields["channel"] = channel
        try:
            file_path = template.apply_fields(fields)
        except sgtk.TankError:
            return self.AOV_ERROR
        return file_path

    def _lock_parms(self, node, lock):
        """
        Lock parms on the node is shotgun is enabled.

        :param node: A :class:`hou.Node` instance.
        :param bool lock: Lock parms if True.
        """
        self._lock_aov_parms(node, lock)
        archive_output = node.parm(self.ARCHIVE_OUTPUT)
        archive_output.lock(lock)

    def _update_aov_paths(self, node):
        """
        Update all the aov output paths on the node.

        :param node: A :class:`hou.Node` instance.
        """
        aov_count = node.parm(self.AOV_COUNT)
        count = aov_count.eval() + 1
        for index in range(1, count):
            aov_name = node.parm(self.AOV_NAME_TMPL.format(index))
            sgtk_aov_name = node.parm(self.SGTK_AOV_NAME_TMPL.format(index))
            sgtk_aov_name.set(aov_name.unexpandedString())
            self._update_aov_path(node, index)

    def update_file_path(self, node, parm_name, template_name, additional_fields=None):
        """
        Update the file path for the given parameter.

        :param node: A :class:`hou.Node` instance.
        :param str parm_name: The name of the parm to update.
        :param str template_name: The name of the shotgun template to use.
        :param dict additional_fields: Any fields to override the template fields with.
        """
        try:
            fields = self._get_template_fields_from(
                node, additional_fields=additional_fields
            )
            template = self._get_template(template_name)
            file_path = template.apply_fields(fields)
        except sgtk.TankError as error:
            file_path = str(error)
        parm = node.parm(parm_name)
        parm.lock(False)
        parm.set(file_path)
        parm.lock(True)

    #############################################################################################
    # Overriden methods
    #############################################################################################

    def _create_sgtk_parms(self, node):
        """
        Create the parameters that are going to live within the sgtk folder.

        :param node: A :class:`hou.Node` instance.

        :rtype: list(:class:`hou.ParmTemplate`)
        """
        templates = super(BaseRenderNodeHandler, self)._create_sgtk_parms(node)

        templates[-1].setJoinWithNext(True)

        sgtk_pass_name = hou.StringParmTemplate(
            self.SGTK_PASS_NAME,
            "Render Pass",
            1,
            default_value=("beauty",),
            script_callback=self.generate_callback_script_str(
                "validate_parm_and_refresh_path"
            ),
            script_callback_language=hou.scriptLanguage.Python,
        )
        sgtk_pass_name.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        templates.append(sgtk_pass_name)

        return templates

    def _update_template_fields(self, node, fields):
        """
        Update template fields from the node's parameter values.

        :param node: A :class:`hou.Node` instance.
        :param dict fields: Template fields.
        """
        super(BaseRenderNodeHandler, self)._update_template_fields(node, fields)
        sgtk_pass_name = node.parm(self.SGTK_PASS_NAME)
        pass_name = sgtk_pass_name.evalAsString().strip()
        if pass_name:
            fields["identifier"] = pass_name

    def _set_up_parms(self, node):
        """
        Set up the given node's parameters.

        :param node: A :class:`hou.Node` instance.
        """
        super(BaseRenderNodeHandler, self)._set_up_parms(node)
        self._lock_parms(node, True)

    def _enable_sgtk(self, node, sgtk_enabled):
        """
        Enable/disable the sgtk parameters.

        :param node: A :class:`hou.Node` instance.
        :param bool sgtk_enabled: The state to set the parameters to.
        """
        super(BaseRenderNodeHandler, self)._enable_sgtk(node, sgtk_enabled)
        self._lock_parms(node, sgtk_enabled)
        if sgtk_enabled:
            self._update_aov_paths(node)

    def _refresh_file_path(self, node):
        """
        Refresh the file paths generated by the node handler.

        :param node: A :class:`hou.Node` instance.
        """
        super(BaseRenderNodeHandler, self)._refresh_file_path(node)
        aov_count = node.parm(self.AOV_COUNT)
        count = aov_count.eval() + 1
        for index in range(1, count):
            self._update_aov_path(node, index)
        self.update_file_path(node, self.ARCHIVE_OUTPUT, self.ARCHIVE_WORK_TEMPLATE)

    #############################################################################################
    # AOVs
    #############################################################################################

    def _update_aov_path(self, node, index):
        """
        Update the aov output path for the given index.

        :param node: A :class:`hou.Node` instance.
        :param int index: The index of the aov parm.

        :raises: :class:`FieldInputError` on invalid input.
        """
        parm = node.parm(self.SGTK_AOV_NAME_TMPL.format(index))
        aov_name = node.parm(self.AOV_NAME_TMPL.format(index))
        aov_file_path = node.parm(self.AOV_FILE_TMPL.format(index))
        try:
            self._validate_parm(parm)
        except Exception:
            aov_name.set("")
            aov_file_path.set(self.AOV_ERROR)
            raise
        aov = parm.evalAsString()
        aov_name.set(parm.unexpandedString())

        aov_path = self.generate_aov_path(node, aov, self.AOV_WORK_TEMPLATE)
        aov_file_path.lock(False)
        aov_file_path.set(aov_path)
        aov_file_path.lock(True)

    def update_aov_path(self, kwargs):
        """
        Callback to update the aov output path for the given index.
        """
        node = kwargs["node"]
        index = kwargs["script_multiparm_index"]
        self._update_aov_path(node, index)

    def _lock_aov_parms(self, node, lock):
        """
        Lock aov output path parms.

        :param node: A :class:`hou.Node` instance.
        :param bool lock: Lock parms if True.
        """
        aov_count = node.parm(self.AOV_COUNT)
        count = aov_count.eval() + 1
        for index in range(1, count):
            aov_file_path = node.parm(self.AOV_FILE_TMPL.format(index))
            aov_file_path.lock(lock)

    def lock_aov_parms(self, kwargs):
        """
        Callback to lock aov output path parms.
        """
        node = kwargs["node"]
        self._lock_aov_parms(node, True)

    #############################################################################################
    # Utilities
    #############################################################################################

    def _populate_aov_names(
        self, node, parent_parm_name, src_parm_name, dest_parm_name
    ):
        """
        Populate sgtk aov names from the original aov names.

        :param node: A :class:`hou.Node` instance.
        :param str parent_parm_name: The parent parm name.
        :param str src_parm_name: The source parm name.
        :param str dest_parm_name: The sgtk parm name.
        """
        parent_parm = node.parm(parent_parm_name)
        count = parent_parm.eval() + 1
        for index in range(1, count):
            src_parm = node.parm(src_parm_name.format(index))
            channel_name = src_parm.evalAsString()
            dest_parm = node.parm(dest_parm_name.format(index))
            dest_parm.set(channel_name)

    def _populate_from_fields(self, node, fields):
        """
        Populate the node from template fields.

        :param node: A :class:`hou.Node` instance.
        :param dict fields: The template fields.
        """
        super(BaseRenderNodeHandler, self)._populate_from_fields(node, fields)
        sgtk_pass_name = node.parm(self.SGTK_PASS_NAME)
        sgtk_pass_name.set(fields.get("identifier", ""))
        self._populate_aov_names(
            node, self.AOV_COUNT, self.AOV_NAME_TMPL, self.SGTK_AOV_NAME_TMPL
        )

    def _get_multi_parm_output_paths_and_templates(
        self,
        node,
        count_parm_name,
        use_file_parm_tmpl,
        file_parm_tmpl,
        work_template_name,
        publish_template_name,
        paths_and_templates,
    ):
        """
        Get the output path and the templates used for the given multi parms.

        :param node: A :class:`hou.Node` instance.
        :param str count_parm_name: The name of the count parameter to query.
        :param str use_file_parm_tmpl: The string template for the use file parm name.
        :param str file_parm_tmpl: The string template for the file parm name.
        :param work_template: The work :class:`sgtk.Template` for this parm.
        :param publish_template: The publish :class:`sgtk.Template` for this parm.
        :param list paths_and_templates: The current list of paths and templates
            to append to.
        """
        aov_work_template = self._get_template(work_template_name)
        aov_publish_template = self._get_template(publish_template_name)
        aov_count = node.parm(count_parm_name)
        count = aov_count.eval() + 1
        for index in range(1, count):
            aov_enabled = node.parm(use_file_parm_tmpl.format(index))
            if aov_enabled.eval():
                self._get_output_path_and_templates_for_parm(
                    node,
                    file_parm_tmpl.format(index),
                    aov_work_template,
                    aov_publish_template,
                    paths_and_templates,
                )

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
        paths_and_templates = super(
            BaseRenderNodeHandler, self
        )._get_output_paths_and_templates(node)

        # get extra image planes
        self._get_multi_parm_output_paths_and_templates(
            node,
            self.AOV_COUNT,
            self.AOV_USE_FILE_TMPL,
            self.AOV_FILE_TMPL,
            self.AOV_WORK_TEMPLATE,
            self.AOV_PUBLISH_TEMPLATE,
            paths_and_templates,
        )

        return paths_and_templates
