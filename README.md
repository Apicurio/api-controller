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

Any operator used in this demo must be installed using the Openshift console.

## Pre-requisites

* An available Openshift cluster must be available in the user's kubeconfig.
* Kuadrantctl is available locally. Instructions to install it can be found [here](https://github.com/Kuadrant/kuadrantctl?tab=readme-ov-file#installing-pre-compiled-binaries).
* oc cli is available locally.


## Installation

1. We must start by creating the namespace that will be used for this project:

  `oc apply -f ./deployment/namespace/apicurio-api-controller.yaml`

2. To enforce some restrictions for our APIs, we need Kuadrant installed in our cluster. Kuadrant has the Kubernetes Gateway API and a provider to work. We will use Istio for this project.

   * Install Kubernetes Gateway API by using: `oc apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v0.4.0/standard-install.yaml` 
   * Install Istio: 
```curl -L https://istio.io/downloadIstio | ISTIO_VERSION=1.22.5 sh -
./istio-1.22.5/bin/istioctl install --set profile=minimal
./istio-1.22.5/bin/istioctl operator init
kubectl apply -f https://raw.githubusercontent.com/Kuadrant/kuadrant-operator/main/config/dependencies/istio/istio-operator.yaml
```

   * Install Kuadrant Operator. The operator is available from the Openshift Console OperatorHub. Just follow [installation steps](https://docs.openshift.com/container-platform/4.11/operators/user/olm-installing-operators-in-namespace.html#olm-installing-from-operatorhub-using-web-console_olm-installing-operators-in-namespace) choosing the "Kuadrant Operator" from the catalog.

   * Once the operator has been installed, create the Kuadrant instance `oc apply -f ./deployment/kuadrant/kuadrant.yaml`

3. Now we have to deploy Strimzi. It can be installed from Operator Hub in Openshift or using the following command:

`oc create -f https://strimzi.io/install/latest?namespace=api-controller -n api-controller`

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

8. Install ArgoCD. For the full integration to work, argocd is required. It will sync the Kuadrant resources generated and apply them to the Openshift cluster. The argocd operator can be installed from the Openshift Console, just like Strimzi or Kuadrant. For convenience, we recomment installing the Red Hat OpenShift GitOps operator.

   * Once the ArgoCD operator has been installed, we must install the ArgoCD resources:
     * Create ArgoCD instance: `oc apply -f ./deployment/argocd/argocd_instance.yaml`
     * Create ArgoCD project: `oc apply -f ./deployment/argocd/argocd_project.yaml`
     * Create ArgoCD app: `oc apply -f ./deployment/argocd/argocd_app.yaml`


## Using the project.

In this section we will discuss an example that uses the different components that have been deployed above. We must follow the steps below:

* Step 1: The API design process starts in Apicurio Studio. This is where API developers, architects, and stakeholders define the API specification using the OpenAPI (or AsyncAPI) format. Here, they specify details like:
  * API paths (endpoints)
Methods (GET, POST, etc.)
Request/response formats
Security (OAuth2, JWT, etc.)
Rate limits, request quotas, etc.

* Step 2: We must go to Apicurio Studio and copy the [petstore API spec](./deployment/petstore/petstore-with-rate-limit.yaml). This OpenAPI spec has a rate limit specification defined using the x-kuadrant format.

* Step 3: Once the API design is completed by the team, from Studio, the API can be transitioned from _draft_ status to _enabled_. This will fire a design finalized event from Apicurio Registry that will reach Kafka.  the API specification is saved directly into Apicurio Registry from Apicurio Studio.

* Step 4: (Optional) For each new version created, a new event is fired to Kafka.

* Step 5: As an example integration, a [Python script](./scripts/events-consumer.py) is provided. For each OpenApi that has been created in Apicurio Registry in enabled state, the Kuadrant CLI is invoked, generating the HTTPRoute, RateLimit policy and AuthPolicy (if they're defined). 

* Step 5: Upon consuming an event, the events-consumer.py script extracts the metadata (such as artifact identifier and version) from the event and retrieves the latest version of the API specification from Apicurio Registry.

* Step 6: The events-consumer.py script then stores the API specification in a Git repository located in the directory api-resources for additional version control and traceability. Storing API specs in Git allows the team to maintain a full history of the API designs outside the registry, making it easier to audit, collaborate, or revert changes.

* Step 7: The events-consumer.py writes to a Git repo, that is used in a GitOps fashion to propagate changes to Kuadrant. An initial implementation will show how to achieve this via ArgoCD makes an API call to Kuadrant to apply or update the policies based on the spec. This step ensures that the API’s rate limits, authentication mechanisms, and traffic controls are enforced in line with the API’s definition.