import os

import sgtk

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class IfdNodeHandler(HookBaseClass):

    NODE_TYPE = "ifd"

    OUTPUT_PARM = "vm_picture"

    VM_NUMAUX = "vm_numaux"
    VM_CHANNEL_PLANE = "vm_channel_plane{}"
    VM_FILENAME_PLANE = "vm_filename_plane{}"
    VM_DCMFILENAME = "vm_dcmfilename"
    VM_DSMFILENAME = "vm_dsmfilename"
    VM_CRYPTOLAYERS = "vm_cryptolayers"
    VM_CRYPTOLAYERNAME = "vm_cryptolayername{}"
    VM_CRYPTOLAYEROUTPUT = "vm_cryptolayeroutput{}"
    VM_CRYPTOLAYERSIDECAR = "vm_cryptolayersidecar{}"
    SOHO_DISKFILE = "soho_diskfile"

    SGTK_PRESENT = "sgtk_present"
    SGTK_DEEP_EXT = "sgtk_deep_extension"
    SGTK_PASS_NAME = "sgtk_pass_name"
    SGTK_CHANNEL_PLANE = "sgtk_channel_plane{}"
    SGTK_CRYPTOLAYERNAME = "sgtk_cryptolayername{}"

    DCM_WORK_TEMPLATE = "dcm_work_template"
    DSM_WORK_TEMPLATE = "dsm_work_template"
    IFD_WORK_TEMPLATE = "ifd_work_template"
    EXTRA_PLANE_WORK_TEMPLATE = "extra_plane_work_template"
    MANIFEST_NAME_TEMPLATE = "manifest_name_template"

    CHANNEL_ERROR = "Channel Name not defined"

    @staticmethod
    def generate_expression_str(method_name, *args):
        args = ["hou.pwd()"] + map(repr, args)
        args_str = ", ".join(args)
        expr_str = (
            "__import__('sgtk').platform.current_engine().node_handler(hou.pwd())"
            ".{method}({args})"
        ).format(method=method_name, args=args_str)
        return expr_str

    def _get_template_fields_from(self, node):
        sgtk_output = node.parm(self.SGTK_OUTPUT)
        filepath = sgtk_output.evalAsString()
        fields = self.get_work_template(node).validate_and_get_fields(filepath)
        if not fields:
            raise sgtk.TankError("Can not extract fields from file path")
        return fields
    
    def generate_channel_path(self, node, channel, template_name):
        try:
            fields = self._get_template_fields_from(node)
            template = self._get_template(template_name)
        except sgtk.TankError as error:
            return str(error)
        if channel:
            fields["channel"] = channel
        try:
            filepath = template.apply_fields(fields)
        except sgtk.TankError:
            return self.CHANNEL_ERROR
        return filepath

    def _update_sgtk_channel_names(self, node):
        vm_numaux = node.parm(self.VM_NUMAUX)
        count = vm_numaux.eval() + 1
        for index in range(1, count):
            vm_channel_plane = node.parm(self.VM_CHANNEL_PLANE.format(index))
            sgtk_channel_plane = node.parm(self.SGTK_CHANNEL_PLANE.format(index))
            sgtk_channel_plane.set(vm_channel_plane.unexpandedString())
            self._update_channel_path(node, index)

        vm_cryptolayers = node.parm(self.VM_CRYPTOLAYERS)
        count = vm_cryptolayers.eval() + 1
        for index in range(1, count):
            vm_cryptolayername = node.parm(self.VM_CRYPTOLAYERNAME.format(index))
            sgtk_cryptolayername = node.parm(self.SGTK_CRYPTOLAYERNAME.format(index))
            sgtk_cryptolayername.set(vm_cryptolayername.unexpandedString())
            self._update_crypto_layer_path(node, index)

    #############################################################################################
    # Overriden methods
    #############################################################################################

    def _add_identifier_parm_template(self, node, templates):
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

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        if self.SGTK_PRESENT not in parameter_group:
            sgtk_present = hou.ToggleParmTemplate(
                self.SGTK_PRESENT,
                "sgtk present",
                default_value=True,
                is_hidden=True
            )
            parameter_group.append_template(sgtk_present)

        # Insert sgtk folder before vm_picture
        images_folder = parameter_group.get("images6")
        index = images_folder.index_of_template(self.OUTPUT_PARM)
        images_folder.insert_template(index, sgtk_folder)
        
        # Add a callback to vm_numaux to set up children properly
        image_planes_folder = images_folder.get("output6_1")
        vm_numaux = image_planes_folder.get(self.VM_NUMAUX)

        index = vm_numaux.index_of_template(self.VM_CHANNEL_PLANE.format("#"))
        sgtk_channel_plane = hou.StringParmTemplate(
            self.SGTK_CHANNEL_PLANE.format("#"),
            "Channel Name",
            1,
            script_callback=self.generate_callback_script_str("update_channel_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_channel_plane.setConditional(
            hou.parmCondType.DisableWhen,
            '{ vm_disable_plane# == 1 } { vm_variable_plane# == "" }'
        )
        sgtk_channel_plane.setConditional(
            hou.parmCondType.HideWhen, "{ use_sgtk != 1 }"
        )
        vm_numaux.insert_template(index, sgtk_channel_plane)

        vm_channel_plane = vm_numaux.get(self.VM_CHANNEL_PLANE.format("#"))
        vm_channel_plane_template = vm_channel_plane.template
        vm_channel_plane_template.setConditional(
            hou.parmCondType.HideWhen, "{ sgtk_present == 1 }"
        )

        vm_filename_plane = vm_numaux.get(self.VM_FILENAME_PLANE.format("#"))
        vm_filename_plane_template = vm_filename_plane.template
        vm_filename_plane_template.setDefaultValue((self.CHANNEL_ERROR,))
        vm_filename_plane_template.setConditional(
            hou.parmCondType.DisableWhen, "{ use_sgtk == 1 } { vm_usefile_plane# == 0 }"
        )

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

        vm_dcmfilename = deep_folder.get(self.VM_DCMFILENAME)
        vm_dcmfilename_template = vm_dcmfilename.template
        vm_dcmfilename_template.setConditional(
            hou.parmCondType.DisableWhen,
            "{ use_sgtk == 1 } { vm_deepresolver != camera }"
        )

        vm_dsmfilename = deep_folder.get(self.VM_DSMFILENAME)
        vm_dsmfilename_template = vm_dsmfilename.template
        vm_dsmfilename_template.setConditional(
            hou.parmCondType.DisableWhen,
            "{ use_sgtk == 1 } { vm_deepresolver != shadow }"
        )

        # Add a callback to vm_cryptolayers
        cryptomatte_folder = images_folder.get("output6_3")
        vm_cryptolayers = cryptomatte_folder.get(self.VM_CRYPTOLAYERS)

        vm_cryptolayername =  vm_cryptolayers.get(self.VM_CRYPTOLAYERNAME.format("#"))
        vm_cryptolayername_template = vm_cryptolayername.template
        vm_cryptolayername_template.setConditional(
            hou.parmCondType.HideWhen, "{ sgtk_present == 1 }"
        )

        vm_cryptolayeroutput =  vm_cryptolayers.get(self.VM_CRYPTOLAYEROUTPUT.format("#"))
        vm_cryptolayeroutput_template = vm_cryptolayeroutput.template
        vm_cryptolayeroutput_template.setDefaultValue((self.CHANNEL_ERROR,))
        vm_cryptolayeroutput_template.setConditional(
            hou.parmCondType.DisableWhen, "{ use_sgtk == 1 } { vm_cryptolayeroutputenable# != 1 }"
        )

        vm_cryptolayersidecar =  vm_cryptolayers.get(self.VM_CRYPTOLAYERSIDECAR.format("#"))
        vm_cryptolayersidecar_template = vm_cryptolayersidecar.template
        vm_cryptolayersidecar_template.setDefaultValue((self.CHANNEL_ERROR,))
        vm_cryptolayersidecar_template.setConditional(
            hou.parmCondType.DisableWhen, "{ use_sgtk == 1 } { vm_cryptolayersidecarenable# != 1 }"
        )

        index = vm_cryptolayers.index_of_template(self.VM_CRYPTOLAYERNAME.format("#"))
        sgtk_cryptolayername = hou.StringParmTemplate(
            self.SGTK_CRYPTOLAYERNAME.format("#"),
            "Channel Name",
            1,
            script_callback=self.generate_callback_script_str("update_crypto_layer_path"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_cryptolayername.setConditional(
            hou.parmCondType.HideWhen, "{ use_sgtk != 1 }"
        )
        vm_cryptolayers.insert_template(index, sgtk_cryptolayername)

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
        self._setup_deep_parms(node, sgtk_enabled=sgtk_enabled)
        self._setup_soho_diskfile_parms(node, sgtk_enabled=sgtk_enabled)
        sgtk_present = node.parm(self.SGTK_PRESENT)
        sgtk_present.set(sgtk_enabled)
        if sgtk_enabled:
            self._update_sgtk_channel_names(node)

    def refresh_file_path(self, kwargs, update_version=True):
        super(IfdNodeHandler, self).refresh_file_path(kwargs, update_version=update_version)
        node = kwargs["node"]
        vm_numaux = node.parm(self.VM_NUMAUX)
        count = vm_numaux.eval() + 1
        for index in range(1, count):
            self._update_channel_path(node, index)

        vm_cryptolayers = node.parm(self.VM_CRYPTOLAYERS)
        count = vm_cryptolayers.eval() + 1
        for index in range(1, count):
            self._update_crypto_layer_path(node, index)

    #############################################################################################
    # Extra Image Planes
    #############################################################################################

    def _update_channel_path(self, node, index):
        parm = node.parm(self.SGTK_CHANNEL_PLANE.format(index))
        vm_channel_plane = node.parm(self.VM_CHANNEL_PLANE.format(index))
        vm_filename_plane = node.parm(self.VM_FILENAME_PLANE.format(index))
        try:
            self.validate_parm(parm)
        except Exception:
            vm_channel_plane.set("")
            vm_filename_plane.set(self.CHANNEL_ERROR)
            raise
        channel = parm.evalAsString()
        vm_channel_plane.set(parm.unexpandedString())

        channel_path = self.generate_channel_path(
            node,
            channel,
            self.EXTRA_PLANE_WORK_TEMPLATE
        )
        vm_filename_plane.set(channel_path)

    def update_channel_path(self, kwargs):
        node = kwargs["node"]
        index = kwargs["script_multiparm_index"]
        self._update_channel_path(node, index)

    #############################################################################################
    # Deep Output
    #############################################################################################

    def update_deep_parm(self, node, template_name):
        try:
            template = self._get_template(template_name)
            fields = self._get_template_fields_from(node)
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
                self._remove_expression_for_path(parm)

    #############################################################################################
    # Cryptomatte
    #############################################################################################

    def _update_crypto_layer_path(self, node, index):
        parm = node.parm(self.SGTK_CRYPTOLAYERNAME.format(index))
        vm_cryptolayername = node.parm(self.VM_CRYPTOLAYERNAME.format(index))
        vm_cryptolayeroutput = node.parm(self.VM_CRYPTOLAYEROUTPUT.format(index))
        vm_cryptolayersidecar = node.parm(self.VM_CRYPTOLAYERSIDECAR.format(index))
        try:
            self.validate_parm(parm)
        except Exception:
            vm_cryptolayername.set("")
            vm_cryptolayeroutput.set(self.CHANNEL_ERROR)
            vm_cryptolayersidecar.set(self.CHANNEL_ERROR)
            raise
        channel = parm.evalAsString()
        vm_cryptolayername.set(parm.unexpandedString())

        channel_path = self.generate_channel_path(
            node,
            channel,
            self.EXTRA_PLANE_WORK_TEMPLATE
        )
        vm_cryptolayeroutput.set(channel_path)

        sidecar_path = self.generate_channel_path(
            node,
            channel,
            self.MANIFEST_NAME_TEMPLATE
        )
        vm_cryptolayersidecar.set(sidecar_path)

    def update_crypto_layer_path(self, kwargs):
        node = kwargs["node"]
        index = kwargs["script_multiparm_index"]
        self._update_crypto_layer_path(node, index)

    #############################################################################################
    # SOHO DiskFile
    #############################################################################################

    def update_soho_diskfile_parm(self, node):
        try:
            template = self._get_template(self.IFD_WORK_TEMPLATE)
            fields = self._get_template_fields_from(node)
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
            self._remove_expression_for_path(parm)
    
    #############################################################################################
    # Utilities
    #############################################################################################

    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        images_folder = parameter_group.get("images6")
        index = images_folder.index_of_template(self.SGTK_FOLDER)
        images_folder.pop_template(index)
        
        image_planes_folder = images_folder.get("output6_1")
        vm_numaux = image_planes_folder.get(self.VM_NUMAUX)

        index = vm_numaux.index_of_template(self.SGTK_CHANNEL_PLANE.format("#"))
        vm_numaux.pop_template(index)

        vm_filename_plane = vm_numaux.get(self.VM_FILENAME_PLANE.format("#"))
        vm_filename_plane_template = vm_filename_plane.template
        vm_filename_plane_template.setDefaultValue(("",))

        deep_folder = images_folder.get("output6_2")
        index = deep_folder.index_of_template(self.SGTK_DEEP_EXT)
        deep_folder.pop_template(index)
        
        cryptomatte_folder = images_folder.get("output6_3")
        vm_cryptolayers = cryptomatte_folder.get(self.VM_CRYPTOLAYERS)

        index = vm_cryptolayers.index_of_template(self.SGTK_CRYPTOLAYERNAME.format("#"))
        vm_cryptolayers.pop_template(index)

        vm_cryptolayeroutput =  vm_cryptolayers.get(self.VM_CRYPTOLAYEROUTPUT.format("#"))
        vm_cryptolayeroutput_template = vm_cryptolayeroutput.template
        vm_cryptolayeroutput_template.setDefaultValue(("$HIP/CryptoMaterial.exr",))

        vm_cryptolayersidecar =  vm_cryptolayers.get(self.VM_CRYPTOLAYERSIDECAR.format("#"))
        vm_cryptolayersidecar_template = vm_cryptolayersidecar.template
        vm_cryptolayersidecar_template.setDefaultValue(("CryptoMaterial.json",))

    def _populate_channel_names(self, node, parent_parm_name, src_parm_name, dest_parm_name):
        parent_parm = node.parm(parent_parm_name)
        count = parent_parm.eval() + 1
        for index in range(1, count):
            src_parm = node.parm(src_parm_name.format(index))
            channel_name = src_parm.evalAsString()
            dest_parm = node.parm(dest_parm_name.format(index))
            dest_parm.set(channel_name)

    def _populate_from_fields(self, node, fields):
        super(IfdNodeHandler, self)._populate_from_fields(node, fields)
        sgtk_pass_name = node.parm(self.SGTK_PASS_NAME)
        sgtk_pass_name.set(fields.get("identifier", "beauty"))
        self._populate_channel_names(
            node, 
            self.VM_NUMAUX,
            self.VM_CHANNEL_PLANE,
            self.SGTK_CHANNEL_PLANE
        )
        self._populate_channel_names(
            node, 
            self.VM_CRYPTOLAYERS,
            self.VM_CRYPTOLAYERNAME,
            self.SGTK_CRYPTOLAYERNAME
        )

    def populate_sgtk_parms(self, node, use_next_version=True):
        vm_dcmfilename = node.parm(self.VM_DCMFILENAME)
        dcm_file_path = vm_dcmfilename.evalAsString()

        super(IfdNodeHandler, self).populate_sgtk_parms(node, use_next_version)
        
        dcm_template = self._get_template(self.DCM_WORK_TEMPLATE)
        dcm_fields = dcm_template.get_fields(dcm_file_path)
        if dcm_fields:
            sgtk_deep_extension = node.parm(self.SGTK_DEEP_EXT)
            entries = sgtk_deep_extension.menuItems()
            ext = dcm_fields.get("extension", "rat")
            index = entries.index(ext)
            sgtk_deep_extension.set(index)

        sgtk_present = node.parm(self.SGTK_PRESENT)
        use_sgtk = node.parm(self.USE_SGTK)
        sgtk_present.set(use_sgtk.eval())