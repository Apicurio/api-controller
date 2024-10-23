#!/bin/bash

kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.1/cert-manager.yaml
kubectl create -f https://operatorhub.io/install/kuadrant-operator.yaml
kubectl create -f https://strimzi.io/install/latest?namespace=api-controller -n api-controller

kubectl apply -f ./deployment/namespace/apicurio-api-controller.yaml

kubectl apply -f ./deployment/apicurio-registry/postgres.yaml
kubectl apply -f ./deployment/apicurio-registry/registry-sql.yaml
kubectl apply -f ./deployment/apicurio-studio/apicurio-studio.yaml

kubectl apply -f ./deployment/debezium/postgresql-source.yaml

kubectl apply -f ./deployment/kafka/kafka.yaml
kubectl apply -f ./deployment/kafka/kafka-connect.yaml

kubectl apply -f ./deployment/kuadrant/kuadrant.yaml

kubectl port-forward -n api-controller svc/kafka-cluster-kafka-bootstrap 9092:9092