import os

import sgtk

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class IfdNodeHandler(HookBaseClass):

    NODE_TYPE = "ifd"

    OUTPUT_PARM = "vm_picture"

    VM_NUMAUX = "vm_numaux"
    VM_DCMFILENAME = "vm_dcmfilename"
    VM_DSMFILENAME = "vm_dsmfilename"
    VM_CRYPTOLAYERS = "vm_cryptolayers"
    SOHO_DISKFILE = "soho_diskfile"

    SGTK_DEEP_EXT = "sgtk_deep_extension"
    SGTK_PASS_NAME = "sgtk_pass_name"

    DCM_WORK_TEMPLATE = "dcm_work_template"
    DSM_WORK_TEMPLATE = "dsm_work_template"
    IFD_WORK_TEMPLATE = "ifd_work_template"
    EXTRA_PLANE_WORK_TEMPLATE = "extra_plane_work_template"
    MANIFEST_NAME_TEMPLATE = "manifest_name_template"

    @staticmethod
    def generate_expression_str(method_name, *args):
        args = ["hou.pwd()"] + map(repr, args)
        args_str = ", ".join(args)
        expr_str = (
            "__import__('sgtk').platform.current_engine().node_handler(hou.pwd())"
            ".{method}({args})"
        ).format(method=method_name, args=args_str)
        return expr_str

    def _get_template_fields_from(self, node, template):
        sgtk_output = node.parm(self.SGTK_OUTPUT)
        filepath = sgtk_output.evalAsString()
        fields = self.work_template.validate_and_get_fields(filepath)
        if not fields:
            raise sgtk.TankError("Can not extract fields from file path")
        return fields
    
    def generate_pass_name(self, node, parm_name, template_name):
        try:
            template = self._get_template(template_name)
            fields = self._get_template_fields_from(node, template)
            channel_parm = node.parm(parm_name)
            channel = channel_parm.evalAsString()
            if channel:
                fields["channel"] = channel
            filepath = template.apply_fields(fields)
        except sgtk.TankError as error:
            return str(error)
        return filepath

    #############################################################################################
    # Overriden methods
    #############################################################################################

    def _add_identifier_parm_template(self, templates):
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

    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        images_folder = parameter_group.get("images6")
        index = images_folder.index_of_template(self.SGTK_FOLDER)
        images_folder.pop_template(index)
        
        image_planes_folder = images_folder.get("output6_1")
        vm_numaux = image_planes_folder.get(self.VM_NUMAUX)
        vm_numaux_template = vm_numaux.template
        vm_numaux_template.setScriptCallback("")

        deep_folder = images_folder.get("output6_2")
        index = deep_folder.index_of_template(self.SGTK_DEEP_EXT)
        deep_folder.pop_template(index)
        
        cryptomatte_folder = images_folder.get("output6_3")
        vm_cryptolayers = cryptomatte_folder.get(self.VM_CRYPTOLAYERS)
        vm_cryptolayers_template = vm_cryptolayers.template
        vm_cryptolayers_template.setScriptCallback("")

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
        index = deep_folder.index_of_template(self.VM_DCMFILENAME)

        deep_template_name = self.extra_args.get(self.DCM_WORK_TEMPLATE)
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

        # Add a callback to vm_cryptolayers
        cryptomatte_folder = images_folder.get("output6_3")
        vm_cryptolayers = cryptomatte_folder.get(self.VM_CRYPTOLAYERS)
        vm_cryptolayers_template = vm_cryptolayers.template
        vm_cryptolayers_template.setScriptCallback(
            self.generate_callback_script_str("setup_cryptolayeroutputs")
        )
        vm_cryptolayers_template.setScriptCallbackLanguage(hou.scriptLanguage.Python)

    def _update_template_fields(self, node, fields):
        super(IfdNodeHandler, self)._update_template_fields(node, fields)
        sgtk_pass_name = node.parm(self.SGTK_PASS_NAME)
        pass_name = sgtk_pass_name.evalAsString().strip()
        if pass_name:
            fields["identifier"] = pass_name

    def setup_parms(self, node):
        super(IfdNodeHandler, self).setup_parms(node)
        self._setup_deep_parms(node)
        self._setup_soho_diskfile_parms(node)

    def _enable_sgtk(self, node, sgtk_enabled):
        super(IfdNodeHandler, self)._enable_sgtk(node, sgtk_enabled)
        self._enable_extra_image_planes(node, sgtk_enabled)
        self._setup_deep_parms(node, sgtk_enabled=sgtk_enabled)
        self._setup_soho_diskfile_parms(node, sgtk_enabled=sgtk_enabled)
        self._enable_cryptolayeroutput(node, sgtk_enabled)

    #############################################################################################
    # Extra Image Planes
    #############################################################################################

    def _setup_extra_image_plane(self, node, index, sgtk_enabled):
        parm_name = "vm_filename_plane{}".format(index)
        parm = node.parm(parm_name)
        if sgtk_enabled:
            expression = self.generate_expression_str(
                "generate_pass_name",
                "vm_channel_plane{}".format(index),
                self.EXTRA_PLANE_WORK_TEMPLATE
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

    def _enable_extra_image_planes(self, node, sgtk_enabled):
        vm_numaux = node.parm(self.VM_NUMAUX)
        count = vm_numaux.eval() + 1
        for index in range(1, count):
            self._setup_extra_image_plane(node, index, sgtk_enabled)

    #############################################################################################
    # Deep Output
    #############################################################################################

    def update_deep_parm(self, node, template_name):
        try:
            template = self._get_template(template_name)
            fields = self._get_template_fields_from(node, template)
            sgtk_deep_ext = node.parm(self.SGTK_DEEP_EXT)
            fields["extension"] = sgtk_deep_ext.evalAsString()
            filepath = template.apply_fields(fields)
        except sgtk.TankError as error:
            return str(error)
        return filepath

    def _setup_deep_parms(self, node, sgtk_enabled=True):
        parm_names = (self.VM_DCMFILENAME, self.VM_DSMFILENAME)
        template_names = (self.DCM_WORK_TEMPLATE, self.DSM_WORK_TEMPLATE)
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

    #############################################################################################
    # Cryptomatte
    #############################################################################################

    def _setup_cryptolayeroutput(self, node, index, sgtk_enabled):
        vm_cryptolayeroutput_name = "vm_cryptolayeroutput{}".format(index)
        vm_cryptolayeroutput = node.parm(vm_cryptolayeroutput_name)

        vm_cryptolayersidecar_name = "vm_cryptolayersidecar{}".format(index)
        vm_cryptolayersidecar = node.parm(vm_cryptolayersidecar_name)
        
        vm_cryptolayername_name = "vm_cryptolayername{}".format(index)

        if sgtk_enabled:
            expression = self.generate_expression_str(
                "generate_pass_name",
                vm_cryptolayername_name,
                self.EXTRA_PLANE_WORK_TEMPLATE
            )
            vm_cryptolayeroutput.setExpression(
                expression,
                language=hou.exprLanguage.Python,
                replace_expression=True
            )

            expression = self.generate_expression_str(
                "generate_pass_name",
                vm_cryptolayername_name,
                self.MANIFEST_NAME_TEMPLATE
            )
            vm_cryptolayersidecar.setExpression(
                expression,
                language=hou.exprLanguage.Python,
                replace_expression=True
            )
        else:
            vm_cryptolayeroutput.deleteAllKeyframes()
            vm_cryptolayersidecar.deleteAllKeyframes()
    
    def setup_cryptolayeroutputs(self, kwargs):
        node = kwargs["node"]
        vm_cryptolayers = node.parm(self.VM_CRYPTOLAYERS)
        index = vm_cryptolayers.eval()
        use_sgtk = node.parm(self.USE_SGTK)
        sgtk_enabled = use_sgtk.eval()
        if index > 0:
            self._setup_cryptolayeroutput(node, index, sgtk_enabled)

    def _enable_cryptolayeroutput(self, node, sgtk_enabled):
        vm_cryptolayers = node.parm(self.VM_CRYPTOLAYERS)
        count = vm_cryptolayers.eval() + 1
        for index in range(1, count):
            self._setup_cryptolayeroutput(node, index, sgtk_enabled)

    #############################################################################################
    # SOHO DiskFile
    #############################################################################################

    def update_soho_diskfile_parm(self, node):
        try:
            template = self._get_template(self.IFD_WORK_TEMPLATE)
            fields = self._get_template_fields_from(node, template)
            filepath = template.apply_fields(fields)
        except sgtk.TankError as error:
            return str(error)
        return filepath

    def _setup_soho_diskfile_parms(self, node, sgtk_enabled=True):
        parm = node.parm(self.SOHO_DISKFILE)
        if sgtk_enabled:
            parm.setExpression(
                self.generate_expression_str(
                    "update_soho_diskfile_parm"
                ),
                language=hou.exprLanguage.Python,
                replace_expression=True
            )
        else:
            parm.deleteAllKeyframes()