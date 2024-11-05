# Apicurio API Controller

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

Any operator used in this demo must be installed using the Openshift console.

## Pre-requisites

* An available Openshift cluster must be available in the user's kubeconfig.
* Kuadrant must be installed in your cluster. Instructions to install can be found [here](https://docs.kuadrant.io/0.11.0/kuadrant-operator/doc/install/install-openshift/).
* Kuadrantctl is available locally. Instructions to install it can be found [here](https://github.com/Kuadrant/kuadrantctl?tab=readme-ov-file#installing-pre-compiled-binaries).
* oc cli is available locally.


## Installation

1. We must start by creating the Gateway that will handle the traffic for our applications. We provide one in [the deployments directory](./deployment/petstore/gateway.yaml)

2. Once the Gateway is available, we must create the namespace that will be used for this the diffent workflow components:

  `oc apply -f ./deployment/namespace/apicurio-api-controller.yaml`

3. Now we have to deploy Strimzi. It can be installed from Operator Hub in your Openshift cluster.

4. Once Strimzi is installed, we must create the Kafka cluster and the Connect cluster that will be used for firing events from Apicurio Registry:

`oc apply -f ./deployment/kafka/kafka.yaml`

  * We can check the state of the Kafka cluster using the following command:

`oc get kafka kafka-cluster -n api-controller -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'`

5. Once our Kafka cluster is ready, it's time to create the Kafka Connect cluster. This is a key component since the PostgreSQL connector that will be listening for events in the Apicurio Registry database will be deployed here.

`oc apply -f ./deployment/kafka/kafka-connect.yaml`

  * As with Kafka, we can check the status of the Connect cluster using:

`oc get kafkaconnect kafka-connect-cluster -n api-controller -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'`

6. Now we have our Kafka components ready to receive events, so we have to deploy the Apicurio components. We will start with Apicurio Registry, since Apicurio Studio will use it to store the API designs:

   * Deploy Apicurio Registry database: `oc apply -f ./deployment/apicurio-registry/postgresql.yaml`
   * Deploy Apicurio Registry backend: `oc apply -f ./deployment/apicurio-registry/registry-sql.yaml`
   * Deploy Apicurio Registry UI: `oc process -f ./deployment/apicurio-registry/registry-ui.yaml -p REGISTRY_API_URL="https://$(oc get route apicurio-registry -n api-controller -o jsonpath='{.spec.host}')/apis/registry/v3" | oc apply -f -`
   * Deploy Apicurio Studio UI: `oc process -f ./deployment/apicurio-studio/apicurio-studio.yaml -p APICURIO_REGISTRY_API_URL="https://$(oc get route apicurio-registry -n api-controller -o jsonpath='{.spec.host}')/apis/registry/v3" | oc apply -f -`

7. Once the Apicurio components have been installed, it's time to install the Postgresql connector that will be listening for events in Apicurio Registry and sending them to Kafka. This way we can use the [Python script](./scripts/events-consumer.py) to consume them.

  * Deploy Postgresql connector: `oc apply -f ./deployment/debezium/postgresql-source.yaml`
  * Check connector status: `oc get kafkaconnector postgres-connector0 -n api-controller -o jsonpath='{.status}'`

8. Install ArgoCD. For the full integration to work, argocd is required. It will sync the Kuadrant resources generated and apply them to the Openshift cluster. The argocd operator can be installed from the Openshift Console, just like Strimzi or Kuadrant. For convenience, we recommend installing the Red Hat OpenShift GitOps operator. This operator creates both an ArgoCD project and an ArgoCD instance that we will refer to in our application.

   * Once the ArgoCD operator has been installed, we must install the ArgoCD resources:
     * First we must create the ArgoCD role, so that the ArgoCD ServiceAccount can manage Kuadrant resources:  `oc apply -f ./deployment/argocd/cluster_role.yaml`
     * Assing the role to the ArgoCD service account: `oc apply -f ./deployment/argocd/argocd_role_binding.yaml`
     * Create ArgoCD app, changing the git repository and the directory to the values to be used by the synchronization: `oc apply -f ./deployment/argocd/argocd_app.yaml`


## Using the project.

### Pre-requisites

* This workflow assumes an existing git repository is setup in a directory `api-resources` in the project root directory. This is the same repository that must be configured in the ArgoCD application.
* Before going through the workflow, we will deploy an example application: `oc apply -f ./deployment/petstore/petstore.yaml`

### Workflow

We will discuss an example that uses the different components that have been deployed above. We must follow the steps below, that can be checked in the sequence diagram ![Sequence diagram displaying the flow for API designs going from Apicurio Studio to the Kuadrant resources being generated in the cluster](diagram.png):

* Step 1: The API design process starts in Apicurio Studio. This is where API developers, architects, and stakeholders define the API specification using the OpenAPI (or AsyncAPI) format. Here, they specify details like:
  * API paths (endpoints)
Methods (GET, POST, etc.)
Request/response formats
Security (OAuth2, JWT, etc.)
Rate limits, request quotas, etc.

* Step 2: We must go to Apicurio Studio and copy the [petstore API spec](./deployment/petstore/petstore-with-rate-limit.yaml). This OpenAPI spec has a rate limit specification defined using the x-kuadrant format.

* Step 3: Once the API design is completed by the team, from Studio, the API can be transitioned from _draft_ status to _enabled_. This will fire a design finalized event from Apicurio Registry that will reach Kafka.  The API specification is saved directly into Apicurio Registry from Apicurio Studio.

* Step 4: (Optional) For each new version created, a new event is fired to Kafka.

* Step 5: As an example integration, a [Python script](./scripts/events-consumer.py) is provided. If you want to use this script, you have to change it to use the proper bootstrap servers and Apicurio Registry API values from your cluster. For each OpenApi that has been created in Apicurio Registry in enabled state, the Kuadrant CLI is invoked, generating the HTTPRoute, RateLimit policy and AuthPolicy (if they're defined). 

* Step 6: The events-consumer.py script then stores the API specification in the Git repository located in the directory `api-resources` for additional version control and traceability. Storing API specs in Git allows the team to maintain a full history of the API designs outside the registry, making it easier to audit, collaborate, or revert changes.

* Step 7: The git repository configured is used in a GitOps fashion, ArgoCD will take the resources defined in the git repository and sync them in Kuadrant.

* Step 8: Once the resources have been defined, the rate limits defined in the Petstore OpenAPI file are enforced. Now it's time to test it
  * Execute the following command to forward the traffic from localhost to the Istio service: ` kubectl port-forward -n gateway-system service/external-istio 9081:80`.
  * Execute `curl -H 'Host: petstore.io' http://localhost:9081/dog -i`. The dog endpoint does not have any rate limit defined, so you can execute this command as many times as you want.
  * Execute `curl -H 'Host: petstore.io' http://localhost:9081/cat -i`. The cat endpoint has a very aggressive rate limit policy (1req/10s), so the second time you execute the command you'll get a `429` error.

This project has been set up as an example of Kuadrant policy design and enforcement and as a potential workflow to be used in production. Just like with the rate limit policy applied to the cat endpoint, this flow can be used for any other Kuadrant resource, like authentication policies.