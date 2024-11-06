import os
import subprocess
import yaml
import argparse

def invoke_kuadrant_cli(group_id, artifact_id, version, openapi_content):
    """
    Invokes the kuadrantctl CLI for the given coordinates and .
    """
    invoke_kuadrant_command(group_id, artifact_id, version, ['kuadrantctl', 'generate', 'gatewayapi', 'httproute', '--oas', '-'], openapi_content, 'httproute')
    invoke_kuadrant_command(group_id, artifact_id, version, ['kuadrantctl', 'generate', 'kuadrant', 'authpolicy', '--oas', '-'], openapi_content, 'authpolicy')
    invoke_kuadrant_command(group_id, artifact_id, version, ['kuadrantctl', 'generate', 'kuadrant', 'ratelimitpolicy', '--oas', '-'], openapi_content, 'ratelimiting_policy')

def invoke_kuadrant_command(group_id, artifact_id, version, args, openapi_content, filename):
    # Define the path to store the generated Kuadrant resources

    # Define the path based on group_id, artifact_id, and version
    folder_path = os.path.join(
        os.path.dirname(os.getcwd()),
        'api-resources/api-resources',
        group_id,
        artifact_id,
        version
    )

    os.makedirs(folder_path, exist_ok=True)

    # Define the output filename for the generated Kuadrant resource
    filename = f"{group_id}_{artifact_id}_v{version}_{filename}.yaml"
    file_path = os.path.join(folder_path, filename)

    try:
        if isinstance(openapi_content, bytes):
            openapi_content = openapi_content.decode("utf-8")

        # Invoke kuadrantctl to generate resources from OpenAPI content
        process = subprocess.run(
            args,
            input=openapi_content,  # Pass the OpenAPI content as input
            text=True,  # Treat input as a string
            capture_output=True,
            check=True
        )

        data = yaml.safe_load(process.stdout)

        #Remove the status part, otherwise the sync will fail
        data.pop('status', None)

        # Write the generated output to the file
        with open(file_path, 'w') as file:
            yaml.dump(data, file, default_flow_style=False)
        print(f"Kuadrant resource generated and saved to {file_path}")

    except subprocess.CalledProcessError as e:
        print(f"Error generating Kuadrant resources:\n{e.stderr}")

def commit_and_push_to_git():
    """
    Commit and push all changes in the api-resources/api-resources directory to the Git repository.
    """
    api_resources_path = os.path.join(os.path.dirname(os.getcwd()), 'api-resources/api-resources')

    try:
        subprocess.run(['git', '-C', api_resources_path, 'add', '.'], check=True)

        commit_message = "Update Kuadrant resources"
        subprocess.run(['git', '-C', api_resources_path, 'commit', '-m', commit_message], check=True)

        subprocess.run(['git', '-C', api_resources_path, 'push'], check=True)

        print("Successfully committed and pushed changes to the Git repository.")
    except subprocess.CalledProcessError as e:
        print(f"Error committing and pushing to Git:\n{e.stderr}")

def read_yaml_file(filepath):
    with open(filepath, 'r') as file:
        return yaml.safe_load(file)

def get_file_content(filepath):
    with open(filepath, 'r') as file:
        return file.read()

def process_artifacts(directory):
    artifacts_data = []

    # Traverse the directory looking for artifact files
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.yaml'):
                artifact_filepath = os.path.join(root, filename)

                # Load the artifact file
                artifact_data = read_yaml_file(artifact_filepath)

                # Skip if it's not an artifact file
                if artifact_data.get('$type') != 'artifact-v0':
                    continue

                group_id = artifact_data.get('groupId')
                artifact_id = artifact_data.get('id')

                # Process each version in the artifact file
                for version in artifact_data.get('versions', []):
                    version_id = str(version.get('id'))
                    content_file_path = os.path.join(root, version.get('contentFile'))

                    # Load the version content file
                    version_content_data = read_yaml_file(content_file_path)

                    # Verify the content file type
                    if version_content_data.get('$type') != 'content-v0':
                        continue

                    # Extract data file path and read actual content
                    data_file_path = os.path.join(root, version_content_data.get('dataFile'))
                    actual_content = get_file_content(data_file_path)

                    invoke_kuadrant_cli(group_id, artifact_id, version_id, actual_content)

    commit_and_push_to_git()


def main(directory_path):
    """
    Main function to set up Kafka consumer and process messages in a loop.
    """
    process_artifacts(directory_path)


# Entry point of the script
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Process OpenAPI definitions and interact with Git")
    parser.add_argument('--directory-path', required=True, help="Directory where the Apicurio Registry Gitops resources are located")
    args = parser.parse_args()
    main(args.directory_path)
