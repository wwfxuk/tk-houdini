def run_on_updated(node):
    try:
        import sgtk
    except ImportError:
        return
    engine = sgtk.platform.current_engine()
    if engine:
        handler = engine.node_handler(node)
        if handler:
            handler.on_updated(node=node)


run_on_updated(kwargs["node"])
