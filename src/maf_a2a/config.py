from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    llm_base_url: str
    llm_api_key: str
    llm_model: str = "gpt-4o"
    a2a_port: int = 5000
    a2a_peer_url: str | None = None
    log_level: str = "INFO"
    otel_exporter_endpoint: str | None = None
    graphiti_uri: str | None = None
    neo4j_user: str = "neo4j"
    neo4j_password: str | None = None
    ssl_verify: bool = True

    @property
    def graphiti_enabled(self) -> bool:
        return self.graphiti_uri is not None
