from . import cli

if __name__ == '__main__':
    try:
        import uvloop

        uvloop.install()
    except ImportError:
        pass

    cli()
