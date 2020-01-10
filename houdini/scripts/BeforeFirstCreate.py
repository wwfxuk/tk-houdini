def run_before_first_create(node, node_type):
    try:
        import sgtk
    except ImportError:
        pass
    engine = sgtk.platform.current_engine()
    node_handlers = engine.get_setting("node_handlers")
    tk_houdini = engine.import_module("tk_houdini")
    base_class = tk_houdini.base_hooks.NodeHandlerBase
    for handler in node_handlers:
        if handler["node_type"] == node_type:
            engine.execute_hook_expression(
                handler["hook"],
                "before_first_create",
                base_class=base_class,
                node=node
            )
            break


run_before_first_create(kwargs["node"], kwargs["type"].name())
