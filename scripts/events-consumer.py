import asyncio
import json
import uuid
import os

from apicurioregistrysdk.client.registry_client import RegistryClient
from confluent_kafka import Consumer, KafkaError
from httpx import AsyncClient
from kiota_abstractions.authentication import AnonymousAuthenticationProvider
from kiota_http.httpx_request_adapter import HttpxRequestAdapter

KAFKA_TOPIC = 'outbox.event.registry-events'
APICURIO_REGISTRY_URL = "https://apicurio-registry-api-controller.apps.api-controller.apicurio.integration-qe.com/apis/registry/v3"
KAFKA_BOOTSTRAP_SERVERS = 'kafka-cluster-kafka-bootstrap-api-controller.apps.api-controller.apicurio.integration-qe.com:443'
GROUP_ID = uuid.uuid4()

def create_consumer():
    """
    Create and return a Kafka consumer configured for the given topic and server.
    """
    consumer = Consumer({
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': GROUP_ID,
        'auto.offset.reset': 'earliest',
        'security.protocol': 'SSL',
        'enable.ssl.certificate.verification': 'false',
    })
    consumer.subscribe([KAFKA_TOPIC])
    return consumer


def process_message(msg):
    """
    Process the Kafka message to extract artifactId, version, and group_id (if present).
    """
    try:
        msg_value = json.loads(msg.value().decode('utf-8'))
        payload = json.loads(msg_value['payload'])

        # Extract artifactId and version
        artifact_id = payload.get('artifactId')
        version = payload.get('version')

        event_type = payload.get('eventType')
        group_id = payload.get('group_id', 'default')

        # Perform different actions based on eventType
        if event_type == "ARTIFACT_VERSION_CREATED":
            asyncio.run(get_artifact_content(group_id, artifact_id, version))
        elif event_type == "ARTIFACT_VERSION_DELETED":
            delete_file_if_exists(group_id, artifact_id, version)
        else:
            print(f"Other Event - {event_type}: Artifact ID: {artifact_id}, Version: {version}")

    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON message: {e}")
    except KeyError as e:
        print(f"Missing expected key: {e}")


async def get_artifact_content(group_id, artifact_id, version):
    """
    Fetch the artifact content from Apicurio Registry using the artifact ID and version.
    """
    try:
        authentication_provider = AnonymousAuthenticationProvider()
        client = AsyncClient(verify=False)
        request_adapter = HttpxRequestAdapter(authentication_provider=authentication_provider, http_client=client)
        request_adapter.base_url = APICURIO_REGISTRY_URL
        client = RegistryClient(request_adapter)

        artifact_content = await client.groups.by_group_id(group_id).artifacts.by_artifact_id(
            artifact_id).versions.by_version_expression(version).content.get()

        save_content_to_file(group_id, artifact_id, version, artifact_content)


    except Exception as e:
        print(f"Failed to retrieve artifact content for {artifact_id} version {version}: {e}")
        return None

def delete_file_if_exists(group_id, artifact_id, version):
    """
    Delete the file named using the groupId, artifactId, and version if it exists
    in the kuadrant-resources directory.
    """
    # Determine the folder path (one level up from current directory)
    folder_path = os.path.join(os.path.dirname(os.getcwd()), 'kuadrant-resources')

    # Construct the filename using groupId, artifactId, and version
    filename = f"{group_id}_{artifact_id}_v{version}.json"
    file_path = os.path.join(folder_path, filename)

    # Check if the file exists
    if os.path.exists(file_path):
        # Delete the file
        os.remove(file_path)
        print(f"File {file_path} has been deleted.")
    else:
        print(f"File {file_path} does not exist, so nothing was deleted.")

def save_content_to_file(group_id, artifact_id, version, content):
    """
    Save the given content to a file named using the groupId, artifactId, and version.
    """
    # Determine the folder path (one level up from current directory)
    folder_path = os.path.join(os.path.dirname(os.getcwd()), 'kuadrant-resources')

    # Ensure the folder exists
    os.makedirs(folder_path, exist_ok=True)

    # Construct the filename using groupId, artifactId, and version
    filename = f"{group_id}_{artifact_id}_v{version}.json"
    file_path = os.path.join(folder_path, filename)

    # Check if the content is in bytes and decode it to a string
    if isinstance(content, bytes):
        content = content.decode('utf-8')

    # Write content to the file
    with open(file_path, 'w') as file:
        file.write(content)

    print(f"Content saved to {file_path}")


def main():
    """
    Main function to set up Kafka consumer and process messages in a loop.
    """
    consumer = create_consumer()

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

            process_message(msg)

    finally:
        consumer.close()


# Entry point of the script
if __name__ == '__main__':
    main()
