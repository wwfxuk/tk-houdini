def run_on_name_changed(node):
    try:
        import sgtk
    except ImportError:
        return
    engine = sgtk.platform.current_engine()
    if engine:
        handler = engine.node_handler(node)
        if handler:
            handler.on_name_changed(node=node)


run_on_name_changed(kwargs["node"])
