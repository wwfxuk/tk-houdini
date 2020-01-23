def run_on_created(node):
    try:
        import sgtk
    except ImportError:
        pass
    engine = sgtk.platform.current_engine()
    handler = engine.node_handler(node)
    if handler:
        handler.on_created(node=node)


run_on_created(kwargs["node"])
