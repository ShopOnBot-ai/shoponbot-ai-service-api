import asyncio
import json

from aiokafka import AIOKafkaConsumer

from app.core.config import settings
from app.core.logger import logger


class KafkaConsumerManager:
    def __init__(self):
        self._consumer: AIOKafkaConsumer | None = None
        self._isrunning: bool

    async def start(self) -> None:
        try:
            self._consumer = AIOKafkaConsumer(
                "product-events",
                bootstrap_servers=settings.kafka_bootstrap_server,
                group_id="ai-service-group",
                client_id='shoponbot-ai-client',
                auto_offset_reset="earliest"
            )

            await self._consumer.start()
            self._isrunning = True
            logger.info("Kafka connection handshake passed successfully. Cluster group listening active.")

            asyncio.create_task(self._consumer_loop())
        except Exception as e:
            logger.exception("Fail: Failed to establish secure connection pipeline to Kafka broker: %s", str(e))
            raise

    async def _consumer_loop(self) -> None:
        if not self._consumer:
            logger.error("Consumer instance found uninitialized inside execution thread context.")
            return

        try:
            async for msg in self._consumer:
                if not self._isrunning:
                    break

                try:
                    raw_payload = msg.value.decode("utf-8")
                    event_data = json.loads(raw_payload)

                    event_type = event_data.get("event_type")
                    event_payload = event_data.get("payload", {})

                    logger.info("📦 [AI SERVICE CONSUMER] Intercepted event structure type: %s", event_type)

                    if event_type == "ProductCreated":
                        logger.info("✨ Processing vector insertions for new product title: '%s'", event_payload.get("title"))
                        # TODO: Connect with Ollama Embedding Engine & Qdrant Seeding Task in the next micro-step!
                        
                    elif event_type == "ProductUpdated":
                        logger.info("Processing vector modifications for product ID: %s", event_payload.get("product_id"))
                        # TODO: Connect with Qdrant Vector Point Overwrite Task in the next micro-step!
                        
                    elif event_type == "ProductDeleted":
                        logger.info("Processing vector permanent deletion wipeout for product ID: %s", event_payload.get("product_id"))
                        # TODO: Connect with Qdrant Point Deletion Task in the next micro-step!

                except json.JSONDecodeError:
                    logger.error("Failed to parse incoming payload binary string parameters into valid JSON schema.")
                except Exception as loop_err:
                    logger.error("Error processing specific intercepted message chunk context: %s", str(loop_err))
        except Exception as fatal_err:
            logger.critical("Fatal: Background ingestion daemon worker thread collapsed: %s", str(fatal_err))
        finally:
            logger.info("Message consumer loop exited processing state boundaries securely.")

    async def stop(self) -> None:
        self._isrunning = False
        if self._consumer:
            await self._consumer.stop()
            logger.info("Kafka channels disconnected cleanly. Lifecycle tasks terminated.")

kafka_consumer_manager = KafkaConsumerManager()
