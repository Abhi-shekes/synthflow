import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RabbitMQOutputCreate(BaseModel):
    host: str
    port: int = 5672
    vhost: str = "/"
    username: str = "guest"
    password: str = "guest"
    # Empty means RabbitMQ's default exchange, where the routing key is the
    # queue name.
    exchange: str = ""
    routing_key: str
    events_per_second: float = Field(default=1.0, gt=0)
    batch_size: int = Field(default=1, gt=0)


class RabbitMQOutputRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    host: str
    port: int
    vhost: str
    username: str
    exchange: str
    routing_key: str
    events_per_second: float
    batch_size: int
    created_at: datetime
