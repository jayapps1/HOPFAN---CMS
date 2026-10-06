"""Run the online API with the shared environment settings and safe defaults."""
from src.config.online_settings import OnlineSettings


def main() -> None:
    import uvicorn

    settings = OnlineSettings.from_environment()
    print(f"HOPFAN API: http://{settings.api_host}:{settings.api_port}")
    if settings.api_docs_enabled:
        print(f"API documentation: http://{settings.api_host}:{settings.api_port}/docs")
    uvicorn.run(
        "src.api.main:app", host=settings.api_host, port=settings.api_port,
        access_log=False, proxy_headers=False,
    )


if __name__ == "__main__":
    main()
