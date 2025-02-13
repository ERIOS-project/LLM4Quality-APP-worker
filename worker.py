import pika
import json
import os
import time
import logging
import signal
from dotenv import load_dotenv
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Optional, Dict
from bson import ObjectId
from consistency_llm.consistency_evaluation.sca_evaluation import ScaEvaluation
from consistency_llm.consistency_evaluation.slca_evaluation import SlcaEvaluation
from consistency_llm.consistency_evaluation.lca_evaluation import LcaEvaluation
from consistency_llm.llm_queries.few_shot_cot_classification import FewShotCotClassification
from consistency_llm.llm_queries.initial_classification import InitialClassification

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env environment variables
load_dotenv()
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT") or 5672
RABBITMQ_USERNAME = os.getenv("RABBITMQ_USERNAME") or "guest"
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD") or "guest"
WORKER_REQUESTS_QUEUE = os.getenv("WORKER_REQUESTS_QUEUE")
WORKER_RESPONSES_QUEUE = os.getenv("WORKER_RESPONSES_QUEUE")
MAX_RETRIES = int(os.getenv("MAX_RETRIES"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS"))

# Global variables
current_message = None

class Result(BaseModel):
    circuit_de_prise_en_charge: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    professionnalisme_de_l_equipe: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    qualite_hoteliere: Dict[str, Dict[str, int]] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict):
        """
        Create a Result instance from a dictionary.
        """
        return cls(**data)

    def to_dict(self) -> dict:
        """
        Convert the Result instance to a dictionary.
        """
        return self.model_dump()


# Verbatim model
class Verbatim(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    content: str
    status: str
    result: Optional[Result] = None
    year: int
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        populate_by_name = True

    def to_json(self):
        return self.model_dump_json(by_alias=True, exclude_unset=True)

    @classmethod
    def from_json(cls, data: dict):
        return cls(
            id=str(data.get("id")) if data.get("id") else None,
            content=data["content"],
            status=data["status"],
            result=data.get("result"),
            year=data["year"],
            created_at=data.get("created_at"),
        )


def connect_to_rabbitmq():
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(
                f"Attempting to connect to RabbitMQ (Attempt {attempt + 1}/{MAX_RETRIES})..."
            )
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD))
            )
            logger.info("Successfully connected to RabbitMQ.")
            return connection
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"RabbitMQ connection failed: {e}")
            if attempt < MAX_RETRIES - 1:
                logger.info(f"Retrying in {RETRY_DELAY_SECONDS} seconds...")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.error("Max retries reached. Could not connect to RabbitMQ.")
                raise


def process_verbatim_pipeline(verbatim: Verbatim) -> Verbatim:
    """
    Process the pipeline for a given verbatim message.
    """
    try:
        output_dir = f"./tmp/output_{verbatim.id}"
        input_csv = f"./tmp/input_{verbatim.id}.csv"


        # Create the tmp directory if it doesn't exist
        os.makedirs("./tmp", exist_ok=True)

        # Write content to a CSV file
        with open(input_csv, "w") as csv_file:
            csv_file.write(verbatim.content)

        # LLM queries
        initial_classification = InitialClassification(input_csv, output_dir)
        initial_classification.run()
        few_shot_cot_classification = FewShotCotClassification(input_csv, output_dir)
        few_shot_cot_classification.run()

        # Consistency evaluation
        sca_evaluation = ScaEvaluation(output_dir)
        sca_evaluation.run()
        lca_evaluation = LcaEvaluation(output_dir)
        lca_evaluation.run()
        slca_evaluation = SlcaEvaluation(output_dir)
        slca_evaluation.run()

        # Get the result from the output file
        with open(f"{output_dir}/evaluations/slca/result_1.json", "r") as file:
            processed_result = json.load(file)
            processed_result = processed_result["output"]

        # Update the Verbatim instance
        verbatim.result = processed_result
        verbatim.status = "SUCCESS"

        # Clean up the tmp directory
        os.remove(input_csv)
        os.system(f"rm -rf {output_dir}")

        return verbatim

    except Exception as e:
        logger.error(f"Error in processing pipeline: {e}")
        # Return the verbatim with an error status
        verbatim.status = "ERROR"
        return verbatim


def callback(ch, method, properties, body):
    global current_message
    try:
        current_message = {"channel": ch, "method": method, "body": body}
        message = json.loads(body)

        logger.info(f"Received message: {message}")

        verbatim = Verbatim.from_json(json.loads(message))
        processed_verbatim = process_verbatim_pipeline(verbatim)

        publish_message(WORKER_RESPONSES_QUEUE, processed_verbatim.to_json())
        logger.info(
            f"Processed and published result for verbatim ID: {processed_verbatim.id}"
        )

        ch.basic_ack(delivery_tag=method.delivery_tag)
        current_message = None  # Clear the current message after processing
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def publish_message(queue, message):
    connection = connect_to_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue=queue, durable=True)
    channel.basic_publish(exchange="", routing_key=queue, body=message)
    connection.close()


def main():
    global current_message
    def handle_interrupt(signal_received, frame):
        if current_message:
            logger.warning("Worker interrupted. Requeuing current message.")
            try:
                ch = current_message["channel"]
                method = current_message["method"]
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            except Exception as e:
                logger.error(f"Error requeuing message: {e}")
        exit(0)

    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)


    connection = connect_to_rabbitmq()
    channel = connection.channel()

    channel.queue_declare(queue=WORKER_REQUESTS_QUEUE, durable=True)

    # Ensure only one unacknowledged message is delivered to each worker at a time
    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(queue=WORKER_REQUESTS_QUEUE, on_message_callback=callback)

    logger.info(f"Listening for messages on {WORKER_REQUESTS_QUEUE}...")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("Worker shutting down...")
        channel.stop_consuming()
        connection.close()


if __name__ == "__main__":
    main()
