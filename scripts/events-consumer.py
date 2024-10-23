from confluent_kafka import Consumer, KafkaError
import uuid

# Configuration
KAFKA_TOPIC = 'outbox.event.registry-events'
KAFKA_BOOTSTRAP_SERVERS = 'kafka-cluster-kafka-bootstrap-api-controller.apps.api-controller.apicurio.integration-qe.com:443'  # e.g., 'kafka:9092'
GROUP_ID = uuid.uuid4()

# Create Kafka consumer
consumer = Consumer({
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'group.id': GROUP_ID,
    'auto.offset.reset': 'earliest',
    'security.protocol': 'SSL',
    'enable.ssl.certificate.verification': 'false',
})

consumer.subscribe([KAFKA_TOPIC])

# Process messages
try:
    while True:
        msg = consumer.poll(1.0)  # Timeout of 1 second
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                # End of partition event
                continue
            else:
                print(f"Error occurred: {msg.error()}")
                break

        print(f"Received message: {msg.value().decode('utf-8')}")

finally:
    consumer.close()