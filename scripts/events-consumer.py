import asyncio
import json
import os
import subprocess
import uuid

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

def consume_messages_in_batches(consumer, batch_size=10, timeout=5, idle_timeout=10):
    """
    Consume Kafka messages in batches. If no messages are received within the idle_timeout, invoke the Kuadrant CLI.
    """
    idle_time = 0  # Tracks the time spent idle
    try:
        while True:
            messages = consumer.consume(batch_size, timeout=timeout)

            if messages:
                idle_time = 0
                process_messages(messages)
            else:
                idle_time += timeout
                if idle_time >= idle_timeout:
                    print("No messages left in Kafka. Invoking Kuadrant CLI...")
                    invoke_kuadrant_cli()
                    break
    finally:
        consumer.close()

def process_messages(messages):
    """
    Process a batch of messages.
    """
    for msg in messages:
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                print(f"Error occurred: {msg.error()}")
                continue

        try:
            process_message(msg)
        except json.JSONDecodeError as e:
            print(f"Error decoding message: {e}")


def process_message(msg):
    """
    Process the Kafka message to extract artifactId, version, and group_id (if present).
    """
    try:
        msg_value = json.loads(msg.value().decode('utf-8'))
        payload = json.loads(msg_value['payload'])

        artifact_id = payload.get('artifactId')
        version = payload.get('version')

        event_type = payload.get('eventType')
        group_id = payload.get('group_id', 'default')

        if event_type == "ARTIFACT_VERSION_CREATED":
            print(f"Artifact version created event - {event_type}: Artifact ID: {artifact_id}, Version: {version}")
            asyncio.run(get_artifact_content(group_id, artifact_id, version))
        elif event_type == "ARTIFACT_VERSION_DELETED":
            print(f"Artifact version deleted event - {event_type}: Artifact ID: {artifact_id}, Version: {version}")
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
    in the api-definitions directory.
    """
    folder_path = os.path.join(os.path.dirname(os.getcwd()), 'api-definitions')

    filename = f"{group_id}_{artifact_id}_v{version}.yaml"
    file_path = os.path.join(folder_path, filename)

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
    folder_path = os.path.join(os.path.dirname(os.getcwd()), 'api-resources')

    os.makedirs(folder_path, exist_ok=True)

    filename = f"{group_id}_{artifact_id}_v{version}.yaml"
    file_path = os.path.join(folder_path, filename)

    if isinstance(content, bytes):
        content = content.decode('utf-8')

    with open(file_path, 'w') as file:
        file.write(content)

    print(f"Content saved to {file_path}")


def invoke_kuadrant_cli():
    """
    Invokes the kuadrantctl CLI for each OpenAPI file present in the api-resources directory.
    """
    folder_path = os.path.join(os.path.dirname(os.getcwd()), 'api-resources')

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        if os.path.isfile(file_path):
            print(f"Processing file: {file_path}")

            gateway_api_command = [
                'kuadrantctl', 'generate', 'gatewayapi', 'httproute',
                '--oas', file_path,
                '-o', 'yaml'
            ]

            authpolicy_command = [
                'kuadrantctl', 'generate', 'kuadrant', 'authpolicy',
                '--oas', file_path,
                '-o', 'yaml'
            ]

            ratelimit_policy_command = [
                'kuadrantctl', 'generate', 'kuadrant', 'ratelimitpolicy',
                '--oas', file_path,
                '-o', 'yaml'
            ]

            gateway_api_resource = invoke_kuadrant_command(authpolicy_command, filename)
            authpolicy_resource = invoke_kuadrant_command(authpolicy_command, filename)
            ratelimit_policy_resource = invoke_kuadrant_command(ratelimit_policy_command, filename)

            apply_kuadrant_resource(gateway_api_resource)
            apply_kuadrant_resource(authpolicy_resource)
            apply_kuadrant_resource(ratelimit_policy_resource)


def apply_kuadrant_resource(resource_string):
    """
    Apply a Kuadrant resource to the Kubernetes cluster using kubectl with the resource in string format.
    """
    try:
        process = subprocess.run(
            ['kubectl', 'apply', '-f', '-', '-n', 'api-controller'],
            input=resource_string,
            text=True,
            check=True,
            capture_output=True
        )
        print(f"Successfully applied Kuadrant resource:\n{process.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"Error applying Kuadrant resource:\n{e.stderr}")



def invoke_kuadrant_command(kuadrant_command, filename):
    try:
        result = subprocess.run(kuadrant_command, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error invoking Kuadrant CLI for {filename}:\n{e.stderr}")


def main():
    """
    Main function to set up Kafka consumer and process messages in a loop.
    """
    consumer = create_consumer()
    consume_messages_in_batches(consumer, batch_size=10, timeout=5)
    exit(0)

# Entry point of the script
if __name__ == '__main__':
    main()
