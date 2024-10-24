# api-controller-poc

## Description

The purpose of this demo is to illustrate to create a workflow that allows API design and management in Openshift.
This project includes the following components:

* [Apicurio Studio](https://github.com/apicurio/apicurio-studio), a design tool for visually creating schemas.
* [Apicurio Registry](https://github.com/apicurio/apicurio-registry), a high performance, runtime registry for API designs and schemas.
* [Strimzi](https://github.com/strimzi), provides the ability to run Apache Kafka and Kafka Connect on Kubernetes.
* [PostgreSQL](https://github.com/postgres/postgres), a high performance open-source relational database.
* [Debezium](https://github.com/debezium/debezium/), a CDC platform for capturing changes from database transaction logs.
* [ArgoCD](https://github.com/argoproj/argo-cd), is a declarative, GitOps continuous delivery tool for Kubernetes.
* [Kuadrant](https://github.com/Kuadrant), an open-source project designed to provide a unified and simplified interface for managing multiple API gateways.

## Pre-requisites

An available Openshift cluster must be available in the user's kubeconfig.

The expected flow for this project is as follows:

* Step 1: The API design process starts in Apicurio Studio. This is where API developers, architects, and stakeholders define the API specification using the OpenAPI (or AsyncAPI) format. Here, they specify details like:
  * API paths (endpoints)
Methods (GET, POST, etc.)
Request/response formats
Security (OAuth2, JWT, etc.)
Rate limits, request quotas, etc.

* Step 2: Once the API design is completed by the team, the API specification is saved directly into Apicurio Registry from Apicurio Studio. Apicurio Registry provides versioning, storage, and governance for API designs.

* Step 3: When the new API spec is saved or an existing one is updated, Apicurio Registry emits an event. This event is triggered through Kafka.

* Step 4: The messages are consumed using the script events-consumer.py.

* Step 5: Upon consuming an event, the events-consumer.py script extracts the metadata (such as artifact identifier and version) from the event and retrieves the latest version of the API specification from Apicurio Registry.

* Step 6: The events-consumer.py script then stores the API specification in a Git repository located in the directory kuadrant-resources for additional version control and traceability. Storing API specs in Git allows the team to maintain a full history of the API designs outside the registry, making it easier to audit, collaborate, or revert changes.

The listener clones or pulls the latest version of the Git repository, commits the API spec (e.g., as api_specs/$API_ID.json), and pushes the updated repository.

* Step 7: Once the API spec is successfully stored in Git, the CI/CD Event Listener triggers an integration with Kuadrant. Kuadrant is responsible for managing the API’s policies (e.g., rate limiting, authentication, and access control).

The listener uses the information from the API spec (retrieved from Apicurio Registry) to enforce policies like security (OAuth2, JWT, etc.) and rate limiting.

* Step 9: The listener writes to a Git repo, that is used in a GitOps fashion to propagate changes to Kuadrant. An initial implementation will show how to achieve this via ArgoCD makes an API call to Kuadrant to apply or update the policies based on the spec. This step ensures that the API’s rate limits, authentication mechanisms, and traffic controls are enforced in line with the API’s definition.