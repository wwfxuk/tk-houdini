import sgtk

import hou


HookBaseClass = sgtk.get_hook_baseclass()


class BaseRenderNodeHandler(HookBaseClass):

    SGTK_PASS_NAME = "sgtk_pass_name"

    # aovs
    AOV_COUNT = ""
    AOV_NAME_TMPL = "{}"
    AOV_FILE_TMPL = "{}"
    AOV_USE_FILE_TMPL = "{}"

    # archives
    ARCHIVE_ENABLED = ""
    ARCHIVE_OUTPUT = ""

    ARCHIVE_ALL_VERSIONS = "sgtk_archive_all_versions"
    ARCHIVE_VERSION = "sgtk_archive_version"
    ARCHIVE_REFRESH_VERSIONS = "sgtk_archive_refresh_versions"
    ARCHIVE_RESOLVED_VERSION = "sgtk_archive_resolved_version"
    ARCHIVE_FOLDER = "sgtk_archive_folder"

    # templates
    AOV_WORK_TEMPLATE = "aov_work_template"
    AOV_PUBLISH_TEMPLATE = "aov_publish_template"
    ARCHIVE_WORK_TEMPLATE = ""
    ARCHIVE_PUBLISH_TEMPLATE = ""

    # strings
    AOV_ERROR = ""
    
    def _get_template_fields_from(self, node, additional_fields={}):
        output_parm = node.parm(self.OUTPUT_PARM)
        file_path = output_parm.unexpandedString()
        fields = self.get_work_template(node).validate_and_get_fields(file_path)
        if not fields:
            raise sgtk.TankError("Can not extract fields from file path")
        if "SEQ" in fields:
            fields["SEQ"] = "FORMAT: $F"
        fields.update(additional_fields)
        return fields
    
    def generate_aov_path(self, node, channel, template_name):
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
        self._lock_aov_parms(node, lock)
        archive_output = node.parm(self.ARCHIVE_OUTPUT)
        archive_output.lock(lock)

    def _update_sgtk_aov_names(self, node):
        aov_count = node.parm(self.AOV_COUNT)
        count = aov_count.eval() + 1
        for index in range(1, count):
            aov_name = node.parm(self.AOV_NAME_TMPL.format(index))
            sgtk_aov_name = node.parm(
                self.SGTK_AOV_NAME_TMPL.format(index)
            )
            sgtk_aov_name.set(aov_name.unexpandedString())
            self._update_aov_path(node, index)

    def update_file_path(self, node, parm_name, template_name, additional_fields={}):
        try:
            fields = self._get_template_fields_from(node, additional_fields=additional_fields)
            template = self._get_template(template_name)
            file_path = template.apply_fields(fields)
        except sgtk.TankError as error:
            file_path = str(error)
        parm = node.parm(parm_name)
        parm.lock(False)
        parm.set(file_path)
        parm.lock(True)

    def _update_archive_path(self, node, update_version=True):
        fields = self._get_template_fields_from(node)
        template = self._get_template(self.ARCHIVE_WORK_TEMPLATE)
        all_versions = self._resolve_all_versions_from_fields(node, fields, template)
        archive_version = node.parm(self.ARCHIVE_VERSION)
        self._update_all_versions(node, all_versions, parm_name=self.ARCHIVE_ALL_VERSIONS)
        
        if update_version:
            archive_version.set(len(all_versions))
        current = archive_version.evalAsString()
        resolved_version = self._resolve_version(all_versions, current)

        archive_resolved_version = node.parm(self.ARCHIVE_RESOLVED_VERSION)
        archive_resolved_version.set(str(resolved_version))
        
        additional_fields = {"version": resolved_version}
        self.update_file_path(node, self.ARCHIVE_OUTPUT, self.ARCHIVE_WORK_TEMPLATE, additional_fields)

    def update_archive_path(self, kwargs):
        node = kwargs["node"]
        archive_version = node.parm(self.ARCHIVE_VERSION)
        update_version = archive_version.evalAsString() in self.VERSION_POLICIES
        self._update_archive_path(node, update_version=update_version)

    def populate_archive_versions(self, kwargs):
        node = kwargs["node"]
        return self._populate_versions_for_parm(node, self.ARCHIVE_ALL_VERSIONS)

    #############################################################################################
    # UI Customisation
    #############################################################################################

    def _create_archive_versions_folder(self, node):
        return self._create_versions_folder(
            node,
            self.ARCHIVE_ENABLED,
            self.ARCHIVE_FOLDER,
            self.ARCHIVE_ALL_VERSIONS,
            self.ARCHIVE_VERSION,
            self.ARCHIVE_REFRESH_VERSIONS,
            self.ARCHIVE_RESOLVED_VERSION,
            "populate_archive_versions",
            "update_archive_path"
        )

    def _create_versions_folder(
            self,
            node,
            enabled_parm_name,
            folder_name,
            all_versions_name,
            version_name,
            refresh_versions_name,
            resolved_version_name,
            populate_callback_name,
            update_callback_name
        ):
        templates = []

        all_versions = hou.StringParmTemplate(
            all_versions_name,
            "All Versions",
            1,
            is_hidden=True
        )
        templates.append(all_versions)

        version = hou.MenuParmTemplate(
            version_name,
            "Version",
            tuple(),
            item_generator_script=self.generate_callback_script_str(populate_callback_name),
            item_generator_script_language=hou.scriptLanguage.Python,
            script_callback=self.generate_callback_script_str(update_callback_name),
            script_callback_language=hou.scriptLanguage.Python
        )
        version.setConditional(
            hou.parmCondType.DisableWhen,
            "{{ {} != 1 }} {{ use_sgtk != 1 }}".format(enabled_parm_name)
        )
        version.setJoinWithNext(True)
        templates.append(version)

        refresh_button = hou.ButtonParmTemplate(
            refresh_versions_name,
            "Refresh Versions",
            script_callback=self.generate_callback_script_str(update_callback_name),
            script_callback_language=hou.scriptLanguage.Python
        )
        refresh_button.setConditional(
            hou.parmCondType.DisableWhen,
            '{{ {} != 1 }} {{ use_sgtk != 1 }} {{ sgtk_element == "" }}'.format(enabled_parm_name)
        )
        refresh_button.setJoinWithNext(True)
        templates.append(refresh_button)

        resolved_version = hou.StringParmTemplate(
            resolved_version_name,
            "Resolved Version",
            1,
            default_value=("1",)
        )
        resolved_version.setConditional(hou.parmCondType.DisableWhen, "{ sgtk_archive_version != -1 }")
        templates.append(resolved_version)
        
        sgtk_folder = hou.FolderParmTemplate(
            folder_name,
            "SGTK",
            parm_templates=templates,
            folder_type=hou.folderType.Simple
        )
        return sgtk_folder

    #############################################################################################
    # Overriden methods
    #############################################################################################

    def _create_sgtk_parms(self, node):
        templates = super(BaseRenderNodeHandler, self)._create_sgtk_parms(node)

        templates[-1].setJoinWithNext(True)

        sgtk_pass_name = hou.StringParmTemplate(
            self.SGTK_PASS_NAME,
            "Render Pass",
            1,
            default_value=("beauty",),
            script_callback=self.generate_callback_script_str("validate_parm_and_refresh_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_pass_name.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        templates.append(sgtk_pass_name)
    
        return templates

    def _update_template_fields(self, node, fields):
        super(BaseRenderNodeHandler, self)._update_template_fields(node, fields)
        sgtk_pass_name = node.parm(self.SGTK_PASS_NAME)
        pass_name = sgtk_pass_name.evalAsString().strip()
        if pass_name:
            fields["identifier"] = pass_name

    def _set_up_parms(self, node):
        super(BaseRenderNodeHandler, self)._set_up_parms(node)
        self._lock_parms(node, True)

    def _enable_sgtk(self, node, sgtk_enabled):
        super(BaseRenderNodeHandler, self)._enable_sgtk(node, sgtk_enabled)
        self._lock_parms(node, sgtk_enabled)
        if sgtk_enabled:
            self._update_sgtk_aov_names(node)

    def _refresh_file_path(self, node, update_version=True):
        super(BaseRenderNodeHandler, self)._refresh_file_path(
            node,
            update_version=update_version
        )
        aov_count = node.parm(self.AOV_COUNT)
        count = aov_count.eval() + 1
        for index in range(1, count):
            self._update_aov_path(node, index)
        self.update_archive_path({"node": node})

    #############################################################################################
    # AOVs
    #############################################################################################

    def _update_aov_path(self, node, index):
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

        aov_path = self.generate_aov_path(
            node,
            aov,
            self.AOV_WORK_TEMPLATE
        )
        aov_file_path.lock(False)
        aov_file_path.set(aov_path)
        aov_file_path.lock(True)

    def update_aov_path(self, kwargs):
        node = kwargs["node"]
        index = kwargs["script_multiparm_index"]
        self._update_aov_path(node, index)

    def _lock_aov_parms(self, node, lock):
        aov_count = node.parm(self.AOV_COUNT)
        count = aov_count.eval() + 1
        for index in range(1, count):
            aov_file_path = node.parm(self.AOV_FILE_TMPL.format(index))
            aov_file_path.lock(lock)

    def lock_aov_parms(self, kwargs):
        node = kwargs["node"]
        self._lock_aov_parms(node, True)
    
    #############################################################################################
    # Utilities
    #############################################################################################

    def _populate_aov_names(self, node, parent_parm_name, src_parm_name, dest_parm_name):
        parent_parm = node.parm(parent_parm_name)
        count = parent_parm.eval() + 1
        for index in range(1, count):
            src_parm = node.parm(src_parm_name.format(index))
            channel_name = src_parm.evalAsString()
            dest_parm = node.parm(dest_parm_name.format(index))
            dest_parm.set(channel_name)

    def _populate_from_fields(self, node, fields):
        super(BaseRenderNodeHandler, self)._populate_from_fields(node, fields)
        sgtk_pass_name = node.parm(self.SGTK_PASS_NAME)
        sgtk_pass_name.set(fields.get("identifier", "beauty"))
        self._populate_aov_names(
            node, 
            self.AOV_COUNT,
            self.AOV_NAME_TMPL,
            self.SGTK_AOV_NAME_TMPL
        )

    def _get_multi_parm_output_paths_and_templates(
            self,
            node,
            count_parm_name,
            use_file_parm_tmpl,
            file_parm_tmpl,
            work_template_name,
            publish_template_name,
            paths_and_templates
        ):
        aov_work_template = self._get_template(work_template_name)
        aov_publish_template = self._get_template(publish_template_name)
        aov_count = node.parm(count_parm_name)
        count = aov_count.eval() + 1
        for index in range(1, count):
            aov_enabled = node.parm(use_file_parm_tmpl.format(index))
            if not aov_enabled.eval():
                continue
            self._get_output_path_and_templates_for_parm(
                node,
                file_parm_tmpl.format(index),
                aov_work_template,
                aov_publish_template,
                paths_and_templates
            )

    def _get_output_paths_and_templates(self, node):
        paths_and_templates = super(BaseRenderNodeHandler, self)._get_output_paths_and_templates(node)

        # get extra image planes
        self._get_multi_parm_output_paths_and_templates(
            node,
            self.AOV_COUNT,
            self.AOV_USE_FILE_TMPL,
            self.AOV_FILE_TMPL,
            self.AOV_WORK_TEMPLATE,
            self.AOV_PUBLISH_TEMPLATE,
            paths_and_templates
        )
        
        return paths_and_templates