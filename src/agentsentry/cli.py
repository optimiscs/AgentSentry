from __future__ import annotations
import argparse
import json
from agentsentry.config import Settings


def main():
    parser = argparse.ArgumentParser(prog="agentsentry")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "init-demo",
        help="Initialize an isolated repository containing synthetic data only",
    )
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8080)
    demo = sub.add_parser("demo")
    demo.add_argument("name", choices=["issue", "secret", "approval", "memory"])
    sub.add_parser("purge")
    mcp = sub.add_parser("mcp")
    mcp.add_argument("--session", required=True)
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.command == "init-demo":
        from agentsentry.demo import seed

        seed(settings)
        print(
            json.dumps({"workspace": str(settings.workspace), "synthetic_only": True})
        )
        return
    if args.command == "serve":
        import uvicorn
        from agentsentry.api.app import create_app

        uvicorn.run(
            create_app(settings),
            host="127.0.0.1",
            port=args.port,
            workers=1,
            access_log=False,
        )
        return
    if args.command == "mcp":
        from agentsentry.gateway.mcp_server import serve

        serve(args.session)
        return
    from agentsentry.gateway.runtime import Runtime

    rt = Runtime(settings)
    try:
        if args.command == "demo":
            from agentsentry.demo import scenario

            print(json.dumps(scenario(rt, args.name), ensure_ascii=False, indent=2))
        elif args.command == "purge":
            rt.store.purge(settings.retention_days)
            print("Retention applied")
    finally:
        rt.close()


if __name__ == "__main__":
    main()
