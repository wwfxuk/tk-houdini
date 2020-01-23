import sgtk

import hou


HookBaseClass = sgtk.get_hook_baseclass()


class BaseRenderNodeHandler(HookBaseClass):

    SGTK_PASS_NAME = "sgtk_pass_name"

    # aovs
    AOV_COUNT = ""
    AOV_NAME_TMPL = "{}"
    AOV_FILE_TMPL = "{}"

    # templates
    AOV_WORK_TEMPLATE = "aov_work_template"

    # strings
    AOV_ERROR = ""
    
    def _get_template_fields_from(self, node, additional_fields={}):
        output_parm = node.parm(self.OUTPUT_PARM)
        file_path = output_parm.evalAsString()
        fields = self.get_work_template(node).validate_and_get_fields(file_path)
        if not fields:
            raise sgtk.TankError("Can not extract fields from file path")
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

    def _setup_parms(self, node):
        super(BaseRenderNodeHandler, self)._setup_parms(node)
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