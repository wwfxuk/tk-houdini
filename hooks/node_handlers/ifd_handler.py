import sgtk


import hou

HookBaseClass = sgtk.get_hook_baseclass()


class IfdNodeHandler(HookBaseClass):

    NODE_TYPE = "ifd"

    OUTPUT_PARM = "vm_picture"

    VM_NUMAUX = "vm_numaux"
    VM_DCMFILENAME = "vm_dcmfilename"
    VM_DSMFILENAME = "vm_dsmfilename"
    VM_CRYPTOMATTE_LAYERS = "vm_cryptolayers"

    SGTK_DEEP_EXT = "sgtk_deep_extension"

    @staticmethod
    def generate_expression_str(method_name, *args):
        args = ["hou.pwd()"] + map(repr, args)
        args_str = ", ".join(args)
        expr_str = (
            "__import__('sgtk').platform.current_engine().node_handler(hou.pwd())"
            ".{method}({args})"
        ).format(method=method_name, args=args_str)
        return expr_str

    def _customise_parameter_group(self, parameter_group, sgtk_folder):
        # Insert sgtk folder before vm_picture
        images_folder = parameter_group.get("images6")
        index = images_folder.index_of_template(self.OUTPUT_PARM)
        images_folder.insert_template(index, sgtk_folder)
        
        # Add a callback to vm_numaux to set up children properly
        image_planes_folder = images_folder.get("output6_1")
        vm_numaux = image_planes_folder.get(self.VM_NUMAUX)
        vm_numaux_template = vm_numaux.template
        vm_numaux_template.setScriptCallback(
            self.generate_callback_script_str("setup_extra_image_planes")
        )
        vm_numaux_template.setScriptCallbackLanguage(hou.scriptLanguage.Python)

        # Add expressions to deep outputs and an extension choice drop down
        deep_folder = images_folder.get("output6_2")
        index = deep_folder.index_of_template("vm_dcmfilename")

        deep_template_name = self.extra_args.get("dcm_work_template")
        deep_template = self.parent.get_template_by_name(deep_template_name)
        choices = deep_template.keys["extension"].labelled_choices
        sgtk_deep_ext = hou.MenuParmTemplate(
            self.SGTK_DEEP_EXT,
            "Extension (sgtk only)",
            choices.keys(),
            menu_labels=choices.values()
        )
        sgtk_deep_ext.setConditional(
            hou.parmCondType.DisableWhen,
            "{ use_sgtk != 1 } { vm_deepresolver == null }"
        )
        deep_folder.insert_template(index, sgtk_deep_ext)

        # cryptomatte_folder = images_folder.get("output6_3")
        # vm_cryptolayers = cryptomatte_folder.get(self.VM_CRYPTOMATTE_LAYERS)

    def _setup_deep_parms(self, node, sgtk_enabled=True):
        parm_names = (self.VM_DCMFILENAME, self.VM_DSMFILENAME)
        template_names = ("dcm_work_template", "dsm_work_template")
        for parm_name, template_name in zip(parm_names, template_names):
            parm = node.parm(parm_name)
            if sgtk_enabled:
                parm.setExpression(
                    self.generate_expression_str(
                        "update_deep_parm",
                        template_name
                    ),
                    language=hou.exprLanguage.Python,
                    replace_expression=True
                )
            else:
                parm.deleteAllKeyframes()
            parm.disable(sgtk_enabled)

    def setup_parms(self, node):
        super(IfdNodeHandler, self).setup_parms(node)
        self._setup_deep_parms(node)

    def update_deep_parm(self, node, template_name):
        try:
            template = self._get_work_template(template_name)
            fields = self._get_template_fields_from(node, template)
            sgtk_deep_ext = node.parm(self.SGTK_DEEP_EXT)
            fields["extension"] = sgtk_deep_ext.evalAsString()
            filepath = template.apply_fields(fields)
        except sgtk.TankError as error:
            return str(error)
        return filepath

    def _setup_extra_image_plane(self, node, index, sgtk_enabled):
        parm = node.parm("vm_filename_plane{}".format(index))
        if sgtk_enabled:
            expression = self.generate_expression_str(
                "update_extra_image_plane_filepath",
                index
            )
            parm.setExpression(
                expression,
                language=hou.exprLanguage.Python,
                replace_expression=True
            )
        else:
            parm.deleteAllKeyframes()

    def setup_extra_image_planes(self, kwargs):
        node = kwargs["node"]
        vm_numaux = node.parm(self.VM_NUMAUX)
        index = vm_numaux.eval()
        use_sgtk = node.parm(self.USE_SGTK)
        sgtk_enabled = use_sgtk.eval()
        if index > 0:
            self._setup_extra_image_plane(node, index, sgtk_enabled)

    def _get_work_template(self, template_name):
        work_template_name = self.extra_args.get(template_name)
        if not work_template_name:
            raise sgtk.TankError("No workfile template name defined")
        work_template = self.parent.get_template_by_name(work_template_name)
        if not work_template:
            raise sgtk.TankError("Can't find work template")
        return work_template

    def _get_template_fields_from(self, node, template):
        sgtk_output = node.parm(self.SGTK_OUTPUT)
        filepath = sgtk_output.evalAsString()
        fields = self.work_template.validate_and_get_fields(filepath)
        if not fields:
            raise sgtk.TankError("Can not extract fields from file path")
        return fields

    def update_extra_image_plane_filepath(self, node, index):
        try:
            template = self._get_work_template("extra_plane_work_template")
            fields = self._get_template_fields_from(node, template)
            channel_parm = node.parm("vm_channel_plane{}".format(index))
            channel = channel_parm.evalAsString()
            if channel:
                fields["channel"] = channel
            filepath = template.apply_fields(fields)
        except sgtk.TankError as error:
            return str(error)
        return filepath

    def _enable_extra_image_planes(self, node, sgtk_enabled):
        vm_numaux = node.parm(self.VM_NUMAUX)
        count = vm_numaux.eval() + 1
        for index in range(1, count):
            self._setup_extra_image_plane(node, index, sgtk_enabled)

    def enable_sgtk(self, kwargs):
        super(IfdNodeHandler, self).enable_sgtk(kwargs)
        node = kwargs["node"]
        use_sgtk = kwargs["parm"]
        sgtk_enabled = use_sgtk.eval()
        self._enable_extra_image_planes(node, sgtk_enabled)
        self._setup_deep_parms(node, sgtk_enabled=sgtk_enabled)