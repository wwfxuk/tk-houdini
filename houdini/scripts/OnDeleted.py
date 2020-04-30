def run_on_deleted(node):
    try:
        import sgtk
    except ImportError:
        return
    engine = sgtk.platform.current_engine()
    if engine:
        handler = engine.node_handler(node)
        if handler:
            handler.on_deleted(node=node)


run_on_deleted(kwargs["node"])
